# O2C Nexus: SAP S/4HANA Order-to-Cash AI Dashboard

> An interactive graph intelligence platform for analysing real SAP S/4HANA transactional data — built for portfolio demonstration and enterprise knowledge transfer.

---

## Overview

O2C Nexus ingests a real SAP S/4HANA Order-to-Cash dataset, models it as a directed property graph using NetworkX, and exposes it through a force-directed React dashboard with an embedded Groq-powered AI chat interface. Users can visually explore how a Sales Order flows through Delivery → Billing → Journal Entry → Payment, and ask natural-language questions that are answered with live SQL queries against the underlying SQLite database.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18 + Vite + TypeScript | SPA dashboard |
| **Graph Visualisation** | react-force-graph-2d | Force-directed canvas rendering |
| **Backend** | FastAPI (Python) | REST API + lifespan graph cache |
| **Graph Engine** | NetworkX `DiGraph` | In-memory transactional graph |
| **Database** | SQLite | Zero-setup, portable, S/4HANA schema |
| **AI / NL-to-SQL** | Groq — `llama-3.3-70b-versatile` | SQL generation (accuracy) |
| **AI / Summaries** | Groq — `llama-3.1-8b-instant` | Natural language answers (speed) |
| **Deployment** | Railway (backend) + Vercel (frontend) | Serverless + PaaS |

---

## Architecture

### Database Schema — strict S/4HANA mapping

The SQLite database mirrors SAP S/4HANA entity types exactly. Every table name and every column maps directly to the corresponding OData entity or field:

```
MASTER DATA
  business_partners          ← BusinessPartner (BuPa)
  business_partner_addresses ← BusinessPartnerAddress
  products                   ← Product
  product_descriptions       ← ProductDescription (language-filtered)
  plants                     ← Plant

ORDER MANAGEMENT
  sales_order_headers        ← SalesOrder (header)
  sales_order_items          ← SalesOrderItem

LOGISTICS
  outbound_delivery_headers  ← OutboundDeliveryHeader
  outbound_delivery_items    ← OutboundDeliveryItem

BILLING & FINANCE
  billing_document_headers   ← BillingDocument (header)
  billing_document_items     ← BillingDocumentItem
  billing_document_cancellations  ← S1 reversal link
  journal_entry_items_accounts_receivable  ← JournalEntryItem (AR)
  payments_accounts_receivable             ← PaymentAccountsReceivable
```

### Graph Model — transactional edges

The NetworkX `DiGraph` is built once at server startup and cached in memory. Nodes represent business entities; directed edges represent the O2C process flow:

```
SalesOrder   ──[HAS_ITEM]────────►  Product
SalesOrder   ──[DELIVERED_IN]────►  Delivery
Delivery     ──[BILLED_IN]───────►  BillingDocument
BillingDocument ──[POSTED_TO]───►  JournalEntry
JournalEntry ──[PAID_BY]────────►  Payment
BillingDocument ──[CANCELLED_BY]►  BillingDocument  (S1 reversal)
```

### AI Chat — two-model pipeline

```
User query
    │
    ▼
llama-3.3-70b-versatile  ←── SYSTEM_PROMPT (full schema + 5-step O2C join chain)
    │  JSON mode enforces {"type":"sql_query","sql":"...","explanation":"..."}
    ▼
SQLite executor  (SELECT-only guard)
    │
    ▼
llama-3.1-8b-instant  ←── results[:20] → concise natural-language answer
    │
    ▼
Response + highlighted graph node IDs
```

---

## Running Locally

### Prerequisites

- Python 3.9+
- Node.js 18+
- A free [Groq API key](https://console.groq.com) (no credit card required)

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# → paste your GROQ_API_KEY into .env

# Ingest the SAP dataset (creates backend/data/o2c.db)
python ingest.py

# Start the API server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Verify with:

```bash
curl http://localhost:8000/health
```

### Frontend

```bash
cd frontend

npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

> The Vite dev server proxies `/api/*` → `http://localhost:8000` so no CORS issues locally.

---

## Deployment

### Backend → Railway

1. Push this repository to GitHub.
2. Create a new Railway project and point it at the `backend/` directory.
3. Set the environment variable `GROQ_API_KEY` in Railway's Variables panel.
4. Railway auto-detects `Procfile` and runs:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
5. Note the Railway public URL (e.g. `https://o2c-nexus.up.railway.app`).

### Frontend → Vercel

1. Import the repository into Vercel and set the **Root Directory** to `frontend/`.
2. Add an environment variable:
   ```
   VITE_API_URL = https://o2c-nexus.up.railway.app/api
   ```
3. Deploy — `vercel.json` handles SPA routing automatically.

---

## Example Queries

Try these in the AI chat panel:

| Query | What it demonstrates |
|---|---|
| `Which customers have the highest total billed amount?` | Cross-table JOIN across 4 entities |
| `Trace the full O2C flow for sales order 740506` | 5-step chain traversal |
| `Which billing documents were cancelled and why?` | S1 cancellation analysis |
| `Show deliveries with pending goods movement status` | Logistics status filtering |
| `Which products appear in the most sales orders?` | Aggregation + ranking |
| `What is the total revenue billed in April 2025?` | Date-range financial query |

---

## Project Structure

```
O2C Nexus/
├── backend/
│   ├── main.py              # FastAPI app + lifespan graph cache
│   ├── ingest.py            # Production JSONL → SQLite pipeline
│   ├── database.py          # Schema DDL + reset_schema()
│   ├── graph_builder.py     # NetworkX DiGraph construction
│   ├── query_engine.py      # Groq NL-to-SQL engine
│   ├── requirements.txt
│   ├── Procfile             # Railway start command
│   └── railway.json         # Railway deployment config
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Layout + state management
│   │   ├── api.ts            # Typed fetch client (VITE_API_URL)
│   │   └── components/
│   │       ├── GraphCanvas.tsx    # ForceGraph2D + hover tooltip
│   │       ├── ChatPanel.tsx      # AI chat interface
│   │       └── NodeDetailPanel.tsx # Click-to-pin detail card
│   ├── vite.config.ts
│   └── vercel.json
└── dataset/
    └── sap-o2c-data/        # Real SAP S/4HANA JSONL export
        ├── sales_order_headers/
        ├── billing_document_headers/
        └── ...
```

---

## Data Source

The dataset is a real SAP S/4HANA sandbox export covering ~1,400 transactional records across 14 entity types in the Order-to-Cash process. All business identifiers are from a non-production sandbox environment.

---

## License

MIT
