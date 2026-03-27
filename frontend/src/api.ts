const BASE_URL: string =
  (import.meta.env.VITE_API_URL as string) || "http://localhost:8000/api";

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  [key: string]: any;
}

export interface GraphLink {
  source: string;
  target: string;
  relation: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  stats: object;
}

export interface ChatHistoryItem {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  answer: string;
  sql: string | null;
  results: any[] | null;
  node_ids: string[];
}

export interface StatsData {
  total_customers: number;
  total_sales_orders: number;
  total_deliveries: number;
  total_billing_docs: number;
  total_payments: number;
  total_products: number;
}

export async function fetchGraph(): Promise<GraphData> {
  const response = await fetch(`${BASE_URL}/graph`);
  if (!response.ok) {
    throw new Error(`Failed to fetch graph: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchNode(nodeId: string): Promise<GraphNode> {
  const response = await fetch(`${BASE_URL}/graph/node/${encodeURIComponent(nodeId)}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch node '${nodeId}': ${response.statusText}`);
  }
  return response.json();
}

export async function sendChat(
  message: string,
  chatHistory: ChatHistoryItem[] = []
): Promise<ChatResponse> {
  const response = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, chat_history: chatHistory }),
  });
  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchStats(): Promise<StatsData> {
  const response = await fetch(`${BASE_URL}/stats`);
  if (!response.ok) {
    throw new Error(`Failed to fetch stats: ${response.statusText}`);
  }
  return response.json();
}
