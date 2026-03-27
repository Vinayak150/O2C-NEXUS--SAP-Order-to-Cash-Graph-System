import datetime
from decimal import Decimal

import networkx as nx

from database import get_db


# ---------------------------------------------------------------------------
# Serialisation helper
# ---------------------------------------------------------------------------

def sanitize_row(row) -> dict:
    """
    Convert a sqlite3.Row (or any mapping) to a plain dict, coercing every
    value to a JSON-safe Python primitive so graph_to_json never raises
    a TypeError.

    SQLite native types are already JSON-safe (str / int / float / None).
    Guards are present for datetime and Decimal in case a third-party
    adapter or future schema migration introduces them.
    """
    result: dict = {}
    for key in row.keys():
        val = row[key]
        if val is None:
            result[key] = None
        elif isinstance(val, (datetime.date, datetime.datetime)):
            result[key] = val.isoformat()
        elif isinstance(val, Decimal):
            result[key] = float(val)
        elif isinstance(val, bytes):
            result[key] = val.decode("utf-8", errors="replace")
        elif isinstance(val, (int, float, str, bool)):
            result[key] = val
        else:
            result[key] = str(val)
    return result


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> nx.DiGraph:
    conn = get_db()
    G = nx.DiGraph()
    cursor = conn.cursor()

    # -----------------------------------------------------------------------
    # NODES  — SELECT * so every column becomes a tooltip-visible attribute.
    #          type and label are injected after sanitize_row so they always
    #          win over any hypothetical same-named DB column.
    # -----------------------------------------------------------------------

    # --- Customers (business_partners) ---
    cursor.execute("SELECT * FROM business_partners")
    for row in cursor.fetchall():
        attrs = sanitize_row(row)
        attrs["type"] = "Customer"
        attrs["label"] = attrs.get("fullName") or attrs["businessPartnerId"]
        G.add_node(f"customer_{attrs['businessPartnerId']}", **attrs)

    # --- Sales Orders ---
    cursor.execute("SELECT * FROM sales_order_headers")
    for row in cursor.fetchall():
        attrs = sanitize_row(row)
        attrs["type"] = "SalesOrder"
        attrs["label"] = f"SO {attrs['salesOrderId']}"
        G.add_node(f"so_{attrs['salesOrderId']}", **attrs)

    # --- Deliveries ---
    cursor.execute("SELECT * FROM outbound_delivery_headers")
    for row in cursor.fetchall():
        attrs = sanitize_row(row)
        attrs["type"] = "Delivery"
        attrs["label"] = f"DEL {attrs['deliveryId']}"
        G.add_node(f"del_{attrs['deliveryId']}", **attrs)

    # --- Billing Documents ---
    cursor.execute("SELECT * FROM billing_document_headers")
    for row in cursor.fetchall():
        attrs = sanitize_row(row)
        attrs["type"] = "BillingDocument"
        attrs["label"] = f"BILL {attrs['billingDocumentId']}"
        G.add_node(f"bill_{attrs['billingDocumentId']}", **attrs)

    # --- Journal Entries  (prefix: je_) ---
    cursor.execute("SELECT * FROM journal_entry_items_accounts_receivable")
    for row in cursor.fetchall():
        attrs = sanitize_row(row)
        attrs["type"] = "JournalEntry"
        attrs["label"] = f"JE {attrs['journalEntryId']}"
        G.add_node(f"je_{attrs['journalEntryId']}", **attrs)

    # --- Payments  (prefix: pay_) ---
    cursor.execute("SELECT * FROM payments_accounts_receivable")
    for row in cursor.fetchall():
        attrs = sanitize_row(row)
        attrs["type"] = "Payment"
        attrs["label"] = f"PAY {attrs['paymentId']}"
        G.add_node(f"pay_{attrs['paymentId']}", **attrs)

    # --- Products  (prefix: prod_)
    #     LEFT JOIN product_descriptions to surface the human-readable name.
    cursor.execute(
        """SELECT p.*, pd.productName
           FROM products p
           LEFT JOIN product_descriptions pd
               ON pd.productId = p.productId AND pd.language = 'EN'"""
    )
    for row in cursor.fetchall():
        attrs = sanitize_row(row)
        attrs["type"] = "Product"
        attrs["label"] = attrs.get("productName") or attrs["productId"]
        G.add_node(f"prod_{attrs['productId']}", **attrs)

    # --- Plants ---
    cursor.execute("SELECT * FROM plants")
    for row in cursor.fetchall():
        attrs = sanitize_row(row)
        attrs["type"] = "Plant"
        attrs["label"] = attrs.get("plantName") or attrs["plantId"]
        G.add_node(f"plant_{attrs['plantId']}", **attrs)

    # -----------------------------------------------------------------------
    # EDGES
    # -----------------------------------------------------------------------

    # 1. SalesOrder –[HAS_ITEM]–► Product
    #    sales_order_items: salesOrderId → productId
    cursor.execute(
        """SELECT DISTINCT salesOrderId, productId FROM sales_order_items
           WHERE productId IS NOT NULL AND productId != ''"""
    )
    for row in cursor.fetchall():
        src = f"so_{row['salesOrderId']}"
        dst = f"prod_{row['productId']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="HAS_ITEM")

    # 2. SalesOrder –[DELIVERED_IN]–► Delivery
    #    outbound_delivery_items: referenceSalesOrderId → deliveryId
    cursor.execute(
        """SELECT DISTINCT referenceSalesOrderId, deliveryId
           FROM outbound_delivery_items
           WHERE referenceSalesOrderId IS NOT NULL AND referenceSalesOrderId != ''"""
    )
    for row in cursor.fetchall():
        src = f"so_{row['referenceSalesOrderId']}"
        dst = f"del_{row['deliveryId']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="DELIVERED_IN")

    # 3. Delivery –[BILLED_IN]–► BillingDocument
    #    billing_document_items: referenceDeliveryId → billingDocumentId
    cursor.execute(
        """SELECT DISTINCT referenceDeliveryId, billingDocumentId
           FROM billing_document_items
           WHERE referenceDeliveryId IS NOT NULL AND referenceDeliveryId != ''"""
    )
    for row in cursor.fetchall():
        src = f"del_{row['referenceDeliveryId']}"
        dst = f"bill_{row['billingDocumentId']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="BILLED_IN")

    # 4. BillingDocument –[POSTED_TO]–► JournalEntry
    #    journal_entry_items_accounts_receivable: referenceBillingDocumentId → journalEntryId
    cursor.execute(
        """SELECT DISTINCT referenceBillingDocumentId, journalEntryId
           FROM journal_entry_items_accounts_receivable
           WHERE referenceBillingDocumentId IS NOT NULL
             AND referenceBillingDocumentId != ''"""
    )
    for row in cursor.fetchall():
        src = f"bill_{row['referenceBillingDocumentId']}"
        dst = f"je_{row['journalEntryId']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="POSTED_TO")

    # 5. JournalEntry –[PAID_BY]–► Payment
    #    payments_accounts_receivable: referenceJournalEntryId → paymentId
    cursor.execute(
        """SELECT DISTINCT referenceJournalEntryId, paymentId
           FROM payments_accounts_receivable
           WHERE referenceJournalEntryId IS NOT NULL
             AND referenceJournalEntryId != ''"""
    )
    for row in cursor.fetchall():
        src = f"je_{row['referenceJournalEntryId']}"
        dst = f"pay_{row['paymentId']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="PAID_BY")

    # 6. BillingDocument –[CANCELLED_BY]–► BillingDocument (S1 reversal)
    #    billing_document_cancellations
    cursor.execute(
        """SELECT cancelledBillingDocumentId, cancellationBillingDocumentId
           FROM billing_document_cancellations
           WHERE cancelledBillingDocumentId IS NOT NULL
             AND cancellationBillingDocumentId IS NOT NULL"""
    )
    for row in cursor.fetchall():
        src = f"bill_{row['cancelledBillingDocumentId']}"
        dst = f"bill_{row['cancellationBillingDocumentId']}"
        if src in G and dst in G:
            G.add_edge(src, dst, relation="CANCELLED_BY")

    # -----------------------------------------------------------------------
    # ADVANCED GRAPH ANALYSIS — Degree-based node sizing
    # Inject a 'calculated_val' attribute onto every node so the frontend
    # can scale node radius proportionally to its connection count.
    # Formula: base size of 2 + 0.5 per connection (casted to float for
    # JSON serialisation safety).
    # -----------------------------------------------------------------------
    degrees = dict(G.degree())
    for node, degree in degrees.items():
        G.nodes[node]['calculated_val'] = float(2.0 + (degree * 0.5))

    conn.close()
    return G


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def graph_to_json(G: nx.DiGraph) -> dict:
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

    node_types: dict = {}
    for node in nodes:
        t = node.get("type", "Unknown")
        node_types[t] = node_types.get(t, 0) + 1

    # Cap at 2000 nodes for frontend performance, sampling evenly across types
    if len(nodes) > 2000:
        type_buckets: dict = {}
        for node in nodes:
            t = node.get("type", "Unknown")
            type_buckets.setdefault(t, []).append(node)
        per_type_limit = max(1, 2000 // len(type_buckets))
        sampled: list = []
        for type_nodes in type_buckets.values():
            sampled.extend(type_nodes[:per_type_limit])
        nodes = sampled[:2000]

    # Drop edges whose endpoints were sampled out
    if len(links) > 5000:
        node_id_set = {n["id"] for n in nodes}
        links = [
            lnk for lnk in links
            if lnk["source"] in node_id_set and lnk["target"] in node_id_set
        ][:5000]

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(links),
            "node_types": node_types,
        },
    }
