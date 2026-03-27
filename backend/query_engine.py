import os
import json
import warnings

# Suppress the deprecation warning — google-generativeai still works correctly
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gemini-2.0-flash"

_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if _api_key:
    genai.configure(api_key=_api_key)


def _get_model() -> genai.GenerativeModel:
    if not _api_key:
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
plants(plant, plant_name, sales_organization)

KEY RELATIONSHIPS:
- sales_order_headers.sold_to_party -> customers.business_partner
- sales_order_items.sales_order -> sales_order_headers.sales_order
- sales_order_items.material -> products.product
- delivery_items.reference_sd_document -> sales_order_headers.sales_order (delivery links to SO)
- delivery_items.delivery_document -> delivery_headers.delivery_document
- delivery_items.plant -> plants.plant
- billing_items.reference_sd_document -> delivery_headers.delivery_document (billing links to delivery)
- billing_items.billing_document -> billing_headers.billing_document
- journal_entries.reference_document -> billing_headers.billing_document
- payments.accounting_document -> journal_entries.accounting_document

GUARDRAILS — IMPORTANT:
- You ONLY answer questions about this O2C dataset and SAP business processes.
- If the user asks about anything unrelated (general knowledge, coding, personal questions,
  creative writing, current events, etc.), respond ONLY with:
  {"type": "off_topic", "message": "This system is designed to answer questions about the Order-to-Cash dataset only. Please ask about sales orders, deliveries, billing, payments, customers, or products."}
- Never make up data. Always query the database.
- For tracing flows, use JOINs across all relevant tables.

RESPONSE FORMAT — always respond with valid JSON only, no markdown fences:
For data queries:   {"type": "sql_query", "sql": "SELECT ...", "explanation": "brief what this does"}
For off-topic:      {"type": "off_topic", "message": "..."}
For clarification:  {"type": "clarification", "message": "..."}
"""


def classify_and_generate_sql(user_query: str) -> dict:
    model = _get_model()
    prompt = f"{SYSTEM_PROMPT}\n\nUser query: {user_query}"
    response = model.generate_content(prompt)
    text = response.text.strip()

    # Strip accidental markdown code fences
    if "```" in text:
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
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
    if any(k in sql_upper for k in forbidden):
        raise ValueError("Security Violation: Only SELECT statements are allowed.")

    db_conn.row_factory = lambda cursor, row: {
        col[0]: row[idx] for idx, col in enumerate(cursor.description)
    }
    cursor = db_conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchmany(100)
    return list(rows)


def format_answer(user_query: str, sql: str, results: list) -> str:
    model = _get_model()
    prompt = (
        f'Given this query "{user_query}", this SQL "{sql}", '
        f"and these results: {json.dumps(results[:20])}, "
        f"write a clear, concise natural language answer. "
        f"Be specific with numbers. Max 3 sentences."
    )
    response = model.generate_content(prompt)
    return response.text.strip()


def answer_query(user_query: str, db_conn) -> dict:
    try:
        classification = classify_and_generate_sql(user_query)
    except Exception as e:
        print(f"Engine Error (classify): {e}")
        return {
            "answer": f"Error processing query: {str(e)}",
            "sql": None,
            "results": None,
            "node_ids": [],
        }

    if classification.get("type") in ("off_topic", "clarification"):
        return {
            "answer": classification.get("message", ""),
            "sql": None,
            "results": None,
            "node_ids": [],
        }

    if classification.get("type") == "sql_query":
        sql = classification.get("sql", "")
        try:
            results = execute_sql(sql, db_conn)
        except Exception as e:
            print(f"Engine Error (sql): {e}")
            return {
                "answer": f"Error executing query: {str(e)}",
                "sql": sql,
                "results": None,
                "node_ids": [],
            }

        try:
            answer = format_answer(user_query, sql, results)
        except Exception:
            answer = f"Query returned {len(results)} results."

        node_ids = []
        for row in results:
            mappings = {
                "sales_order": "so_",
                "delivery_document": "del_",
                "billing_document": "bill_",
                "accounting_document": "journal_",
                "business_partner": "customer_",
                "product": "product_",
            }
            for key, prefix in mappings.items():
                val = row.get(key)
                if val:
                    node_ids.append(f"{prefix}{val}")

        return {
            "answer": answer,
            "sql": sql,
            "results": results,
            "node_ids": list(set(node_ids)),
        }

    return {
        "answer": "Unable to process the query.",
        "sql": None,
        "results": None,
        "node_ids": [],
    }
