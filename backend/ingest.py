"""
Production data pipeline for the SAP S/4HANA O2C dataset.

Layout on disk:
    dataset/sap-o2c-data/
        <table_name>/          ← subdirectory whose name == target table
            part-*.jsonl       ← one or more JSONL shards

Run from the backend/ directory:
    python ingest.py
"""

import os
import json
import sqlite3
from typing import Dict, List, Optional, Tuple

from database import reset_schema, DB_PATH

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# dataset/sap-o2c-data/ lives one level above backend/ inside the project root
DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "dataset", "sap-o2c-data"
)

CHUNK_SIZE = 1000  # rows per executemany() batch

# ---------------------------------------------------------------------------
# Column mapping
#   Each entry:  (db_column_name, jsonl_field_name)
#   jsonl_field_name = None  →  value is computed in _extract_row()
# ---------------------------------------------------------------------------

TABLE_COLUMN_MAPS: Dict[str, List[Tuple[str, Optional[str]]]] = {
    "business_partners": [
        ("businessPartnerId", "businessPartner"),
        ("partnerType",       "businessPartnerGrouping"),
        ("fullName",          "businessPartnerFullName"),
    ],
    "business_partner_addresses": [
        ("addressId",         "addressId"),
        ("businessPartnerId", "businessPartner"),
        ("city",              "cityName"),
        ("country",           "country"),
        ("postalCode",        "postalCode"),
        ("streetName",        "streetName"),
    ],
    "sales_order_headers": [
        ("salesOrderId",        "salesOrder"),
        ("customerId",          "soldToParty"),
        ("salesOrganization",   "salesOrganization"),
        ("distributionChannel", "distributionChannel"),
        ("division",            "organizationDivision"),
        ("creationDate",        "creationDate"),
        ("overallStatus",       "overallDeliveryStatus"),
        ("totalNetAmount",      "totalNetAmount"),
        ("currency",            "transactionCurrency"),
    ],
    "sales_order_items": [
        ("salesOrderId",  "salesOrder"),
        ("itemPosition",  "salesOrderItem"),
        ("productId",     "material"),
        ("orderQuantity", "requestedQuantity"),
        ("netAmount",     "netAmount"),
    ],
    "outbound_delivery_headers": [
        ("deliveryId",          "deliveryDocument"),
        ("shippingPoint",       "shippingPoint"),
        ("deliveryDate",        "creationDate"),
        ("goodsMovementStatus", "overallGoodsMovementStatus"),
    ],
    "outbound_delivery_items": [
        ("deliveryId",              "deliveryDocument"),
        ("itemPosition",            "deliveryDocumentItem"),
        ("referenceSalesOrderId",   "referenceSdDocument"),
        ("referenceSalesOrderItem", "referenceSdDocumentItem"),
        ("deliveredQuantity",       "actualDeliveryQuantity"),
        ("plant",                   "plant"),
    ],
    "billing_document_headers": [
        ("billingDocumentId", "billingDocument"),
        ("billingDate",       "billingDocumentDate"),
        ("billingType",       "billingDocumentType"),
        ("customerId",        "soldToParty"),
        ("totalNetAmount",    "totalNetAmount"),
        ("currency",          "transactionCurrency"),
        ("isCancelled",       None),          # computed: bool → 0/1
    ],
    "billing_document_items": [
        ("billingDocumentId",   "billingDocument"),
        ("itemPosition",        "billingDocumentItem"),
        ("referenceDeliveryId", "referenceSdDocument"),
        ("referenceDeliveryItem", "referenceSdDocumentItem"),
        ("billedAmount",        "netAmount"),
        ("productId",           "material"),
    ],
    "billing_document_cancellations": [
        # The cancellations folder contains S1-type docs.
        # cancelledBillingDocument = the original F2 doc being reversed.
        # billingDocument          = the S1 reversal doc itself.
        ("cancelledBillingDocumentId",    "cancelledBillingDocument"),
        ("cancellationBillingDocumentId", "billingDocument"),
        ("cancellationDate",              "billingDocumentDate"),
    ],
    "journal_entry_items_accounts_receivable": [
        # journalEntryId = accountingDocument (INSERT OR IGNORE → first item wins)
        ("journalEntryId",             "accountingDocument"),
        ("referenceBillingDocumentId", "referenceDocument"),
        ("amount",                     "amountInTransactionCurrency"),
        ("currency",                   "transactionCurrency"),
        ("postingDate",                "postingDate"),
        ("glAccount",                  "glAccount"),
        ("profitCenter",               "profitCenter"),
    ],
    "payments_accounts_receivable": [
        ("paymentId",               None),          # computed: doc + '_' + item
        ("referenceJournalEntryId", "accountingDocument"),
        ("paymentAmount",           "amountInTransactionCurrency"),
        ("currency",                "transactionCurrency"),
        ("paymentDate",             "clearingDate"),
        ("customerId",              "customer"),
    ],
    "products": [
        ("productId",   "product"),
        ("productType", "productType"),
        ("grossWeight", "grossWeight"),
        ("weightUnit",  "weightUnit"),
    ],
    "product_descriptions": [
        ("productId",   "product"),
        ("language",    "language"),
        ("productName", "productDescription"),
    ],
    "plants": [
        ("plantId",           "plant"),
        ("plantName",         "plantName"),
        ("salesOrganization", "salesOrganization"),
    ],
}

# ---------------------------------------------------------------------------
# Row extractor
# ---------------------------------------------------------------------------

def _extract_row(table: str, record: dict) -> tuple:
    """
    Return a tuple of values (one per DB column) for a single JSONL record.
    Missing JSONL keys are gracefully returned as None.
    Computed fields (jsonl_key is None) are handled with table-specific logic.
    """
    result = []
    for db_col, jsonl_key in TABLE_COLUMN_MAPS[table]:
        if jsonl_key is not None:
            result.append(record.get(jsonl_key))
        # ── computed fields ──────────────────────────────────────────────
        elif table == "billing_document_headers" and db_col == "isCancelled":
            result.append(1 if record.get("billingDocumentIsCancelled") else 0)
        elif table == "payments_accounts_receivable" and db_col == "paymentId":
            doc  = record.get("accountingDocument", "")
            item = record.get("accountingDocumentItem", "1") or "1"
            result.append(f"{doc}_{item}")
        else:
            result.append(None)
    return tuple(result)


# ---------------------------------------------------------------------------
# Core ingestion routine
# ---------------------------------------------------------------------------

def ingest_table(conn: sqlite3.Connection, table: str, folder_path: str) -> int:
    """
    Stream all .jsonl shards in folder_path into the target table.
    Uses INSERT OR IGNORE (duplicate PKs are silently skipped).
    Returns total number of records attempted.
    """
    cols         = [col for col, _ in TABLE_COLUMN_MAPS[table]]
    placeholders = ", ".join("?" * len(cols))
    insert_sql   = (
        f"INSERT OR IGNORE INTO {table} "
        f"({', '.join(cols)}) "
        f"VALUES ({placeholders})"
    )

    cursor      = conn.cursor()
    grand_total = 0

    for fname in sorted(os.listdir(folder_path)):
        if not fname.endswith(".jsonl"):
            continue

        fpath      = os.path.join(folder_path, fname)
        batch: list[tuple] = []
        file_rows  = 0
        errors     = 0

        with open(fpath, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                    batch.append(_extract_row(table, record))
                    file_rows += 1
                except (json.JSONDecodeError, KeyError, TypeError):
                    errors += 1
                    continue

                if len(batch) >= CHUNK_SIZE:
                    cursor.executemany(insert_sql, batch)
                    conn.commit()
                    batch.clear()

        if batch:
            cursor.executemany(insert_sql, batch)
            conn.commit()

        suffix = f"  ({errors} parse errors)" if errors else ""
        print(f"    {fname:<50}  {file_rows:>6} records{suffix}")
        grand_total += file_rows

    return grand_total


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 65)
    print("SAP O2C Production Ingestion Pipeline")
    print(f"Data source : {os.path.abspath(DATA_DIR)}")
    print(f"Database    : {os.path.abspath(DB_PATH)}")
    print("=" * 65)

    if not os.path.isdir(DATA_DIR):
        raise FileNotFoundError(
            f"Dataset folder not found:\n  {DATA_DIR}\n"
            "Please check the DATA_DIR path at the top of ingest.py."
        )

    print("\nResetting database schema …")
    reset_schema()
    print("Schema ready.\n")

    # Open a single connection for the whole pipeline
    conn = sqlite3.connect(DB_PATH)

    grand_total = 0
    tables_processed = 0
    tables_skipped   = 0

    for table in sorted(TABLE_COLUMN_MAPS.keys()):
        folder = os.path.join(DATA_DIR, table)
        if not os.path.isdir(folder):
            print(f"[SKIP]  {table}  (no matching folder found)")
            tables_skipped += 1
            continue

        print(f"[{table}]")
        count = ingest_table(conn, table, folder)
        print(f"  ↳  {count} rows ingested into {table}\n")
        grand_total   += count
        tables_processed += 1

    conn.close()

    print("=" * 65)
    print(f"Tables processed : {tables_processed}")
    print(f"Tables skipped   : {tables_skipped}")
    print(f"Total rows       : {grand_total:,}")
    print("=" * 65)


if __name__ == "__main__":
    main()
