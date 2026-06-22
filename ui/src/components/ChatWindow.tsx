import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, MemoryOp } from "../types";

interface Props {
  messages: Message[];
  onSend: (text: string) => void;
  busy: boolean;
}

const OP_COLORS: Record<string, string> = {
  ADD:       "#4ade80",
  REINFORCE: "#60a5fa",
  SUPERSEDE: "#f59e0b",
  NOOP:      "#475569",
};

function MemoryOps({ ops }: { ops: MemoryOp[] }) {
  const salient = ops.filter((o) => o.op_type !== "NOOP");
  if (salient.length === 0) return null;
  return (
    <div style={styles.opsBlock}>
      {salient.map((op, i) => (
        <div key={i} style={styles.opRow}>
          <span style={{ ...styles.opTag, color: OP_COLORS[op.op_type] }}>
            {op.op_type}
          </span>
          {op.category && <span style={styles.opCat}>{op.category}</span>}
          {op.text && <span style={styles.opText}>{op.text}</span>}
          {!op.text && op.target_item_id && (
            <span style={styles.opTarget}>→ {op.target_item_id.slice(0, 8)}…</span>
          )}
        </div>
      ))}
    </div>
  );
}

function Cursor() {
  return <span style={styles.cursor}>▋</span>;
}

export default function ChatWindow({ messages, onSend, busy }: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = () => {
    const trimmed = input.trim();
    if (!trimmed || busy) return;
    setInput("");
    onSend(trimmed);
  };

  return (
    <div style={styles.window}>
      <div style={styles.messageList}>
        {messages.length === 0 && (
          <div style={styles.placeholder}>
            Ask a question or describe an alarm to get started.
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              ...styles.messageBubble,
              ...(msg.role === "user" ? styles.userBubble : styles.assistantBubble),
            }}
          >
            <span style={styles.roleLabel}>
              {msg.role === "user" ? "You" : "Assistant"}
            </span>

            {msg.role === "assistant" && msg.ops && msg.ops.length > 0 && (
              <MemoryOps ops={msg.ops} />
            )}

            {msg.role === "user" ? (
              <p style={styles.userText}>{msg.text}</p>
            ) : (
              <div className="md-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.text || (msg.streaming ? "" : "…")}
                </ReactMarkdown>
                {msg.streaming && <Cursor />}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div style={styles.inputBar}>
        <input
          style={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
          placeholder="Describe an alarm, ask a question…"
          disabled={busy}
        />
        <button style={styles.button} onClick={submit} disabled={busy || !input.trim()}>
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  window: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  messageList: {
    flex: 1,
    overflowY: "auto",
    padding: "20px 24px",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  placeholder: {
    color: "#475569",
    fontSize: 13,
    textAlign: "center",
    marginTop: 60,
  },
  messageBubble: {
    maxWidth: 720,
    borderRadius: 10,
    padding: "12px 16px",
  },
  userBubble: {
    alignSelf: "flex-end",
    background: "#1e3a5f",
    borderBottomRightRadius: 2,
  },
  assistantBubble: {
    alignSelf: "flex-start",
    background: "#1a2030",
    borderBottomLeftRadius: 2,
    width: "100%",
    maxWidth: 760,
  },
  roleLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: "#64748b",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    display: "block",
    marginBottom: 6,
  },
  userText: {
    margin: 0,
    fontSize: 14,
    lineHeight: 1.65,
    color: "#e2e8f0",
  },
  cursor: {
    display: "inline-block",
    animation: "blink 1s step-end infinite",
    color: "#60a5fa",
    marginLeft: 1,
  },
  opsBlock: {
    marginBottom: 10,
    borderLeft: "2px solid #1e2535",
    paddingLeft: 10,
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  opRow: {
    display: "flex",
    alignItems: "baseline",
    gap: 6,
    fontSize: 11,
    flexWrap: "wrap",
  },
  opTag: {
    fontWeight: 700,
    fontFamily: "monospace",
    letterSpacing: "0.04em",
  },
  opCat: {
    color: "#64748b",
    fontFamily: "monospace",
  },
  opText: {
    color: "#94a3b8",
    fontStyle: "italic",
  },
  opTarget: {
    color: "#64748b",
    fontFamily: "monospace",
  },
  inputBar: {
    display: "flex",
    gap: 10,
    padding: "14px 20px",
    borderTop: "1px solid #1e2535",
    background: "#131820",
  },
  input: {
    flex: 1,
    background: "#1a2030",
    border: "1px solid #1e2535",
    borderRadius: 8,
    padding: "10px 14px",
    color: "#e2e8f0",
    fontSize: 14,
    outline: "none",
  },
  button: {
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    padding: "10px 20px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
};
