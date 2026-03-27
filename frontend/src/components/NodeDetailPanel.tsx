import { useRef, useEffect, useState } from "react";

const TYPE_COLORS: Record<string, string> = {
  Customer: "#FF6B6B",
  SalesOrder: "#4ECDC4",
  Delivery: "#45B7D1",
  BillingDocument: "#96CEB4",
  JournalEntry: "#FFEAA7",
  Payment: "#DDA0DD",
  Product: "#98D8C8",
  Plant: "#F7DC6F",
};

// D3 internal keys injected by ForceGraph2D — never show these
const INTERNAL_KEYS = new Set([
  "x", "y", "vx", "vy", "fx", "fy",
  "index", "__indexColor", "__threeObj", "__lineColor",
]);

// Human-readable label overrides for known keys
const KEY_LABELS: Record<string, string> = {
  id: "Node ID",
  type: "Entity",
  label: "Label",
  amount: "Amount",
  currency: "Currency",
  creation_date: "Creation Date",
  delivery_status: "Delivery Status",
  goods_movement_status: "Goods Movement Status",
  is_cancelled: "Is Cancelled",
  billing_document_type: "Billing Doc Type",
  clearing_date: "Clearing Date",
  product_type: "Product Type",
  plant_code: "Plant Code",
  city: "City",
  country: "Country",
};

interface NodeDetailPanelProps {
  node: any;
  connections: number;
  screenX: number;
  screenY: number;
  pinned: boolean;
  onClose: () => void;
}

export default function NodeDetailPanel({
  node,
  connections,
  screenX,
  screenY,
  pinned,
  onClose,
}: NodeDetailPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [panelSize, setPanelSize] = useState({ w: 300, h: 400 });
  const typeColor = TYPE_COLORS[node.type as string] ?? "#BDC3C7";

  useEffect(() => {
    if (panelRef.current) {
      setPanelSize({
        w: panelRef.current.offsetWidth,
        h: panelRef.current.offsetHeight,
      });
    }
  });

  // Smart viewport-aware positioning — stays near node, never clips off screen
  const vw = typeof window !== "undefined" ? window.innerWidth : 1280;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const PANEL_W = 296;
  const OFFSET = 18;

  let left = screenX + OFFSET;
  let top = screenY - 12;

  if (left + PANEL_W > vw - 16) {
    left = screenX - PANEL_W - OFFSET;
  }
  if (left < 8) left = 8;
  if (top + panelSize.h > vh - 16) {
    top = vh - panelSize.h - 16;
  }
  if (top < 8) top = 8;

  // Build attribute rows — show every non-internal key, show blank as "—"
  const topRows: [string, any][] = [
    ["Entity", node.type],
    ["Label", node.label],
    ["Node ID", node.id],
  ];

  const dataRows = Object.entries(node).filter(([k]) => {
    if (INTERNAL_KEYS.has(k)) return false;
    if (k === "type" || k === "label" || k === "id") return false;
    return true;
  });

  const formatValue = (v: any): { text: string; empty: boolean } => {
    if (v === null || v === undefined || v === "") return { text: "—", empty: true };
    if (typeof v === "boolean") return { text: v ? "Yes" : "No", empty: false };
    return { text: String(v), empty: false };
  };

  const humanKey = (k: string) =>
    KEY_LABELS[k] ?? k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div
      ref={panelRef}
      style={{
        position: "fixed",
        left,
        top,
        width: PANEL_W,
        background: "#ffffff",
        borderRadius: 10,
        boxShadow: "0 4px 24px rgba(0,0,0,0.18), 0 1px 4px rgba(0,0,0,0.10)",
        zIndex: 100,
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize: 13,
        overflow: "hidden",
        border: "1px solid #e5e7eb",
        pointerEvents: pinned ? "auto" : "none",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 14px 10px",
          borderBottom: "1px solid #f0f0f0",
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <div>
          <span
            style={{
              display: "inline-block",
              background: typeColor,
              color: "#111",
              borderRadius: 4,
              padding: "2px 8px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.04em",
              marginBottom: 4,
            }}
          >
            {node.type}
          </span>
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: "#111",
              lineHeight: 1.3,
              wordBreak: "break-all",
            }}
          >
            {node.label}
          </div>
        </div>

        {pinned && (
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: "none",
              border: "none",
              fontSize: 18,
              cursor: "pointer",
              color: "#9ca3af",
              lineHeight: 1,
              padding: 0,
              flexShrink: 0,
            }}
          >
            ×
          </button>
        )}
      </div>

      {/* Attribute rows */}
      <div
        style={{
          maxHeight: 340,
          overflowY: "auto",
          padding: "6px 0",
        }}
      >
        {/* Fixed top rows: Entity, Label, Node ID */}
        {topRows.map(([k, v]) => {
          const { text, empty } = formatValue(v);
          return (
            <div
              key={k}
              style={{
                display: "flex",
                padding: "3px 14px",
                gap: 8,
                alignItems: "baseline",
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color: "#6b7280",
                  minWidth: 130,
                  flexShrink: 0,
                  lineHeight: 1.6,
                }}
              >
                {k}:
              </span>
              <span
                style={{
                  fontSize: 12,
                  color: empty ? "#d1d5db" : "#111827",
                  lineHeight: 1.6,
                  wordBreak: "break-all",
                  fontWeight: k === "Node ID" ? 400 : 500,
                }}
              >
                {text}
              </span>
            </div>
          );
        })}

        {/* Separator */}
        {dataRows.length > 0 && (
          <div style={{ borderTop: "1px solid #f3f4f6", margin: "4px 0" }} />
        )}

        {/* All remaining data attributes */}
        {dataRows.map(([k, v]) => {
          const { text, empty } = formatValue(v);
          return (
            <div
              key={k}
              style={{
                display: "flex",
                padding: "3px 14px",
                gap: 8,
                alignItems: "baseline",
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color: "#6b7280",
                  minWidth: 130,
                  flexShrink: 0,
                  lineHeight: 1.6,
                }}
              >
                {humanKey(k)}:
              </span>
              <span
                style={{
                  fontSize: 12,
                  color: empty ? "#d1d5db" : "#111827",
                  lineHeight: 1.6,
                  wordBreak: "break-all",
                }}
              >
                {text}
              </span>
            </div>
          );
        })}
      </div>

      {/* Footer — connection count */}
      <div
        style={{
          borderTop: "1px solid #f0f0f0",
          padding: "7px 14px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span style={{ fontSize: 11, color: "#6b7280" }}>
          Connections:{" "}
          <strong style={{ color: "#111", fontWeight: 700 }}>{connections}</strong>
        </span>
        {!pinned && (
          <span style={{ fontSize: 10, color: "#9ca3af", fontStyle: "italic" }}>
            Click node to pin
          </span>
        )}
      </div>
    </div>
  );
}
