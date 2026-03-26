import { useRef, useEffect, useCallback, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

interface GraphCanvasProps {
  graphData: { nodes: any[]; links: any[] };
  highlightedNodes: Set<string>;
  onNodeClick: (node: any) => void;
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

export default function GraphCanvas({
  graphData,
  highlightedNodes,
  onNodeClick,
  onClearHighlight,
}: GraphCanvasProps) {
  const forceRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

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

  // PROMPT 12 — zoom/pan to first highlighted node
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

  const getColor = useCallback(
    (node: any): string =>
      NODE_COLORS[node.type as string] ?? NODE_COLORS.default,
    []
  );

  const getRadius = useCallback(
    (node: any): number => {
      if (highlightedNodes.has(node.id)) return 8;
      const degree = graphData.links.filter((l: any) => {
        const src = typeof l.source === "object" ? l.source?.id : l.source;
        const tgt = typeof l.target === "object" ? l.target?.id : l.target;
        return src === node.id || tgt === node.id;
      }).length;
      return degree > 5 ? 6 : 4;
    },
    [highlightedNodes, graphData.links]
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

  // PROMPT 12 — Reset View button
  const handleResetView = useCallback(() => {
    onClearHighlight();
    if (forceRef.current) {
      forceRef.current.zoomToFit(400);
    }
  }, [onClearHighlight]);

  return (
    <div
      ref={containerRef}
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
        onNodeClick={onNodeClick}
        nodeLabel={(node: any) => node.label ?? node.id}
      />

      {/* Legend — absolute top-left */}
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
            <span
              style={{ fontSize: 11, color: "#ccc", whiteSpace: "nowrap" }}
            >
              {type}
            </span>
          </div>
        ))}
      </div>

      {/* Reset View — absolute top-right */}
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
