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

const SKIP_KEYS = new Set([
  "id",
  "x",
  "y",
  "vx",
  "vy",
  "fx",
  "fy",
  "index",
  "__indexColor",
  "__threeObj",
]);

interface NodeDetailPanelProps {
  node: any;
  onClose: () => void;
}

export default function NodeDetailPanel({
  node,
  onClose,
}: NodeDetailPanelProps) {
  const typeColor = TYPE_COLORS[node.type as string] ?? "#BDC3C7";

  const entries = Object.entries(node).filter(([k, v]) => {
    if (SKIP_KEYS.has(k)) return false;
    if (k === "type" || k === "label") return false;
    if (v === null || v === undefined || v === "") return false;
    return true;
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 20,
        left: 20,
        background: "#fff",
        borderRadius: 12,
        boxShadow: "0 8px 32px rgba(0,0,0,0.55)",
        maxWidth: 280,
        width: "calc(100% - 40px)",
        padding: "14px 16px",
        zIndex: 10,
        color: "#111",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: 10,
          gap: 8,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              display: "inline-block",
              background: typeColor,
              color: "#111",
              borderRadius: 20,
              padding: "2px 10px",
              fontSize: 10,
              fontWeight: 700,
              marginBottom: 5,
              letterSpacing: "0.03em",
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
              wordBreak: "break-word",
            }}
          >
            {node.label}
          </div>
        </div>

        <button
          onClick={onClose}
          aria-label="Close"
          style={{
            background: "none",
            border: "none",
            fontSize: 20,
            cursor: "pointer",
            color: "#aaa",
            lineHeight: 1,
            padding: "0 0 0 6px",
            flexShrink: 0,
            marginTop: -2,
          }}
        >
          ×
        </button>
      </div>

      {/* Attributes */}
      {entries.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 5,
            borderTop: "1px solid #f0f0f0",
            paddingTop: 10,
          }}
        >
          {entries.map(([k, v]) => (
            <div
              key={k}
              style={{ display: "flex", gap: 8, alignItems: "flex-start" }}
            >
              <span
                style={{
                  fontSize: 11,
                  color: "#888",
                  minWidth: 90,
                  flexShrink: 0,
                  textTransform: "capitalize",
                  lineHeight: 1.5,
                }}
              >
                {k.replace(/_/g, " ")}
              </span>
              <span
                style={{
                  fontSize: 12,
                  color: "#222",
                  wordBreak: "break-word",
                  lineHeight: 1.5,
                }}
              >
                {String(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
