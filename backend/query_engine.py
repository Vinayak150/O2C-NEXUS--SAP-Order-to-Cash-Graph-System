import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()

# 2. Configure the SDK with the exact authorized model
# Based on your diagnostic, 'gemini-2.0-flash' is the optimal choice.
MODEL_NAME = "gemini-2.0-flash"

api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def get_model():
    """Returns the Gemini model instance."""
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment.")
    return genai.GenerativeModel(MODEL_NAME)

SYSTEM_PROMPT = """You are a data analyst for an SAP Order-to-Cash (O2C) business process.
You have access to a SQLite database with these tables:

customers(business_partner, full_name, city, country)
sales_order_headers(sales_order, sold_to_party, creation_date, total_net_amount, overall_delivery_status, transaction_currency)
sales_order_items(sales_order, sales_order_item, material, requested_quantity, net_amount)
delivery_headers(delivery_document, creation_date, shipping_point, overall_goods_movement_status)
delivery_items(delivery_document, delivery_document_item, reference_sd_document, reference_sd_document_item, plant, storage_location)
billing_headers(billing_document, billing_document_type, creation_date, billing_document_date, total_net_amount, sold_to_party, transaction_currency, billing_document_is_cancelled)
billing_items(billing_document, billing_document_item, material, billing_quantity, net_amount, reference_sd_document, reference_sd_document_item)
journal_entries(accounting_document, accounting_document_item, reference_document, gl_account, amount_in_transaction_currency, transaction_currency, posting_date, profit_center)
payments(accounting_document, accounting_document_item, customer, clearing_date, clearing_accounting_document, amount_in_transaction_currency, transaction_currency, invoice_reference)
products(product, product_type, gross_weight, weight_unit, product_description)

KEY RELATIONSHIPS:
- sales_order_headers.sold_to_party -> customers.business_partner
- delivery_items.reference_sd_document -> sales_order_headers.sales_order
- billing_items.reference_sd_document -> delivery_headers.delivery_document
- journal_entries.reference_document -> billing_headers.billing_document
- payments.invoice_reference -> billing_headers.billing_document

RESPONSE FORMAT: Valid JSON only. No markdown.
For SQL: {"type": "sql_query", "sql": "SELECT ...", "explanation": "..."}
For Off-Topic: {"type": "off_topic", "message": "..."}
"""

def classify_and_generate_sql(user_query: str) -> dict:
    model = get_model()
    prompt = f"{SYSTEM_PROMPT}\n\nUser query: {user_query}"
    response = model.generate_content(prompt)
    
    text = response.text.strip()
    # Robust cleanup for any accidental markdown blocks
    if "```" in text:
        # Split by backticks and find the content block
        parts = text.split("```")
        for part in parts:
            if "{" in part and "}" in part:
                text = part.strip()
                if text.startswith("json"):
                    text = text[4:].strip()
                break
    
    return json.loads(text)

def execute_sql(sql: str, db_conn) -> list:
    sql_upper = sql.strip().upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE"]
    if any(k in sql_upper for k in forbidden):
        raise ValueError("Security Violation: Only SELECT statements allowed.")

    # Ensure results are returned as dictionaries
    db_conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    cursor = db_conn.cursor()
    cursor.execute(sql)
    return cursor.fetchall()

def format_answer(user_query: str, sql: str, results: list) -> str:
    model = get_model()
    prompt = (
        f"Query: {user_query}\nSQL: {sql}\nResults: {json.dumps(results[:10])}\n"
        "Briefly explain these results to a business user in 1-2 sentences."
    )
    response = model.generate_content(prompt)
    return response.text.strip()

def answer_query(user_query: str, db_conn) -> dict:
    try:
        classification = classify_and_generate_sql(user_query)
        
        if classification.get("type") != "sql_query":
            return {
                "answer": classification.get("message", "I am specialized in O2C data analysis."),
                "sql": None, "results": None, "node_ids": []
            }

        sql = classification["sql"]
        results = execute_sql(sql, db_conn)
        answer = format_answer(user_query, sql, results)

        # Map findings to Graph Node IDs for visualization highlighting
        node_ids = []
        for row in results:
            mappings = {
                "sales_order": "so_",
                "delivery_document": "del_",
                "billing_document": "bill_",
                "accounting_document": "journal_",
                "business_partner": "cust_",
                "product": "prod_"
            }
            for key, prefix in mappings.items():
                if row.get(key):
                    node_ids.append(f"{prefix}{row[key]}")

        return {
            "answer": answer,
            "sql": sql,
            "results": results,
            "node_ids": list(set(node_ids))
        }

    except Exception as e:
        print(f"Engine Error: {e}")
        return {
            "answer": f"System error: {str(e)}",
            "sql": None, "results": None, "node_ids": []
        }