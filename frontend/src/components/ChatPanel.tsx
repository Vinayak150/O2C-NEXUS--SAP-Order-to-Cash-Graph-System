import { useState, useRef, useEffect } from "react";
import { sendChat } from "../api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sql?: string | null;
  results?: any[] | null;
}

interface ChatPanelProps {
  onHighlightNodes: (nodeIds: string[]) => void;
}

const SUGGESTED_QUERIES = [
  "Which products have the most billing documents?",
  "Trace billing document 91150187",
  "Find sales orders delivered but not billed",
  "Show top 5 customers by revenue",
  "Which deliveries are pending goods movement?",
];

function DotsLoader() {
  return (
    <>
      <style>{`
        @keyframes dotBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.35; }
          40%            { transform: translateY(-5px); opacity: 1; }
        }
        .o2c-dot {
          display: inline-block;
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #7ab3e8;
          margin: 0 2px;
          animation: dotBounce 1.2s ease-in-out infinite;
        }
        .o2c-dot:nth-child(2) { animation-delay: 0.15s; }
        .o2c-dot:nth-child(3) { animation-delay: 0.30s; }
      `}</style>
      <span className="o2c-dot" />
      <span className="o2c-dot" />
      <span className="o2c-dot" />
    </>
  );
}

export default function ChatPanel({ onHighlightNodes }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedSql, setExpandedSql] = useState<Set<number>>(new Set());
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSend = async (query?: string) => {
    const text = (query ?? input).trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);
    try {
      const res = await sendChat(text);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          sql: res.sql,
          results: res.results,
        },
      ]);
      if (res.node_ids && res.node_ids.length > 0) {
        onHighlightNodes(res.node_ids);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "An error occurred. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleSql = (idx: number) => {
    setExpandedSql((prev) => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  };

  return (
    <div
      style={{
        width: 380,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        background: "#13151f",
        borderLeft: "1px solid #1e1e2e",
        height: "100%",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px 20px 12px",
          borderBottom: "1px solid #1e1e2e",
          flexShrink: 0,
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 700, color: "#fff" }}>
          Chat with Graph
        </div>
        <div style={{ fontSize: 12, color: "#555", marginTop: 2 }}>
          Order to Cash
        </div>
      </div>

      {/* Message list */}
      <div
        ref={listRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px 16px 8px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              color: "#444",
              fontSize: 13,
              textAlign: "center",
              marginTop: 32,
            }}
          >
            Ask anything about your O2C data.
          </div>
        )}

        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={idx}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: isUser ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "88%",
                  padding: "9px 13px",
                  borderRadius: isUser
                    ? "14px 14px 4px 14px"
                    : "14px 14px 14px 4px",
                  background: isUser ? "#1e3a5f" : "#1e1e2e",
                  color: "#f0f0f0",
                  fontSize: 13,
                  lineHeight: 1.55,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {msg.content}
              </div>

              {!isUser && msg.sql && (
                <div style={{ maxWidth: "88%", marginTop: 5 }}>
                  <button
                    onClick={() => toggleSql(idx)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#4a8ac4",
                      fontSize: 11,
                      cursor: "pointer",
                      padding: "2px 0",
                    }}
                  >
                    {expandedSql.has(idx) ? "▲ Hide SQL" : "▼ Show SQL"}
                  </button>
                  {expandedSql.has(idx) && (
                    <pre
                      style={{
                        background: "#0e0e18",
                        border: "1px solid #2a2a3a",
                        borderRadius: 6,
                        padding: "8px 10px",
                        fontSize: 11,
                        color: "#7ab8ff",
                        overflowX: "auto",
                        marginTop: 4,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                        fontFamily: "monospace",
                      }}
                    >
                      {msg.sql}
                    </pre>
                  )}
                  {msg.results != null && (
                    <div
                      style={{ fontSize: 11, color: "#555", marginTop: 4 }}
                    >
                      {msg.results.length} row
                      {msg.results.length !== 1 ? "s" : ""} returned
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {/* Animated loading bubble */}
        {loading && (
          <div style={{ display: "flex", alignItems: "flex-start" }}>
            <div
              style={{
                background: "#1e1e2e",
                borderRadius: "14px 14px 14px 4px",
                padding: "12px 16px",
                display: "flex",
                alignItems: "center",
                gap: 2,
                minHeight: 40,
              }}
            >
              <DotsLoader />
            </div>
          </div>
        )}
      </div>

      {/* Suggested query chips — visible only when no messages */}
      {messages.length === 0 && (
        <div
          style={{
            padding: "0 16px 12px",
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
          }}
        >
          {SUGGESTED_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => handleSend(q)}
              style={{
                background: "#1a1a2e",
                border: "1px solid #2a2a3a",
                color: "#999",
                borderRadius: 20,
                padding: "5px 11px",
                fontSize: 11,
                cursor: "pointer",
                lineHeight: 1.4,
                textAlign: "left",
              }}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <div
        style={{
          padding: "12px 16px 16px",
          borderTop: "1px solid #1e1e2e",
          display: "flex",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Ask about sales orders, billing…"
          disabled={loading}
          style={{
            flex: 1,
            background: "#0f111a",
            border: "1px solid #2a2a3a",
            borderRadius: 8,
            color: "#f0f0f0",
            padding: "9px 12px",
            fontSize: 13,
            outline: "none",
            fontFamily: "inherit",
          }}
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          style={{
            background: loading || !input.trim() ? "#181826" : "#1e3a5f",
            border: "1px solid",
            borderColor: loading || !input.trim() ? "#2a2a3a" : "#2a4a7f",
            color: loading || !input.trim() ? "#444" : "#7ab3e8",
            borderRadius: 8,
            padding: "9px 16px",
            cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            fontSize: 13,
            fontWeight: 600,
            transition: "all 0.15s",
            flexShrink: 0,
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
