import sqlite3
import os

DB_PATH = "data/o2c.db"


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            business_partner TEXT PRIMARY KEY,
            full_name TEXT,
            city TEXT,
            country TEXT
        );

        CREATE TABLE IF NOT EXISTS sales_order_headers (
            sales_order TEXT PRIMARY KEY,
            sold_to_party TEXT,
            creation_date TEXT,
            total_net_amount REAL,
            overall_delivery_status TEXT,
            transaction_currency TEXT
        );

        CREATE TABLE IF NOT EXISTS sales_order_items (
            sales_order TEXT,
            sales_order_item TEXT,
            material TEXT,
            requested_quantity REAL,
            net_amount REAL,
            PRIMARY KEY (sales_order, sales_order_item)
        );

        CREATE TABLE IF NOT EXISTS delivery_headers (
            delivery_document TEXT PRIMARY KEY,
            creation_date TEXT,
            shipping_point TEXT,
            overall_goods_movement_status TEXT
        );

        CREATE TABLE IF NOT EXISTS delivery_items (
            delivery_document TEXT,
            delivery_document_item TEXT,
            reference_sd_document TEXT,
            reference_sd_document_item TEXT,
            plant TEXT,
            storage_location TEXT,
            PRIMARY KEY (delivery_document, delivery_document_item)
        );

        CREATE TABLE IF NOT EXISTS billing_headers (
            billing_document TEXT PRIMARY KEY,
            billing_document_type TEXT,
            creation_date TEXT,
            billing_document_date TEXT,
            total_net_amount REAL,
            sold_to_party TEXT,
            transaction_currency TEXT,
            billing_document_is_cancelled INTEGER
        );

        CREATE TABLE IF NOT EXISTS billing_items (
            billing_document TEXT,
            billing_document_item TEXT,
            material TEXT,
            billing_quantity REAL,
            net_amount REAL,
            reference_sd_document TEXT,
            reference_sd_document_item TEXT,
            PRIMARY KEY (billing_document, billing_document_item)
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            accounting_document TEXT,
            accounting_document_item TEXT,
            reference_document TEXT,
            gl_account TEXT,
            amount_in_transaction_currency REAL,
            transaction_currency TEXT,
            posting_date TEXT,
            profit_center TEXT,
            PRIMARY KEY (accounting_document, accounting_document_item)
        );

        CREATE TABLE IF NOT EXISTS payments (
            accounting_document TEXT,
            accounting_document_item TEXT,
            customer TEXT,
            clearing_date TEXT,
            clearing_accounting_document TEXT,
            amount_in_transaction_currency REAL,
            transaction_currency TEXT,
            invoice_reference TEXT,
            PRIMARY KEY (accounting_document, accounting_document_item)
        );

        CREATE TABLE IF NOT EXISTS products (
            product TEXT PRIMARY KEY,
            product_type TEXT,
            gross_weight REAL,
            weight_unit TEXT,
            product_description TEXT
        );

        CREATE TABLE IF NOT EXISTS plants (
            plant TEXT PRIMARY KEY,
            plant_name TEXT,
            sales_organization TEXT
        );
    """)

    conn.commit()
    conn.close()
