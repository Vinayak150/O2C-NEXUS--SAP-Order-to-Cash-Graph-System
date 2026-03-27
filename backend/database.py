import sqlite3
import os

DB_PATH = "data/o2c.db"

# ---------------------------------------------------------------------------
# Shared DDL — used by both init_db() and reset_schema()
# ---------------------------------------------------------------------------
_SCHEMA_DDL = """
    -- 1. Business Partners
    CREATE TABLE IF NOT EXISTS business_partners (
        businessPartnerId TEXT PRIMARY KEY,
        partnerType       TEXT,
        fullName          TEXT
    );

    -- 2. Business Partner Addresses
    CREATE TABLE IF NOT EXISTS business_partner_addresses (
        addressId         TEXT PRIMARY KEY,
        businessPartnerId TEXT NOT NULL,
        city              TEXT,
        country           TEXT,
        postalCode        TEXT,
        streetName        TEXT
    );

    -- 3. Sales Order Headers
    CREATE TABLE IF NOT EXISTS sales_order_headers (
        salesOrderId        TEXT PRIMARY KEY,
        customerId          TEXT,
        salesOrganization   TEXT,
        distributionChannel TEXT,
        division            TEXT,
        creationDate        TEXT,
        overallStatus       TEXT,
        totalNetAmount      REAL,
        currency            TEXT
    );

    -- 4. Sales Order Items
    CREATE TABLE IF NOT EXISTS sales_order_items (
        salesOrderId  TEXT,
        itemPosition  TEXT,
        productId     TEXT,
        orderQuantity REAL,
        netAmount     REAL,
        PRIMARY KEY (salesOrderId, itemPosition)
    );

    -- 5. Outbound Delivery Headers
    CREATE TABLE IF NOT EXISTS outbound_delivery_headers (
        deliveryId          TEXT PRIMARY KEY,
        shippingPoint       TEXT,
        deliveryDate        TEXT,
        goodsMovementStatus TEXT
    );

    -- 6. Outbound Delivery Items
    CREATE TABLE IF NOT EXISTS outbound_delivery_items (
        deliveryId              TEXT,
        itemPosition            TEXT,
        referenceSalesOrderId   TEXT,
        referenceSalesOrderItem TEXT,
        deliveredQuantity       REAL,
        plant                   TEXT,
        PRIMARY KEY (deliveryId, itemPosition)
    );

    -- 7. Billing Document Headers
    CREATE TABLE IF NOT EXISTS billing_document_headers (
        billingDocumentId  TEXT PRIMARY KEY,
        billingDate        TEXT,
        billingType        TEXT,
        customerId         TEXT,
        totalNetAmount     REAL,
        currency           TEXT,
        isCancelled        INTEGER DEFAULT 0
    );

    -- 8. Billing Document Items
    CREATE TABLE IF NOT EXISTS billing_document_items (
        billingDocumentId    TEXT,
        itemPosition         TEXT,
        referenceDeliveryId  TEXT,
        referenceDeliveryItem TEXT,
        billedAmount         REAL,
        productId            TEXT,
        PRIMARY KEY (billingDocumentId, itemPosition)
    );

    -- 9. Billing Document Cancellations
    CREATE TABLE IF NOT EXISTS billing_document_cancellations (
        cancelledBillingDocumentId    TEXT,
        cancellationBillingDocumentId TEXT,
        cancellationDate              TEXT,
        PRIMARY KEY (cancelledBillingDocumentId, cancellationBillingDocumentId)
    );

    -- 10. Journal Entry Items (Accounts Receivable)
    CREATE TABLE IF NOT EXISTS journal_entry_items_accounts_receivable (
        journalEntryId             TEXT PRIMARY KEY,
        referenceBillingDocumentId TEXT,
        amount                     REAL,
        currency                   TEXT,
        postingDate                TEXT,
        glAccount                  TEXT,
        profitCenter               TEXT
    );

    -- 11. Payments (Accounts Receivable)
    CREATE TABLE IF NOT EXISTS payments_accounts_receivable (
        paymentId              TEXT PRIMARY KEY,
        referenceJournalEntryId TEXT,
        paymentAmount          REAL,
        currency               TEXT,
        paymentDate            TEXT,
        customerId             TEXT
    );

    -- 12. Products
    CREATE TABLE IF NOT EXISTS products (
        productId   TEXT PRIMARY KEY,
        productType TEXT,
        grossWeight REAL,
        weightUnit  TEXT
    );

    -- 13. Product Descriptions
    CREATE TABLE IF NOT EXISTS product_descriptions (
        productId   TEXT,
        language    TEXT,
        productName TEXT,
        PRIMARY KEY (productId, language)
    );

    -- 14. Plants
    CREATE TABLE IF NOT EXISTS plants (
        plantId          TEXT PRIMARY KEY,
        plantName        TEXT,
        salesOrganization TEXT
    );
"""

_DROP_ALL_DDL = """
    -- Legacy table names (old snake_case schema)
    DROP TABLE IF EXISTS customers;
    DROP TABLE IF EXISTS delivery_headers;
    DROP TABLE IF EXISTS delivery_items;
    DROP TABLE IF EXISTS billing_headers;
    DROP TABLE IF EXISTS billing_items;
    DROP TABLE IF EXISTS journal_entries;
    DROP TABLE IF EXISTS payments;

    -- Current camelCase tables
    DROP TABLE IF EXISTS business_partners;
    DROP TABLE IF EXISTS business_partner_addresses;
    DROP TABLE IF EXISTS sales_order_headers;
    DROP TABLE IF EXISTS sales_order_items;
    DROP TABLE IF EXISTS outbound_delivery_headers;
    DROP TABLE IF EXISTS outbound_delivery_items;
    DROP TABLE IF EXISTS billing_document_headers;
    DROP TABLE IF EXISTS billing_document_items;
    DROP TABLE IF EXISTS billing_document_cancellations;
    DROP TABLE IF EXISTS journal_entry_items_accounts_receivable;
    DROP TABLE IF EXISTS payments_accounts_receivable;
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS product_descriptions;
    DROP TABLE IF EXISTS plants;
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    """Return an open connection with sqlite3.Row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Create new-schema tables if they don't already exist.
    Safe for server startup — does NOT drop data.
    Call reset_schema() from ingest.py for a full migration.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA_DDL)
    conn.commit()
    conn.close()


def reset_schema() -> None:
    """
    Drop ALL tables (old and new schema) then recreate the new schema.
    Destroys all existing data — call only from ingest.py.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_DROP_ALL_DDL)
    conn.executescript(_SCHEMA_DDL)
    conn.commit()
    conn.close()
    print("Schema reset complete.")
