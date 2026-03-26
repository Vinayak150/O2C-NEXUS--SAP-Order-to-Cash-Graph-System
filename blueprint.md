# SAP Order-to-Cash Graph System — Complete Build Guide
> For use with Cursor Pro. Follow each prompt in order.

---

## Architecture Overview

```
sap-o2c-graph/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── ingest.py            # JSONL → SQLite ingestion
│   ├── graph_builder.py     # SQLite → NetworkX graph
│   ├── query_engine.py      # NL → SQL + LLM answer
│   ├── database.py          # DB connection + schema
│   └── data/
│       └── o2c.db           # SQLite database (generated)
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── GraphCanvas.tsx   # react-force-graph-2d
│   │   │   ├── ChatPanel.tsx     # Chat interface
│   │   │   └── NodeTooltip.tsx   # Node detail popup
│   │   └── api.ts           # API client
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

**Stack:**
| Layer | Choice | Why |
|-------|--------|-----|
| Backend | FastAPI (Python) | Fast API dev, great async support |
| Database | SQLite | Zero setup, portable, sufficient for this scale |
| Graph Engine | NetworkX (in-memory) | Best Python graph library for analysis |
| Frontend | React + Vite + TypeScript | Fast build, modern DX |
| Graph Viz | react-force-graph-2d | Force-directed, exactly like screenshots |
| LLM | Google Gemini 2.0 Flash (free) | Free tier generous, fast |

---

## Graph Model

### Nodes (7 entity types)

| Node Type | Key Field | Label |
|-----------|-----------|-------|
| Customer | businessPartner | Customer name |
| SalesOrder | salesOrder | SO number |
| SalesOrderItem | salesOrder+salesOrderItem | SO+item |
| DeliveryHeader | deliveryDocument | Delivery number |
| BillingDocument | billingDocument | Billing number |
| JournalEntry | accountingDocument | Journal number |
| Payment | accountingDocument+item | Payment ref |
| Product | product | Product ID |
| Plant | plant | Plant code |

### Edges (relationships)

```
Customer ──PLACED──► SalesOrder          (soldToParty)
SalesOrder ──HAS──► SalesOrderItem       (salesOrder)
SalesOrderItem ──REFERENCES──► Product  (material)
SalesOrderItem ──FULFILLED_BY──► DeliveryHeader  (via DeliveryItem)
DeliveryHeader ──BILLED_IN──► BillingDocument    (via BillingItem)
BillingDocument ──GENERATES──► JournalEntry      (referenceDocument)
JournalEntry ──CLEARED_BY──► Payment             (accountingDocument)
DeliveryHeader ──SHIPPED_FROM──► Plant           (plant in delivery item)
```

---

## Step-by-Step Cursor Prompts

---

### PROMPT 1 — Project Scaffold

```
Create a new project called sap-o2c-graph with this structure:
- backend/ (Python FastAPI)
- frontend/ (React + Vite + TypeScript)

In backend/, create:
1. requirements.txt with: fastapi, uvicorn, python-multipart, networkx, google-generativeai, pydantic

In frontend/, run: npm create vite@latest . -- --template react-ts
Then install: npm install react-force-graph-2d three @types/three

Create a root package.json with scripts:
  "dev:backend": "cd backend && uvicorn main:app --reload --port 8000"
  "dev:frontend": "cd frontend && npm run dev"
```

---

### PROMPT 2 — Database Schema & Ingestion

Paste this prompt into Cursor:

```
In backend/database.py, create a SQLite database with these tables using Python's sqlite3 module:

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

Export a get_db() function returning a sqlite3 connection with row_factory = sqlite3.Row.
Export an init_db() function that creates all tables.
Export DB_PATH = "data/o2c.db"
```

---

### PROMPT 3 — Data Ingestion Script

```
In backend/ingest.py, write a Python script that reads all JSONL files from the dataset
and inserts them into the SQLite database defined in database.py.

The dataset is at: ../../dataset/sap-o2c-data/ (relative to backend/)
Each folder has one or more .jsonl files. Read them all.

Ingest these mappings:

1. business_partners/ → customers table
   Fields: businessPartner→business_partner, businessPartnerFullName→full_name
   Also join with business_partner_addresses/: cityName→city, country→country

2. sales_order_headers/ → sales_order_headers table
   Fields: salesOrder, soldToParty, creationDate, totalNetAmount, overallDeliveryStatus, transactionCurrency

3. sales_order_items/ → sales_order_items table
   Fields: salesOrder, salesOrderItem, material, requestedQuantity, netAmount

4. outbound_delivery_headers/ → delivery_headers table
   Fields: deliveryDocument, creationDate, shippingPoint, overallGoodsMovementStatus

5. outbound_delivery_items/ → delivery_items table
   Fields: deliveryDocument, deliveryDocumentItem, referenceSdDocument, referenceSdDocumentItem, plant, storageLocation

6. billing_document_headers/ AND billing_document_cancellations/ → billing_headers table
   Fields: billingDocument, billingDocumentType, creationDate, billingDocumentDate, totalNetAmount, soldToParty, transactionCurrency, billingDocumentIsCancelled

7. billing_document_items/ → billing_items table
   Fields: billingDocument, billingDocumentItem, material, billingQuantity, netAmount, referenceSdDocument, referenceSdDocumentItem

8. journal_entry_items_accounts_receivable/ → journal_entries table
   Fields: accountingDocument, accountingDocumentItem (use "1" if missing), referenceDocument, glAccount, amountInTransactionCurrency, transactionCurrency, postingDate, profitCenter

9. payments_accounts_receivable/ → payments table
   Fields: accountingDocument, accountingDocumentItem, customer, clearingDate, clearingAccountingDocument, amountInTransactionCurrency, transactionCurrency, invoiceReference

10. products/ → products table
    Also join with product_descriptions/ where language='EN': productDescription→product_description
    Fields: product, productType, grossWeight, weightUnit

11. plants/ → plants table
    Fields: plant, plantName, salesOrganization

Use INSERT OR IGNORE to avoid duplicates.
Add a main() function that calls init_db() then ingests all tables.
Print progress: "Ingested X rows into TABLE_NAME"

Run this as: python ingest.py
```

---

### PROMPT 4 — Graph Builder

```
In backend/graph_builder.py, build a NetworkX DiGraph from the SQLite database.

Import networkx as nx and the get_db() function from database.

Build the graph with this exact node/edge structure:

NODES — use add_node(id, **attributes):
  - f"customer_{bp}" for each customer (type="Customer", label=full_name, city, country)
  - f"so_{so}" for each sales order (type="SalesOrder", label=f"SO {so}", amount, currency, creation_date, delivery_status)
  - f"del_{doc}" for each delivery (type="Delivery", label=f"DEL {doc}", creation_date, goods_movement_status)
  - f"bill_{doc}" for each billing doc (type="BillingDocument", label=f"BILL {doc}", amount, currency, is_cancelled)
  - f"journal_{doc}" for each unique accounting_document in journal_entries (type="JournalEntry", label=f"JE {doc}")
  - f"payment_{doc}_{item}" for each payment (type="Payment", label=f"PAY {doc}", amount, currency, clearing_date)
  - f"product_{p}" for each product (type="Product", label=product or product_description, product_type)
  - f"plant_{p}" for each plant (type="Plant", label=plant_name, plant_code=plant)

EDGES — use add_edge(src, dst, relation="..."):
  1. customer → sales_order: Customer PLACED SalesOrder (join on soldToParty)
  2. sales_order → product: SalesOrder CONTAINS Product (join sales_order_items on material)
  3. delivery_item links SalesOrder → Delivery: SO HAS_DELIVERY Delivery (join delivery_items.referenceSdDocument = sales_order)
  4. billing_item links Delivery → Billing: Delivery BILLED_IN BillingDocument (join billing_items.referenceSdDocument = delivery_document)
  5. BillingDocument → JournalEntry: Billing GENERATES JournalEntry (journal_entries.referenceDocument = billingDocument)
  6. JournalEntry → Payment: JournalEntry CLEARED_BY Payment (payments.accountingDocument = journal_entries.accountingDocument)
  7. Delivery → Plant: Delivery SHIPPED_FROM Plant (delivery_items.plant)

Export two functions:
  build_graph() → returns nx.DiGraph
  graph_to_json(G) → returns dict with:
    - nodes: list of {id, type, label, ...all attributes}
    - links: list of {source, target, relation}
    - stats: {node_count, edge_count, node_types: {type: count}}
  
  In graph_to_json, LIMIT nodes to max 2000 and edges to max 5000 for frontend performance.
  Sample evenly across types if over limit.
```

---

### PROMPT 5 — Query Engine (LLM + SQL)

```
In backend/query_engine.py, build the NL-to-SQL query engine using Google Gemini.

Install: pip install google-generativeai

Import google.generativeai as genai.
Use model: "gemini-2.0-flash-exp"
Configure with: genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

Create a SYSTEM_PROMPT constant:

"""
You are a data analyst for an SAP Order-to-Cash (O2C) business process.
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
- sales_order_headers.sold_to_party → customers.business_partner
- sales_order_items.sales_order → sales_order_headers.sales_order
- sales_order_items.material → products.product
- delivery_items.reference_sd_document → sales_order_headers.sales_order (delivery item references sales order)
- delivery_items.delivery_document → delivery_headers.delivery_document
- delivery_items.plant → plants.plant
- billing_items.reference_sd_document → delivery_headers.delivery_document (billing item references delivery)
- billing_items.billing_document → billing_headers.billing_document
- journal_entries.reference_document → billing_headers.billing_document
- payments.accounting_document → journal_entries.accounting_document

GUARDRAILS — IMPORTANT:
- You ONLY answer questions about this O2C dataset and SAP business processes.
- If the user asks about anything unrelated (general knowledge, coding, personal questions, 
  creative writing, current events, etc.), respond ONLY with:
  {"type": "off_topic", "message": "This system is designed to answer questions about the Order-to-Cash dataset only. Please ask about sales orders, deliveries, billing, payments, customers, or products."}
- Never make up data. Always query the database.
- For tracing flows, use JOINs across all relevant tables.

RESPONSE FORMAT — always respond with valid JSON only, no markdown:
For data queries: {"type": "sql_query", "sql": "SELECT ...", "explanation": "brief what this does"}
For off-topic: {"type": "off_topic", "message": "..."}
For clarification needed: {"type": "clarification", "message": "..."}
"""

Build these functions:

1. classify_and_generate_sql(user_query: str) -> dict
   - Call Gemini with SYSTEM_PROMPT + user_query
   - Parse the JSON response
   - Return the dict

2. execute_sql(sql: str, db_conn) -> list[dict]
   - Execute the SQL safely (read-only, SELECT only)
   - Return results as list of row dicts
   - Limit to 100 rows max
   - Raise ValueError if SQL contains INSERT/UPDATE/DELETE/DROP

3. format_answer(user_query: str, sql: str, results: list, db_conn) -> str
   - Call Gemini with: given this query "{user_query}", this SQL "{sql}", and these results: {json.dumps(results[:20])}, write a clear, concise natural language answer. Be specific with numbers. Max 3 sentences.
   - Return the answer string

4. answer_query(user_query: str, db_conn) -> dict
   Main function that:
   - Calls classify_and_generate_sql
   - If off_topic or clarification: return {"answer": message, "sql": None, "results": None, "node_ids": []}
   - If sql_query: execute the SQL, format the answer
   - Also extract relevant node IDs for graph highlighting:
     Look for billing_document, sales_order, delivery_document, accounting_document values in results
     Map them to graph node IDs: bill_X, so_X, del_X, journal_X
   - Return {"answer": str, "sql": str, "results": list, "node_ids": list[str]}
```

---

### PROMPT 6 — FastAPI Backend

```
In backend/main.py, create the FastAPI application.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

Import: init_db, get_db from database
Import: build_graph, graph_to_json from graph_builder
Import: answer_query from query_engine

app = FastAPI(title="SAP O2C Graph API")

Add CORS middleware allowing origins: ["http://localhost:5173", "http://localhost:3000"]

On startup (lifespan or @app.on_event("startup")):
  - Call init_db()
  - Build the graph once and cache it as a module-level variable GRAPH_DATA
  - GRAPH_DATA = graph_to_json(build_graph())
  - Print "Graph built: X nodes, Y edges"

Endpoints:

GET /api/graph
  Returns GRAPH_DATA (cached, no rebuild per request)

GET /api/graph/node/{node_id}
  Returns full attributes of a single node from the graph
  Look up node_id in GRAPH_DATA["nodes"]

GET /api/stats
  Returns summary stats:
  - total_customers: COUNT from customers
  - total_sales_orders: COUNT from sales_order_headers  
  - total_deliveries: COUNT from delivery_headers
  - total_billing_docs: COUNT from billing_headers
  - total_payments: COUNT from payments
  - total_products: COUNT from products

class ChatRequest(BaseModel):
    message: str

POST /api/chat
  Body: ChatRequest
  - Get db connection
  - Call answer_query(request.message, db)
  - Return: {"answer": str, "sql": str|None, "results": list|None, "node_ids": list[str]}
  - Handle exceptions: return 500 with error message

GET /health
  Returns {"status": "ok", "graph_nodes": len(GRAPH_DATA["nodes"]), "graph_edges": len(GRAPH_DATA["links"])}
```

---

### PROMPT 7 — Frontend API Client

```
In frontend/src/api.ts, create typed API functions:

const BASE_URL = "http://localhost:8000/api"

Types:
  GraphNode { id: string, type: string, label: string, [key: string]: any }
  GraphLink { source: string, target: string, relation: string }
  GraphData { nodes: GraphNode[], links: GraphLink[], stats: object }
  ChatResponse { answer: string, sql: string | null, results: any[] | null, node_ids: string[] }
  StatsData { total_customers: number, total_sales_orders: number, total_deliveries: number, total_billing_docs: number, total_payments: number, total_products: number }

Functions:
  fetchGraph(): Promise<GraphData>
  fetchNode(nodeId: string): Promise<GraphNode>
  sendChat(message: string): Promise<ChatResponse>
  fetchStats(): Promise<StatsData>

Use standard fetch with error handling.
```

---

### PROMPT 8 — Graph Canvas Component

```
In frontend/src/components/GraphCanvas.tsx, build the graph visualization.

Use react-force-graph-2d.

Props:
  graphData: { nodes: any[], links: any[] }
  highlightedNodes: Set<string>  (node IDs to highlight from chat)
  onNodeClick: (node: any) => void

Node color by type (use these exact colors):
  Customer: "#FF6B6B"      (coral red)
  SalesOrder: "#4ECDC4"    (teal)
  Delivery: "#45B7D1"      (sky blue)
  BillingDocument: "#96CEB4" (sage green)
  JournalEntry: "#FFEAA7"  (pale yellow)
  Payment: "#DDA0DD"       (plum)
  Product: "#98D8C8"       (mint)
  Plant: "#F7DC6F"         (golden)
  default: "#BDC3C7"       (gray)

Node radius: 4 base, 8 if highlighted, 6 if it has many connections (degree > 5)

Highlighted nodes should glow: draw a larger circle behind with 40% opacity same color

On node click: call onNodeClick

Canvas config:
  - backgroundColor: "#0F1117"  (dark background like screenshots)
  - linkColor: rgba(100,160,255,0.3)
  - linkWidth: 1
  - d3VelocityDecay: 0.4
  - cooldownTicks: 100
  - width: fill container (use useRef + ResizeObserver)
  - height: fill container

Add a legend in the top-left corner (absolute positioned div) showing each node type with its color dot.

Export the component as default.
```

---

### PROMPT 9 — Chat Panel Component

```
In frontend/src/components/ChatPanel.tsx, build the chat interface.

Props:
  onHighlightNodes: (nodeIds: string[]) => void

State:
  messages: Array<{role: "user"|"assistant", content: string, sql?: string, results?: any[]}>
  input: string
  loading: boolean

UI layout (right panel, fixed width 380px):
  - Header: "Chat with Graph" title + "Order to Cash" subtitle
  - Message list (scrollable, flex-grow)
  - Input area at bottom: text input + Send button

Message display:
  - User messages: right-aligned, dark background bubble
  - Assistant messages: left-aligned, slightly lighter background
  - Show SQL as a collapsible code block (gray background, monospace font) below assistant message
  - Show result count as small text: "X rows returned"

On send:
  - Add user message to messages
  - Set loading=true
  - Call sendChat(input)
  - Add assistant message with answer
  - If node_ids exist, call onHighlightNodes(node_ids)
  - Set loading=false

Suggested queries (show as clickable chips above input when messages is empty):
  - "Which products have the most billing documents?"
  - "Trace billing document 91150187"
  - "Find sales orders delivered but not billed"
  - "Show top 5 customers by revenue"
  - "Which deliveries are pending goods movement?"

Loading state: show animated "..." dots in an assistant bubble

Style: dark theme matching the graph canvas (#0F1117 background, white text)
Use CSS modules or inline styles — no external CSS framework needed.

Export as default.
```

---

### PROMPT 10 — Main App Component

```
In frontend/src/App.tsx, build the main layout.

Import GraphCanvas, ChatPanel, fetchGraph, fetchStats.

State:
  graphData: GraphData | null
  highlightedNodes: Set<string> = new Set()
  selectedNode: any | null
  stats: StatsData | null
  loading: boolean

On mount:
  - fetchGraph() → setGraphData
  - fetchStats() → setStats

Layout (full viewport, dark theme #0F1117):
  Header bar (48px height):
    Left: "⬡" icon + "O2C Graph" title (white)
    Center: stats chips (customers count, SO count, billing docs count) in small pill badges
    Right: "Powered by Gemini" badge

  Main area (flex row, fills remaining height):
    Left: GraphCanvas (flex: 1, no chat panel width)
      - Show loading spinner while graphData is null
      - highlightedNodes from state
      - onNodeClick → setSelectedNode

    Right: ChatPanel (width: 380px, border-left)
      - onHighlightNodes: (ids) => setHighlightedNodes(new Set(ids))

  Node detail popup (absolute, bottom-left of graph area):
    Show when selectedNode is not null
    Display: entity type badge, label, key attributes (skip nulls/empty)
    Close button (×)
    Style: white background, rounded corners, subtle shadow, max-width 280px

In index.css:
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0F1117; color: white; font-family: 'Inter', system-ui; }
  ::-webkit-scrollbar { width: 4px; background: transparent; }
  ::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

Export default App.
```

---

### PROMPT 11 — Environment & Run Setup

```
Create a .env file in backend/:
  GEMINI_API_KEY=your_key_here

Create backend/run.sh:
  #!/bin/bash
  cd backend
  python ingest.py
  uvicorn main:app --reload --port 8000

Create a root README.md:

# SAP O2C Graph System

## Setup

### Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # Add your Gemini API key
python ingest.py      # One-time ingestion (~30 seconds)
uvicorn main:app --reload --port 8000

### Frontend  
cd frontend
npm install
npm run dev

Open http://localhost:5173

## Architecture
[describe stack decisions here]

Also update frontend/vite.config.ts to add:
  server: { proxy: { '/api': 'http://localhost:8000' } }
  (so you can also use /api in frontend without CORS issues)
```

---

### PROMPT 12 — Bonus: Node Highlighting on Graph

```
In GraphCanvas.tsx, add this enhancement:

When highlightedNodes changes, use forceRef.current to:
1. Zoom/pan the graph to center on the first highlighted node
2. Use setTimeout to call forceRef.current.centerAt(x, y, 1000) and forceRef.current.zoom(3, 1000)

Find the node by id in graphData.nodes to get its x, y position.

Also add a "Reset View" button (top-right of canvas) that:
- Clears highlighted nodes (call a prop: onClearHighlight)
- Resets zoom to default: forceRef.current.zoomToFit(400)
```

---

### PROMPT 13 — Deployment to Vercel + Railway

```
For deployment:

Backend (Railway):
1. Create Procfile in backend/:
   web: uvicorn main:app --host 0.0.0.0 --port $PORT

2. Update main.py CORS to also allow the Vercel domain

3. Update graph_builder.py to include the full dataset path via env var:
   DATA_PATH = os.getenv("DATA_PATH", "../../dataset/sap-o2c-data")

4. Add a startup script that runs ingest.py if the DB doesn't exist yet

Frontend (Vercel):
1. Update frontend/src/api.ts to use:
   const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api"

2. Add frontend/.env.production:
   VITE_API_URL=https://your-railway-app.railway.app/api

3. vercel.json in frontend/:
   { "rewrites": [{ "source": "/(.*)", "destination": "/" }] }
```

---

## Key Design Decisions for README

**Why SQLite over a graph database (Neo4j)?**
SQLite is zero-setup, portable, and the dataset is small enough (~50K rows). Complex graph traversals are handled in Python with NetworkX after loading from SQLite. This avoids Cypher query complexity while keeping the analytical power of graph algorithms.

**Why NetworkX for graph construction?**
The graph is built once at server startup and cached in memory. NetworkX enables rich algorithms (centrality, path finding, connected components) that would require complex Cypher in Neo4j. For a dataset of this scale, in-memory is fast enough.

**Why Gemini Flash for LLM?**
Free tier with 15 RPM and 1M TPM is sufficient for demo purposes. The structured JSON response format (type + sql/message) makes it robust against hallucination — if Gemini doesn't return valid JSON, the system catches it and returns an error rather than a fabricated answer.

**Guardrails strategy:**
Two layers:
1. LLM-level: System prompt explicitly instructs the model to return `{"type": "off_topic"}` for non-dataset queries
2. Code-level: SQL executor only allows SELECT statements; any mutation attempt throws an error

---

## Example Queries to Demo

1. `Which products are associated with the highest number of billing documents?`
2. `Trace the full flow of billing document 91150187`
3. `Which sales orders were delivered but never billed?`
4. `Show me the top 5 customers by total revenue`
5. `How many payments have been cleared in April 2025?`
6. `Which plants handle the most deliveries?`
7. `Find all billing documents that were cancelled`

---

## Gemini API Key

Get a free key at: https://aistudio.google.com/app/apikey
No credit card required. 15 requests/minute free.