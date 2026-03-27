import os
import json
from typing import Dict, List, Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Module-level client — instantiated once at startup
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Updated to the new active Groq models
# llama-3.3-70b-versatile → SQL generation (accuracy critical)
SQL_MODEL = "llama-3.3-70b-versatile"

# llama-3.1-8b-instant    → Natural language summaries (speed/cost optimised)
NL_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are a data analyst for an SAP S/4HANA Order-to-Cash (O2C) business process.
You have access to a SQLite database with the following tables and columns:

MASTER DATA
  business_partners(businessPartnerId, partnerType, fullName)
  business_partner_addresses(addressId, businessPartnerId, city, country, postalCode, streetName)
  products(productId, productType, grossWeight, weightUnit)
  product_descriptions(productId, language, productName)
  plants(plantId, plantName, salesOrganization)

ORDER MANAGEMENT
  sales_order_headers(salesOrderId, customerId, salesOrganization, distributionChannel, division, creationDate, overallStatus, totalNetAmount, currency)
  sales_order_items(salesOrderId, itemPosition, productId, orderQuantity, netAmount)

LOGISTICS
  outbound_delivery_headers(deliveryId, shippingPoint, deliveryDate, goodsMovementStatus)
  outbound_delivery_items(deliveryId, itemPosition, referenceSalesOrderId, referenceSalesOrderItem, deliveredQuantity, plant)

BILLING & FINANCE
  billing_document_headers(billingDocumentId, billingDate, billingType, customerId, totalNetAmount, currency, isCancelled)
  billing_document_items(billingDocumentId, itemPosition, referenceDeliveryId, referenceDeliveryItem, billedAmount, productId)
  billing_document_cancellations(cancelledBillingDocumentId, cancellationBillingDocumentId, cancellationDate)
  journal_entry_items_accounts_receivable(journalEntryId, referenceBillingDocumentId, amount, currency, postingDate, glAccount, profitCenter)
  payments_accounts_receivable(paymentId, referenceJournalEntryId, paymentAmount, currency, paymentDate, customerId)

KEY O2C JOINS & RELATIONSHIPS:

  Step 1 — SO to Customer:
    sales_order_headers.customerId = business_partners.businessPartnerId

  Step 2 — SO to Delivery:
    outbound_delivery_items.referenceSalesOrderId = sales_order_headers.salesOrderId
    (outbound_delivery_items.deliveryId links items to outbound_delivery_headers.deliveryId)

  Step 3 — Delivery to Billing:
    billing_document_items.referenceDeliveryId = outbound_delivery_headers.deliveryId
    (billing_document_items.billingDocumentId links items to billing_document_headers.billingDocumentId)

  Step 4 — Billing to Journal Entry:
    journal_entry_items_accounts_receivable.referenceBillingDocumentId = billing_document_headers.billingDocumentId

  Step 5 — Journal Entry to Payment:
    payments_accounts_receivable.referenceJournalEntryId = journal_entry_items_accounts_receivable.journalEntryId

  Cancellations:
    billing_document_cancellations.cancelledBillingDocumentId = billing_document_headers.billingDocumentId
    (cancellationBillingDocumentId is the S1 reversal document)

SUPPLEMENTARY JOINS:
  - business_partner_addresses.businessPartnerId = business_partners.businessPartnerId
  - sales_order_items.salesOrderId = sales_order_headers.salesOrderId
  - sales_order_items.productId = products.productId
  - product_descriptions.productId = products.productId  (use language = 'EN' for names)
  - outbound_delivery_items.plant = plants.plantId

BUSINESS LOGIC & DEFINITIONS:
- "Sales" or "Most Sales": Calculate this by summing `netAmount` from `sales_order_items` grouped by `productId`, or by counting `salesOrderId`. DO NOT over-join to billing or delivery tables unless explicitly requested.
- "Revenue": Calculate this by summing `billedAmount` in `billing_document_items`.
- "Customers": Always refers to `businessPartnerId` in the `business_partners` table.
- GOLDEN RULE FOR SQL: Keep queries as simple as possible. Only JOIN the tables that are strictly required to answer the user's question. Avoid massive 5-table joins if a 2-table join gives the answer.

GUARDRAILS:
1. You must restrict all answers exclusively to the SAP O2C dataset and domain.
2. If the user asks a general knowledge question, requests creative writing, or asks about completely irrelevant topics, you MUST reject it.
3. To reject the prompt, you must output ONLY this JSON format, using this exact phrasing:
   {"type": "off_topic", "message": "This system is designed to answer questions related to the provided dataset only."}

ADDITIONAL RULES:
- Never fabricate data. Every answer must be backed by a SQL query against the database.
- For full O2C flow traces, chain JOINs through all 5 steps above.
- billingType = 'S1' means a cancellation/reversal document.
- isCancelled = 1 means the billing document has been cancelled.

RESPONSE FORMAT — respond with valid JSON only, no markdown fences:
For data queries:   {"type": "sql_query", "sql": "SELECT ...", "explanation": "brief what this does"}
For off-topic:      {"type": "off_topic", "message": "This system is designed to answer questions related to the provided dataset only."}
For clarification:  {"type": "clarification", "message": "..."}
"""

def classify_and_generate_sql(
    user_query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> dict:
    """
    Use the larger model for accurate SQL generation.
    chat_history is injected between the system prompt and the current user
    message so the model can resolve pronouns and references from prior turns.
    JSON mode enforces valid output.
    """
    # Cap history at 20 messages (10 turns) to stay well within token limits
    history = (chat_history or [])[-20:]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_query},
    ]

    response = client.chat.completions.create(
        model=SQL_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    text = response.choices[0].message.content.strip()
    return json.loads(text)


def execute_sql(sql: str, db_conn) -> list:
    """Execute a SELECT-only query and return rows as dicts. Max 100 rows."""
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
    """Use the smaller, faster model for natural language summaries."""
    response = client.chat.completions.create(
        model=NL_MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    f'Given this query "{user_query}", this SQL "{sql}", '
                    f"and these results: {json.dumps(results[:20])}, "
                    f"write a clear, concise natural language answer. "
                    f"Be specific with numbers. Max 3 sentences."
                ),
            }
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def answer_query(
    user_query: str,
    db_conn,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> dict:
    try:
        classification = classify_and_generate_sql(user_query, chat_history)
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

        # Map result column names to graph node ID prefixes
        node_ids = []
        for row in results:
            mappings = {
                "salesOrderId":          "so_",
                "deliveryId":            "del_",
                "billingDocumentId":     "bill_",
                "journalEntryId":        "je_",
                "paymentId":             "pay_",
                "businessPartnerId":     "customer_",
                "productId":             "prod_",
                "plantId":               "plant_",
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