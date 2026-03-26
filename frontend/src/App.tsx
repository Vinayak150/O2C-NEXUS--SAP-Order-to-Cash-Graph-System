import { useState, useEffect } from "react";
import GraphCanvas from "./components/GraphCanvas";
import ChatPanel from "./components/ChatPanel";
import NodeDetailPanel from "./components/NodeDetailPanel";
import { fetchGraph, fetchStats } from "./api";
import type { GraphData, StatsData } from "./api";

function StatChip({ label, value }: { label: string; value: number }) {
  return (
    <div
      style={{
        background: "#1a1a2e",
        border: "1px solid #2a2a3a",
        borderRadius: 20,
        padding: "3px 10px",
        fontSize: 11,
        color: "#aaa",
        display: "flex",
        gap: 5,
        alignItems: "center",
      }}
    >
      <span style={{ color: "#fff", fontWeight: 700 }}>
        {value?.toLocaleString()}
      </span>
      <span>{label}</span>
    </div>
  );
}

function Spinner() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        flexDirection: "column",
        gap: 16,
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          border: "3px solid #222",
          borderTopColor: "#4ECDC4",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }}
      />
      <span style={{ color: "#555", fontSize: 14 }}>Building graph…</span>
    </div>
  );
}

export default function App() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [highlightedNodes, setHighlightedNodes] = useState<Set<string>>(
    new Set()
  );
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchGraph(), fetchStats()])
      .then(([graph, s]) => {
        setGraphData(graph);
        setStats(s);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleHighlightNodes = (ids: string[]) => {
    setHighlightedNodes(new Set(ids));
  };

  const handleClearHighlight = () => {
    setHighlightedNodes(new Set());
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "#0F1117",
        color: "#fff",
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        overflow: "hidden",
      }}
    >
      {/* Header bar — 48px */}
      <div
        style={{
          height: 48,
          display: "flex",
          alignItems: "center",
          padding: "0 20px",
          borderBottom: "1px solid #1a1a2e",
          background: "#0c0e16",
          gap: 16,
          flexShrink: 0,
        }}
      >
        {/* Left: icon + title */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 20, lineHeight: 1 }}>⬡</span>
          <span
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: "#fff",
              letterSpacing: "0.02em",
            }}
          >
            O2C Graph
          </span>
        </div>

        {/* Center: stats chips */}
        <div
          style={{
            flex: 1,
            display: "flex",
            justifyContent: "center",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          {stats && (
            <>
              <StatChip label="Customers" value={stats.total_customers} />
              <StatChip
                label="Sales Orders"
                value={stats.total_sales_orders}
              />
              <StatChip
                label="Billing Docs"
                value={stats.total_billing_docs}
              />
              <StatChip label="Payments" value={stats.total_payments} />
              <StatChip label="Products" value={stats.total_products} />
            </>
          )}
        </div>

        {/* Right: Gemini badge */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "#1a1a2e",
            border: "1px solid #2a2a4a",
            borderRadius: 20,
            padding: "4px 12px",
            fontSize: 11,
            color: "#7ab3e8",
            flexShrink: 0,
          }}
        >
          
          <span>Powered by Vinayak</span>
        </div>
      </div>

      {/* Main content area — fills remaining height */}
      <div
        style={{
          flex: 1,
          display: "flex",
          overflow: "hidden",
        }}
      >
        {/* Graph area */}
        <div
          style={{
            flex: 1,
            position: "relative",
            overflow: "hidden",
          }}
        >
          {loading || !graphData ? (
            <Spinner />
          ) : (
            <GraphCanvas
              graphData={graphData}
              highlightedNodes={highlightedNodes}
              onNodeClick={(node) => setSelectedNode(node)}
              onClearHighlight={handleClearHighlight}
            />
          )}

          {/* Node detail popup — absolute bottom-left of graph area */}
          {selectedNode && (
            <NodeDetailPanel
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
            />
          )}
        </div>

        {/* Chat panel — right side */}
        <ChatPanel onHighlightNodes={handleHighlightNodes} />
      </div>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
