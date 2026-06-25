import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, MemoryOp, Signal } from "../types";

interface Props {
  messages: Message[];
  onSendUser: (text: string) => void;
  onSendSimulated: () => void;
  onCloseSession: (outcome: "resolved_independently" | "escalated") => void;
  activeAlarm: boolean;
  busy: boolean;
}

const OP_COLORS: Record<string, string> = {
  ADD: "#4ade80", REINFORCE: "#60a5fa", SUPERSEDE: "#f59e0b", NOOP: "#475569",
};

function LearnedAnnotation({ signals, ops }: { signals?: Signal[]; ops?: MemoryOp[] }) {
  const [open, setOpen] = useState(false);
  const salientOps = (ops ?? []).filter((o) => o.op_type !== "NOOP");
  if (!signals?.length && !salientOps.length) return null;

  return (
    <div style={s.annotation}>
      <button style={s.annoToggle} onClick={() => setOpen((o) => !o)}>
        {open ? "▼" : "▶"} what was learned
      </button>
      {open && (
        <div style={s.annoBody}>
          {signals && signals.length > 0 && (
            <>
              <p style={s.annoLabel}>SIGNALS</p>
              {signals.map((sig, i) => (
                <div key={i} style={s.annoRow}>
                  <span style={s.annoCat}>{sig.category}</span>
                  <span style={s.annoVal}>{sig.value}</span>
                  <span style={s.annoObs}>{sig.observation}</span>
                </div>
              ))}
            </>
          )}
          {salientOps.length > 0 && (
            <>
              <p style={s.annoLabel}>MEMORY OPS</p>
              {salientOps.map((op, i) => (
                <div key={i} style={s.annoRow}>
                  <span style={{ ...s.annoOp, color: OP_COLORS[op.op_type] }}>{op.op_type}</span>
                  {op.category && <span style={s.annoCat}>{op.category}</span>}
                  {op.text && <span style={s.annoObs}>{op.text}</span>}
                  {!op.text && op.target_item_id && (
                    <span style={s.annoObs}>→ {op.target_item_id.slice(0, 8)}…</span>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function ConversationPanel({ messages, onSendUser, onSendSimulated, onCloseSession, activeAlarm, busy }: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = () => {
    const t = input.trim();
    if (!t || busy) return;
    setInput("");
    onSendUser(t);
  };

  return (
    <div style={s.panel}>
      <div style={s.messages}>
        {messages.length === 0 && (
          <p style={s.empty}>Type a message or click "Next Interaction" to begin.</p>
        )}
        {messages.map((msg) => msg.role === "system" ? (
          <div key={msg.id} style={s.systemBanner}>⚠ {msg.text}</div>
        ) : (
          <div key={msg.id} style={{ ...s.bubble, ...(msg.role === "user" ? s.userBubble : s.asstBubble) }}>
            <span style={s.roleLabel}>{msg.role === "user" ? "Operator" : "Assistant"}</span>
            {msg.role === "assistant" ? (
              <>
                <LearnedAnnotation signals={msg.signals} ops={msg.ops} />
                {msg.loading ? (
                  <p style={s.loading}>Thinking…</p>
                ) : (
                  <div className="md-body">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                  </div>
                )}
              </>
            ) : (
              <p style={s.userText}>{msg.text}</p>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div style={s.inputBar}>
        <input
          style={s.input}
          value={input}
          placeholder="Type an operator message…"
          disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
        />
        <button style={s.sendBtn} onClick={submit} disabled={busy || !input.trim()}>
          Send
        </button>
        <button style={s.simBtn} onClick={onSendSimulated} disabled={busy}>
          Next Interaction
        </button>
        <button
          style={s.resolveBtn}
          onClick={() => onCloseSession("resolved_independently")}
          disabled={busy || !activeAlarm}
        >
          Mark Resolved
        </button>
        <button
          style={s.escalateBtn}
          onClick={() => onCloseSession("escalated")}
          disabled={busy || !activeAlarm}
        >
          Escalate
        </button>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  panel: { display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" },
  messages: { flex: 1, overflowY: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: 14 },
  empty: { color: "#475569", fontSize: 13, textAlign: "center", marginTop: 60 },
  bubble: { maxWidth: 760, borderRadius: 10, padding: "12px 16px" },
  userBubble: { alignSelf: "flex-end", background: "#1e3a5f", borderBottomRightRadius: 2 },
  asstBubble: { alignSelf: "flex-start", background: "#1a2030", borderBottomLeftRadius: 2, width: "100%" },
  roleLabel: { fontSize: 11, fontWeight: 600, color: "#64748b", letterSpacing: "0.06em", textTransform: "uppercase" as const, display: "block", marginBottom: 6 },
  userText: { margin: 0, fontSize: 14, lineHeight: 1.65, color: "#e2e8f0" },
  loading: { margin: 0, fontSize: 14, color: "#475569", fontStyle: "italic" },
  annotation: { marginBottom: 8 },
  annoToggle: { background: "none", border: "none", color: "#475569", fontSize: 11, cursor: "pointer", padding: "2px 0", fontFamily: "monospace" },
  annoBody: { marginTop: 6, borderLeft: "2px solid #1e2535", paddingLeft: 10 },
  annoLabel: { margin: "6px 0 3px", fontSize: 10, fontWeight: 700, color: "#475569", letterSpacing: "0.08em" },
  annoRow: { display: "flex", gap: 6, fontSize: 11, flexWrap: "wrap" as const, alignItems: "baseline", marginBottom: 2 },
  annoOp: { fontWeight: 700, fontFamily: "monospace" },
  annoCat: { color: "#64748b", fontFamily: "monospace" },
  annoVal: { color: "#60a5fa", fontFamily: "monospace" },
  annoObs: { color: "#94a3b8", fontStyle: "italic" },
  inputBar: { display: "flex", gap: 8, padding: "14px 20px", borderTop: "1px solid #1e2535", background: "#131820" },
  input: { flex: 1, background: "#1a2030", border: "1px solid #1e2535", borderRadius: 8, padding: "10px 14px", color: "#e2e8f0", fontSize: 14, outline: "none" },
  sendBtn: { background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, padding: "10px 18px", fontSize: 14, fontWeight: 600, cursor: "pointer" },
  simBtn: { background: "#1e2535", color: "#94a3b8", border: "1px solid #334155", borderRadius: 8, padding: "10px 14px", fontSize: 13, fontWeight: 500, cursor: "pointer" },
  resolveBtn: { background: "transparent", color: "#4ade80", border: "1px solid #16653f", borderRadius: 8, padding: "10px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer" },
  escalateBtn: { background: "transparent", color: "#f87171", border: "1px solid #7f1d1d", borderRadius: 8, padding: "10px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer" },
  systemBanner: { alignSelf: "center", fontSize: 12, color: "#fbbf24", background: "#251c08", border: "1px solid #5c4716", borderRadius: 8, padding: "8px 16px", fontFamily: "monospace" },
};
