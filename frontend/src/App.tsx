import { useState, useEffect, useCallback } from "react";
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
  // Click-to-pin state — persists until the user closes the panel
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [selectedPos, setSelectedPos] = useState({ x: 0, y: 0 });

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

  // Degree count for NodeDetailPanel "Connections" footer
  const getDegree = useCallback(
    (nodeId: string): number => {
      if (!graphData) return 0;
      return graphData.links.filter((l: any) => {
        const src = typeof l.source === "object" ? l.source?.id : l.source;
        const tgt = typeof l.target === "object" ? l.target?.id : l.target;
        return src === nodeId || tgt === nodeId;
      }).length;
    },
    [graphData]
  );

  // GraphCanvas forwards mousePos alongside the node on every click
  const handleNodeClick = useCallback(
    (node: any, screenX: number, screenY: number) => {
      if (selectedNode?.id === node.id) {
        setSelectedNode(null); // second click on same node unpins
      } else {
        setSelectedNode(node);
        setSelectedPos({ x: screenX, y: screenY });
      }
    },
    [selectedNode]
  );

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
              <StatChip label="Sales Orders" value={stats.total_sales_orders} />
              <StatChip label="Billing Docs" value={stats.total_billing_docs} />
              <StatChip label="Payments" value={stats.total_payments} />
              <StatChip label="Products" value={stats.total_products} />
            </>
          )}
        </div>

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
          
          <span>Created by Vinayak</span>
        </div>
      </div>

      {/* Main content area */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Graph area */}
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          {loading || !graphData ? (
            <Spinner />
          ) : (
            <GraphCanvas
              graphData={graphData}
              highlightedNodes={highlightedNodes}
              onNodeClick={handleNodeClick}
              onClearHighlight={handleClearHighlight}
            />
          )}

          {/* NodeDetailPanel — click-to-pin only, always pinned=true */}
          {selectedNode && (
            <NodeDetailPanel
              node={selectedNode}
              connections={getDegree(selectedNode.id)}
              screenX={selectedPos.x}
              screenY={selectedPos.y}
              pinned={true}
              onClose={() => setSelectedNode(null)}
            />
          )}
        </div>

        {/* Chat panel */}
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
