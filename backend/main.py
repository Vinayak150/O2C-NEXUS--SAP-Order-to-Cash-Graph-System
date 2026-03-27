import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables at the absolute start
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, get_db
from graph_builder import build_graph, graph_to_json
from query_engine import answer_query

GRAPH_DATA: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global GRAPH_DATA
    init_db()
    G = build_graph()
    GRAPH_DATA = graph_to_json(G)
    
    # Check if API Key is loaded successfully for the logs
    api_key = os.getenv("GROQ_API_KEY")
    key_status = "LOADED" if api_key else "MISSING"

    print(f"--- System Startup ---")
    print(f"Graph built: {len(GRAPH_DATA['nodes'])} nodes, {len(GRAPH_DATA['links'])} edges")
    print(f"Groq API Key: {key_status}")
    print(f"-----------------------")
    yield

app = FastAPI(title="SAP O2C Graph API", lifespan=lifespan)

# CORS setup is perfect. allow_credentials MUST be False when allow_origins is ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FIXED: Added a Root Route so you don't get {"detail":"Not Found"} anymore!
@app.get("/")
def read_root():
    return {"status": "System Online", "message": "Backend is running perfectly!"}

# FIXED: Added double-routes to catch requests with or without "/api"
@app.get("/graph")
@app.get("/api/graph")
def get_graph():
    return GRAPH_DATA

@app.get("/graph/node/{node_id}")
@app.get("/api/graph/node/{node_id}")
def get_node(node_id: str):
    for node in GRAPH_DATA.get("nodes", []):
        if node["id"] == node_id:
            return node
    raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

@app.get("/stats")
@app.get("/api/stats")
def get_stats():
    conn = get_db()
    # Ensure rows are returned as dictionaries
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    cursor = conn.cursor()

    queries = {
        "total_customers":    "SELECT COUNT(*) AS count FROM business_partners",
        "total_sales_orders": "SELECT COUNT(*) AS count FROM sales_order_headers",
        "total_deliveries":   "SELECT COUNT(*) AS count FROM outbound_delivery_headers",
        "total_billing_docs": "SELECT COUNT(*) AS count FROM billing_document_headers",
        "total_payments":     "SELECT COUNT(*) AS count FROM payments_accounts_receivable",
        "total_products":     "SELECT COUNT(*) AS count FROM products",
    }

    results = {}
    for key, sql in queries.items():
        cursor.execute(sql)
        results[key] = cursor.fetchone()["count"]

    conn.close()
    return results

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict[str, str]]] = []

@app.post("/chat")
@app.post("/api/chat")
def chat(request: ChatRequest):
    try:
        conn = get_db()
        result = answer_query(request.message, conn, request.chat_history or [])
        conn.close()
        return result
    except Exception as e:
        print(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "graph_nodes": len(GRAPH_DATA.get("nodes", [])),
        "graph_edges": len(GRAPH_DATA.get("links", [])),
    }