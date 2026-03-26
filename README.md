# SAP O2C Graph System

A full-stack graph visualization and natural language query system for SAP Order-to-Cash data. Explore the complete O2C flow — from Sales Order through Delivery, Billing, Journal Entry, and Payment — as an interactive force-directed graph, then query it in plain English powered by Gemini.

## Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | FastAPI (Python) | Fast API dev, great async support |
| Database | SQLite | Zero setup, portable, sufficient for this scale |
| Graph Engine | NetworkX (in-memory) | Best Python graph library for analysis |
| Frontend | React + Vite + TypeScript | Fast build, modern DX |
| Graph Viz | react-force-graph-2d | Force-directed, performant canvas rendering |
| LLM | Google Gemini 2.0 Flash | Free tier generous, fast, structured JSON output |

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # paste your Gemini API key
python ingest.py             # one-time data ingestion (~30 seconds)
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

## Gemini API Key

Get a free key at: <https://aistudio.google.com/app/apikey>  
No credit card required. 15 requests/minute free.

---

## Architecture

### Why SQLite over Neo4j?

SQLite is zero-setup, portable, and the dataset is small enough (~50 K rows). Complex graph traversals are handled in Python with NetworkX after loading from SQLite. This avoids Cypher query complexity while keeping the analytical power of graph algorithms.

### Why NetworkX for graph construction?

The graph is built once at server startup and cached in memory. NetworkX enables rich algorithms (centrality, path finding, connected components) that would require complex Cypher in Neo4j. For a dataset of this scale, in-memory is fast enough.

### Why Gemini Flash for LLM?

Free tier with 15 RPM and 1 M TPM is sufficient for demo purposes. The structured JSON response format (`type` + `sql`/`message`) makes it robust against hallucination — if Gemini doesn't return valid JSON, the system catches it and returns an error rather than a fabricated answer.

### Guardrails strategy

Two layers:

1. **LLM-level** — System prompt explicitly instructs the model to return `{"type": "off_topic"}` for non-dataset queries.
2. **Code-level** — SQL executor only allows `SELECT` statements; any mutation attempt throws a `ValueError`.

---

## Graph Model

### Node types

| Node Type | Color | Key field |
|-----------|-------|-----------|
| Customer | `#FF6B6B` coral red | businessPartner |
| SalesOrder | `#4ECDC4` teal | salesOrder |
| Delivery | `#45B7D1` sky blue | deliveryDocument |
| BillingDocument | `#96CEB4` sage green | billingDocument |
| JournalEntry | `#FFEAA7` pale yellow | accountingDocument |
| Payment | `#DDA0DD` plum | accountingDocument + item |
| Product | `#98D8C8` mint | product |
| Plant | `#F7DC6F` golden | plant |

### Edge relationships

```
Customer        ──PLACED──►       SalesOrder
SalesOrder      ──HAS_DELIVERY──► DeliveryHeader
SalesOrder      ──CONTAINS──►     Product
DeliveryHeader  ──BILLED_IN──►    BillingDocument
BillingDocument ──GENERATES──►    JournalEntry
JournalEntry    ──CLEARED_BY──►   Payment
DeliveryHeader  ──SHIPPED_FROM──► Plant
BillingDocument ──CANCELLED_BY──► BillingDocument  (S1 type)
```

### O2C logic fixes implemented

- **Delivery → Billing join**: `billing_items.reference_sd_document = delivery_headers.delivery_document`
- **S1 cancellation edges**: billing docs with `billing_document_type = 'S1'` generate `CANCELLED_BY` edges back to their original billing doc via `billing_items.reference_sd_document`

---

## Example Queries

1. `Which products are associated with the highest number of billing documents?`
2. `Trace the full flow of billing document 91150187`
3. `Which sales orders were delivered but never billed?`
4. `Show me the top 5 customers by total revenue`
5. `How many payments have been cleared in April 2025?`
6. `Which plants handle the most deliveries?`
7. `Find all billing documents that were cancelled`

---

## Deployment

### Backend → Railway

1. Add `backend/Procfile`:
   ```
   web: uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
2. Set `GEMINI_API_KEY` as a Railway environment variable.
3. Add a startup script that runs `python ingest.py` if `data/o2c.db` doesn't exist yet.

### Frontend → Vercel

1. Update `frontend/.env.production` with your Railway URL.
2. Push `frontend/` to Vercel — `vercel.json` handles SPA routing automatically.
