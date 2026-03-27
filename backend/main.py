import os
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
    api_key = os.getenv("GOOGLE_API_KEY")
    key_status = "LOADED" if api_key else "MISSING"
    
    print(f"--- System Startup ---")
    print(f"Graph built: {len(GRAPH_DATA['nodes'])} nodes, {len(GRAPH_DATA['links'])} edges")
    print(f"Gemini API Key: {key_status}")
    print(f"-----------------------")
    yield

app = FastAPI(title="SAP O2C Graph API", lifespan=lifespan)

# CORS — add your Vercel URL to ALLOWED_ORIGINS env var (comma-separated)
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
)
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/graph")
def get_graph():
    return GRAPH_DATA

@app.get("/api/graph/node/{node_id}")
def get_node(node_id: str):
    for node in GRAPH_DATA.get("nodes", []):
        if node["id"] == node_id:
            return node
    raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

@app.get("/api/stats")
def get_stats():
    conn = get_db()
    # Ensure rows are returned as dictionaries
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    cursor = conn.cursor()

    queries = {
        "total_customers": "SELECT COUNT(*) AS count FROM customers",
        "total_sales_orders": "SELECT COUNT(*) AS count FROM sales_order_headers",
        "total_deliveries": "SELECT COUNT(*) AS count FROM delivery_headers",
        "total_billing_docs": "SELECT COUNT(*) AS count FROM billing_headers",
        "total_payments": "SELECT COUNT(*) AS count FROM payments",
        "total_products": "SELECT COUNT(*) AS count FROM products",
    }

    results = {}
    for key, sql in queries.items():
        cursor.execute(sql)
        results[key] = cursor.fetchone()["count"]

    conn.close()
    return results

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
def chat(request: ChatRequest):
    try:
        conn = get_db()
        # Pass context to engine
        result = answer_query(request.message, conn)
        conn.close()
        return result
    except Exception as e:
        print(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {
        "status": "ok",
        "graph_nodes": len(GRAPH_DATA.get("nodes", [])),
        "graph_edges": len(GRAPH_DATA.get("links", [])),
    }