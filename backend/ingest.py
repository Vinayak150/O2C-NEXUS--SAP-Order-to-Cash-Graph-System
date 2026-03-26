import os
import json

from database import get_db, init_db

# Updated path to correctly locate the dataset folder relative to the backend directory
DATASET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../dataset/sap-o2c-data")


def read_jsonl_files(folder_name):
    folder_path = os.path.join(DATASET_PATH, folder_name)
    records = []
    if not os.path.exists(folder_path):
        print(f"Warning: folder '{folder_path}' does not exist, skipping.")
        return records
    for filename in sorted(os.listdir(folder_path)):
        if filename.endswith(".jsonl"):
            filepath = os.path.join(folder_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    return records


def ingest_customers(conn):
    addresses = {}
    for record in read_jsonl_files("business_partner_addresses"):
        bp = record.get("businessPartner", "")
        if bp:
            addresses[bp] = {
                "city": record.get("cityName", ""),
                "country": record.get("country", ""),
            }

    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("business_partners"):
        bp = record.get("businessPartner", "")
        addr = addresses.get(bp, {})
        cursor.execute(
            """INSERT OR IGNORE INTO customers
               (business_partner, full_name, city, country)
               VALUES (?, ?, ?, ?)""",
            (
                bp,
                record.get("businessPartnerFullName", ""),
                addr.get("city", ""),
                addr.get("country", ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into customers")


def ingest_sales_order_headers(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("sales_order_headers"):
        cursor.execute(
            """INSERT OR IGNORE INTO sales_order_headers
               (sales_order, sold_to_party, creation_date, total_net_amount,
                overall_delivery_status, transaction_currency)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                record.get("salesOrder", ""),
                record.get("soldToParty", ""),
                record.get("creationDate", ""),
                record.get("totalNetAmount"),
                record.get("overallDeliveryStatus", ""),
                record.get("transactionCurrency", ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into sales_order_headers")


def ingest_sales_order_items(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("sales_order_items"):
        cursor.execute(
            """INSERT OR IGNORE INTO sales_order_items
               (sales_order, sales_order_item, material, requested_quantity, net_amount)
               VALUES (?, ?, ?, ?, ?)""",
            (
                record.get("salesOrder", ""),
                record.get("salesOrderItem", ""),
                record.get("material", ""),
                record.get("requestedQuantity"),
                record.get("netAmount"),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into sales_order_items")


def ingest_delivery_headers(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("outbound_delivery_headers"):
        cursor.execute(
            """INSERT OR IGNORE INTO delivery_headers
               (delivery_document, creation_date, shipping_point, overall_goods_movement_status)
               VALUES (?, ?, ?, ?)""",
            (
                record.get("deliveryDocument", ""),
                record.get("creationDate", ""),
                record.get("shippingPoint", ""),
                record.get("overallGoodsMovementStatus", ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into delivery_headers")


def ingest_delivery_items(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("outbound_delivery_items"):
        cursor.execute(
            """INSERT OR IGNORE INTO delivery_items
               (delivery_document, delivery_document_item, reference_sd_document,
                reference_sd_document_item, plant, storage_location)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                record.get("deliveryDocument", ""),
                record.get("deliveryDocumentItem", ""),
                record.get("referenceSdDocument", ""),
                record.get("referenceSdDocumentItem", ""),
                record.get("plant", ""),
                record.get("storageLocation", ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into delivery_items")


def ingest_billing_headers(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("billing_document_headers"):
        cursor.execute(
            """INSERT OR IGNORE INTO billing_headers
               (billing_document, billing_document_type, creation_date, billing_document_date,
                total_net_amount, sold_to_party, transaction_currency, billing_document_is_cancelled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("billingDocument", ""),
                record.get("billingDocumentType", ""),
                record.get("creationDate", ""),
                record.get("billingDocumentDate", ""),
                record.get("totalNetAmount"),
                record.get("soldToParty", ""),
                record.get("transactionCurrency", ""),
                1 if record.get("billingDocumentIsCancelled") else 0,
            ),
        )
        count += 1

    cancel_count = 0
    for record in read_jsonl_files("billing_document_cancellations"):
        cursor.execute(
            """INSERT OR IGNORE INTO billing_headers
               (billing_document, billing_document_type, creation_date, billing_document_date,
                total_net_amount, sold_to_party, transaction_currency, billing_document_is_cancelled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("billingDocument", ""),
                record.get("billingDocumentType", ""),
                record.get("creationDate", ""),
                record.get("billingDocumentDate", ""),
                record.get("totalNetAmount"),
                record.get("soldToParty", ""),
                record.get("transactionCurrency", ""),
                1,
            ),
        )
        cancel_count += 1

    conn.commit()
    print(f"Ingested {count} rows into billing_headers (+ {cancel_count} cancellations)")


def ingest_billing_items(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("billing_document_items"):
        cursor.execute(
            """INSERT OR IGNORE INTO billing_items
               (billing_document, billing_document_item, material, billing_quantity,
                net_amount, reference_sd_document, reference_sd_document_item)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("billingDocument", ""),
                record.get("billingDocumentItem", ""),
                record.get("material", ""),
                record.get("billingQuantity"),
                record.get("netAmount"),
                record.get("referenceSdDocument", ""),
                record.get("referenceSdDocumentItem", ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into billing_items")


def ingest_journal_entries(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("journal_entry_items_accounts_receivable"):
        cursor.execute(
            """INSERT OR IGNORE INTO journal_entries
               (accounting_document, accounting_document_item, reference_document, gl_account,
                amount_in_transaction_currency, transaction_currency, posting_date, profit_center)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("accountingDocument", ""),
                record.get("accountingDocumentItem") or "1",
                record.get("referenceDocument", ""),
                record.get("glAccount", ""),
                record.get("amountInTransactionCurrency"),
                record.get("transactionCurrency", ""),
                record.get("postingDate", ""),
                record.get("profitCenter", ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into journal_entries")


def ingest_payments(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("payments_accounts_receivable"):
        cursor.execute(
            """INSERT OR IGNORE INTO payments
               (accounting_document, accounting_document_item, customer, clearing_date,
                clearing_accounting_document, amount_in_transaction_currency,
                transaction_currency, invoice_reference)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("accountingDocument", ""),
                record.get("accountingDocumentItem", ""),
                record.get("customer", ""),
                record.get("clearingDate", ""),
                record.get("clearingAccountingDocument", ""),
                record.get("amountInTransactionCurrency"),
                record.get("transactionCurrency", ""),
                record.get("invoiceReference", ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into payments")


def ingest_products(conn):
    descriptions = {}
    for record in read_jsonl_files("product_descriptions"):
        if record.get("language", "") == "EN":
            product = record.get("product", "")
            if product:
                descriptions[product] = record.get("productDescription", "")

    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("products"):
        product = record.get("product", "")
        cursor.execute(
            """INSERT OR IGNORE INTO products
               (product, product_type, gross_weight, weight_unit, product_description)
               VALUES (?, ?, ?, ?, ?)""",
            (
                product,
                record.get("productType", ""),
                record.get("grossWeight"),
                record.get("weightUnit", ""),
                descriptions.get(product, ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into products")


def ingest_plants(conn):
    cursor = conn.cursor()
    count = 0
    for record in read_jsonl_files("plants"):
        cursor.execute(
            """INSERT OR IGNORE INTO plants
               (plant, plant_name, sales_organization)
               VALUES (?, ?, ?)""",
            (
                record.get("plant", ""),
                record.get("plantName", ""),
                record.get("salesOrganization", ""),
            ),
        )
        count += 1
    conn.commit()
    print(f"Ingested {count} rows into plants")


def main():
    print("Initializing database...")
    init_db()
    conn = get_db()
    try:
        ingest_customers(conn)
        ingest_sales_order_headers(conn)
        ingest_sales_order_items(conn)
        ingest_delivery_headers(conn)
        ingest_delivery_items(conn)
        ingest_billing_headers(conn)
        ingest_billing_items(conn)
        ingest_journal_entries(conn)
        ingest_payments(conn)
        ingest_products(conn)
        ingest_plants(conn)
        print("Ingestion complete!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()