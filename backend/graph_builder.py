import networkx as nx

from database import get_db


def build_graph():
    conn = get_db()
    G = nx.DiGraph()
    cursor = conn.cursor()

    # --- NODES ---

    cursor.execute("SELECT business_partner, full_name, city, country FROM customers")
    for row in cursor.fetchall():
        G.add_node(
            f"customer_{row['business_partner']}",
            type="Customer",
            label=row["full_name"] or row["business_partner"],
            city=row["city"],
            country=row["country"],
        )

    cursor.execute(
        """SELECT sales_order, sold_to_party, total_net_amount, transaction_currency,
                  creation_date, overall_delivery_status
           FROM sales_order_headers"""
    )
    for row in cursor.fetchall():
        G.add_node(
            f"so_{row['sales_order']}",
            type="SalesOrder",
            label=f"SO {row['sales_order']}",
            amount=row["total_net_amount"],
            currency=row["transaction_currency"],
            creation_date=row["creation_date"],
            delivery_status=row["overall_delivery_status"],
        )

    cursor.execute(
        """SELECT delivery_document, creation_date, overall_goods_movement_status
           FROM delivery_headers"""
    )
    for row in cursor.fetchall():
        G.add_node(
            f"del_{row['delivery_document']}",
            type="Delivery",
            label=f"DEL {row['delivery_document']}",
            creation_date=row["creation_date"],
            goods_movement_status=row["overall_goods_movement_status"],
        )

    cursor.execute(
        """SELECT billing_document, total_net_amount, transaction_currency,
                  billing_document_is_cancelled, billing_document_type
           FROM billing_headers"""
    )
    for row in cursor.fetchall():
        G.add_node(
            f"bill_{row['billing_document']}",
            type="BillingDocument",
            label=f"BILL {row['billing_document']}",
            amount=row["total_net_amount"],
            currency=row["transaction_currency"],
            is_cancelled=row["billing_document_is_cancelled"],
            billing_document_type=row["billing_document_type"],
        )

    cursor.execute("SELECT DISTINCT accounting_document FROM journal_entries")
    for row in cursor.fetchall():
        G.add_node(
            f"journal_{row['accounting_document']}",
            type="JournalEntry",
            label=f"JE {row['accounting_document']}",
        )

    cursor.execute(
        """SELECT accounting_document, accounting_document_item,
                  amount_in_transaction_currency, transaction_currency, clearing_date
           FROM payments"""
    )
    for row in cursor.fetchall():
        G.add_node(
            f"payment_{row['accounting_document']}_{row['accounting_document_item']}",
            type="Payment",
            label=f"PAY {row['accounting_document']}",
            amount=row["amount_in_transaction_currency"],
            currency=row["transaction_currency"],
            clearing_date=row["clearing_date"],
        )

    cursor.execute("SELECT product, product_type, product_description FROM products")
    for row in cursor.fetchall():
        G.add_node(
            f"product_{row['product']}",
            type="Product",
            label=row["product_description"] or row["product"],
            product_type=row["product_type"],
        )

    cursor.execute("SELECT plant, plant_name, sales_organization FROM plants")
    for row in cursor.fetchall():
        G.add_node(
            f"plant_{row['plant']}",
            type="Plant",
            label=row["plant_name"] or row["plant"],
            plant_code=row["plant"],
        )

    # --- EDGES ---

    # 1. Customer PLACED SalesOrder
    cursor.execute("SELECT sold_to_party, sales_order FROM sales_order_headers")
    for row in cursor.fetchall():
        src = f"customer_{row['sold_to_party']}"
        dst = f"so_{row['sales_order']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="PLACED")

    # 2. SalesOrder CONTAINS Product (via sales_order_items.material)
    cursor.execute(
        """SELECT DISTINCT sales_order, material FROM sales_order_items
           WHERE material IS NOT NULL AND material != ''"""
    )
    for row in cursor.fetchall():
        src = f"so_{row['sales_order']}"
        dst = f"product_{row['material']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="CONTAINS")

    # 3. SalesOrder HAS_DELIVERY Delivery
    #    delivery_items.reference_sd_document = sales_order_headers.sales_order
    cursor.execute(
        """SELECT DISTINCT reference_sd_document, delivery_document FROM delivery_items
           WHERE reference_sd_document IS NOT NULL AND reference_sd_document != ''"""
    )
    for row in cursor.fetchall():
        src = f"so_{row['reference_sd_document']}"
        dst = f"del_{row['delivery_document']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="HAS_DELIVERY")

    # 4. Delivery BILLED_IN BillingDocument
    #    O2C FIX: billing_items.reference_sd_document = delivery_headers.delivery_document
    cursor.execute(
        """SELECT DISTINCT reference_sd_document, billing_document FROM billing_items
           WHERE reference_sd_document IS NOT NULL AND reference_sd_document != ''"""
    )
    for row in cursor.fetchall():
        src = f"del_{row['reference_sd_document']}"
        dst = f"bill_{row['billing_document']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="BILLED_IN")

    # 5. BillingDocument GENERATES JournalEntry
    #    journal_entries.reference_document = billing_headers.billing_document
    cursor.execute(
        """SELECT DISTINCT reference_document, accounting_document FROM journal_entries
           WHERE reference_document IS NOT NULL AND reference_document != ''"""
    )
    for row in cursor.fetchall():
        src = f"bill_{row['reference_document']}"
        dst = f"journal_{row['accounting_document']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="GENERATES")

    # 6. JournalEntry CLEARED_BY Payment
    #    payments.accounting_document = journal_entries.accounting_document
    cursor.execute(
        """SELECT DISTINCT je.accounting_document,
                  p.accounting_document AS pay_doc,
                  p.accounting_document_item
           FROM journal_entries je
           JOIN payments p ON je.accounting_document = p.accounting_document"""
    )
    for row in cursor.fetchall():
        src = f"journal_{row['accounting_document']}"
        dst = f"payment_{row['pay_doc']}_{row['accounting_document_item']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="CLEARED_BY")

    # 7. Delivery SHIPPED_FROM Plant (delivery_items.plant)
    cursor.execute(
        """SELECT DISTINCT delivery_document, plant FROM delivery_items
           WHERE plant IS NOT NULL AND plant != ''"""
    )
    for row in cursor.fetchall():
        src = f"del_{row['delivery_document']}"
        dst = f"plant_{row['plant']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="SHIPPED_FROM")

    # S1 Cancellation edges: BillingDocument CANCELLED_BY BillingDocument(type=S1)
    # billing_items for S1-type docs reference the original billing document
    cursor.execute(
        """SELECT bi.reference_sd_document AS original_doc,
                  bi.billing_document AS cancel_doc
           FROM billing_items bi
           JOIN billing_headers bh ON bi.billing_document = bh.billing_document
           WHERE bh.billing_document_type = 'S1'
             AND bi.reference_sd_document IS NOT NULL
             AND bi.reference_sd_document != ''"""
    )
    for row in cursor.fetchall():
        src = f"bill_{row['original_doc']}"
        dst = f"bill_{row['cancel_doc']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="CANCELLED_BY")

    conn.close()
    return G


def graph_to_json(G):
    nodes = []
    for node_id, attrs in G.nodes(data=True):
        node_data = {"id": node_id}
        node_data.update(attrs)
        nodes.append(node_data)

    links = []
    for src, dst, attrs in G.edges(data=True):
        link_data = {"source": src, "target": dst}
        link_data.update(attrs)
        links.append(link_data)

    node_types = {}
    for node in nodes:
        t = node.get("type", "Unknown")
        node_types[t] = node_types.get(t, 0) + 1

    if len(nodes) > 2000:
        type_buckets = {}
        for node in nodes:
            t = node.get("type", "Unknown")
            if t not in type_buckets:
                type_buckets[t] = []
            type_buckets[t].append(node)

        total_types = len(type_buckets)
        per_type_limit = max(1, 2000 // total_types)
        sampled_nodes = []
        for t, type_nodes in type_buckets.items():
            sampled_nodes.extend(type_nodes[:per_type_limit])
        nodes = sampled_nodes[:2000]

    if len(links) > 5000:
        node_id_set = {n["id"] for n in nodes}
        filtered_links = [
            lnk for lnk in links
            if lnk["source"] in node_id_set and lnk["target"] in node_id_set
        ]
        links = filtered_links[:5000]

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(links),
            "node_types": node_types,
        },
    }
