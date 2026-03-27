import { useRef, useEffect, useCallback, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

interface GraphCanvasProps {
  graphData: { nodes: any[]; links: any[] };
  highlightedNodes: Set<string>;
  /** Receives node + the current mouse viewport coords for NodeDetailPanel positioning */
  onNodeClick: (node: any, screenX: number, screenY: number) => void;
  onClearHighlight: () => void;
}

const NODE_COLORS: Record<string, string> = {
  Customer: "#FF6B6B",
  SalesOrder: "#4ECDC4",
  Delivery: "#45B7D1",
  BillingDocument: "#96CEB4",
  JournalEntry: "#FFEAA7",
  Payment: "#DDA0DD",
  Product: "#98D8C8",
  Plant: "#F7DC6F",
  default: "#BDC3C7",
};

const LEGEND_ENTRIES = Object.entries(NODE_COLORS).filter(
  ([k]) => k !== "default"
);

/**
 * Keys injected by the ForceGraph2D physics engine — never meaningful to the
 * user, and must be excluded from the tooltip data table.
 */
const TOOLTIP_IGNORED_KEYS = new Set([
  "id", "x", "y", "vx", "vy", "fx", "fy",
  "index", "color", "val", "type", "label", "group",
]);

export default function GraphCanvas({
  graphData,
  highlightedNodes,
  onNodeClick,
  onClearHighlight,
}: GraphCanvasProps) {
  const forceRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // ── Hover tooltip state ──────────────────────────────────────────────────
  const [hoverNode, setHoverNode] = useState<any>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // ── Container resize observer ────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width, height });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // ── Zoom/pan to first highlighted node (chat response) ───────────────────
  useEffect(() => {
    if (highlightedNodes.size === 0 || !forceRef.current) return;
    const firstId = Array.from(highlightedNodes)[0];
    const node = graphData.nodes.find((n: any) => n.id === firstId);
    if (node && node.x !== undefined && node.y !== undefined) {
      setTimeout(() => {
        forceRef.current.centerAt(node.x, node.y, 1000);
        forceRef.current.zoom(3, 1000);
      }, 300);
    }
  }, [highlightedNodes, graphData.nodes]);

  // ── Canvas node painter ──────────────────────────────────────────────────
  const getColor = useCallback(
    (node: any): string =>
      NODE_COLORS[node.type as string] ?? NODE_COLORS.default,
    []
  );

  const getRadius = useCallback(
    (node: any): number => {
      // Use the server-computed degree-centrality size when available.
      // calculated_val = 2.0 + (degree * 0.5), injected by graph_builder.py.
      // Clamp between 2 and 12 so no node becomes unreadably large.
      const base: number =
        typeof node.calculated_val === "number"
          ? Math.min(Math.max(node.calculated_val, 2), 12)
          : 4; // fallback for stale payloads without the attribute

      // Highlighted nodes get a visible boost on top of their natural size.
      if (highlightedNodes.has(node.id)) return Math.max(base + 2, 8);
      return base;
    },
    [highlightedNodes]
  );

  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D) => {
      const color = getColor(node);
      const r = getRadius(node);
      const isHighlighted = highlightedNodes.has(node.id);

      if (isHighlighted) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r * 2.5, 0, 2 * Math.PI);
        ctx.fillStyle = color + "66"; // 40% opacity glow
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
    },
    [getColor, getRadius, highlightedNodes]
  );

  // ── Reset View ───────────────────────────────────────────────────────────
  const handleResetView = useCallback(() => {
    onClearHighlight();
    if (forceRef.current) {
      forceRef.current.zoomToFit(400);
    }
  }, [onClearHighlight]);

  // ── Tooltip data rows (filter out physics / meta keys) ───────────────────
  const tooltipEntries = hoverNode
    ? Object.entries(hoverNode).filter(([key]) => !TOOLTIP_IGNORED_KEYS.has(key))
    : [];

  return (
    <div
      ref={containerRef}
      onMouseMove={(e) => {
        setMousePos({ x: e.clientX, y: e.clientY });
      }}
      style={{
        position: "relative",
        flex: 1,
        width: "100%",
        height: "100%",
        overflow: "hidden",
        background: "#0F1117",
      }}
    >
      <ForceGraph2D
        ref={forceRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="#0F1117"
        linkColor={() => "rgba(100,160,255,0.3)"}
        linkWidth={1}
        d3VelocityDecay={0.4}
        cooldownTicks={100}
        nodeCanvasObject={paintNode}
        nodeCanvasObjectMode={() => "replace"}
        onNodeClick={(node) => onNodeClick(node, mousePos.x, mousePos.y)}
        onNodeHover={(node) => setHoverNode(node)}
      />

      {/* ── Floating hover tooltip ─────────────────────────────────────── */}
      {hoverNode && (
        <div
          style={{
            position: "fixed",
            left: mousePos.x + 15,
            top: mousePos.y + 15,
            zIndex: 1000,
            backgroundColor: "rgba(30, 41, 59, 0.95)",
            color: "white",
            padding: "12px",
            borderRadius: "8px",
            boxShadow: "0 4px 6px rgba(0,0,0,0.3)",
            pointerEvents: "none",
            fontSize: "12px",
            maxHeight: "400px",
            overflowY: "auto",
            minWidth: "200px",
            maxWidth: "320px",
          }}
        >
          {/* Header */}
          <h3
            style={{
              margin: "0 0 8px 0",
              fontSize: "13px",
              fontWeight: 700,
              color: NODE_COLORS[hoverNode.type as string] ?? "#fff",
              borderBottom: "1px solid rgba(255,255,255,0.12)",
              paddingBottom: "6px",
              wordBreak: "break-all",
            }}
          >
            {hoverNode.label ?? hoverNode.id}
          </h3>

          {/* Entity type badge */}
          <div style={{ marginBottom: "8px" }}>
            <span
              style={{
                display: "inline-block",
                background: "rgba(255,255,255,0.1)",
                borderRadius: "4px",
                padding: "1px 7px",
                fontSize: "10px",
                letterSpacing: "0.06em",
                fontWeight: 600,
                textTransform: "uppercase",
              }}
            >
              {hoverNode.type}
            </span>
          </div>

          {/* Data rows */}
          {tooltipEntries.map(([key, value]) => (
            <div
              key={key}
              style={{
                marginBottom: "3px",
                lineHeight: 1.55,
                display: "flex",
                gap: "6px",
                flexWrap: "wrap",
              }}
            >
              <strong style={{ color: "#94a3b8", flexShrink: 0 }}>
                {key}:
              </strong>
              <span style={{ color: "#e2e8f0", wordBreak: "break-all" }}>
                {String(value ?? "—")}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Legend — top-left ─────────────────────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          top: 12,
          left: 12,
          background: "rgba(15,17,23,0.88)",
          border: "1px solid #2a2a3a",
          borderRadius: 8,
          padding: "10px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 6,
          pointerEvents: "none",
          zIndex: 2,
        }}
      >
        {LEGEND_ENTRIES.map(([type, color]) => (
          <div
            key={type}
            style={{ display: "flex", alignItems: "center", gap: 8 }}
          >
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: color,
                flexShrink: 0,
              }}
            />
            <span style={{ fontSize: 11, color: "#ccc", whiteSpace: "nowrap" }}>
              {type}
            </span>
          </div>
        ))}
      </div>

      {/* ── Reset View — top-right ────────────────────────────────────────── */}
      <button
        onClick={handleResetView}
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          background: "rgba(255,255,255,0.08)",
          border: "1px solid #444",
          color: "#fff",
          borderRadius: 6,
          padding: "6px 14px",
          cursor: "pointer",
          fontSize: 12,
          letterSpacing: "0.02em",
          zIndex: 2,
        }}
      >
        Reset View
      </button>
    </div>
  );
}
