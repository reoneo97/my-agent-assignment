import { useState, useCallback } from "react";
import ChatWindow from "./components/ChatWindow";
import ProfilePanel from "./components/ProfilePanel";
import { streamChat } from "./api";
import type { Message, MemoryItemSummary, MemoryOp } from "./types";

const OPERATOR_ID = "op-demo-01";

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [profile, setProfile] = useState<MemoryItemSummary[]>([]);
  const [busy, setBusy] = useState(false);

  const send = useCallback(async (text: string) => {
    if (busy || !text.trim()) return;
    setBusy(true);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text,
    };

    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      text: "",
      ops: [],
      streaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    const controller = new AbortController();

    try {
      for await (const event of streamChat(text, OPERATOR_ID, controller.signal)) {
        if (event.type === "ops") {
          const ops: MemoryOp[] = event.ops;
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, ops } : m))
          );
        } else if (event.type === "profile") {
          setProfile(event.items);
        } else if (event.type === "chunk") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, text: m.text + event.text } : m
            )
          );
        } else if (event.type === "done" || event.type === "error") {
          const errText = event.type === "error" ? `\n\n[Error: ${event.message}]` : "";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, text: m.text + errText, streaming: false }
                : m
            )
          );
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, text: "[Connection error]", streaming: false }
              : m
          )
        );
      }
    } finally {
      setBusy(false);
    }
  }, [busy]);

  return (
    <div style={styles.root}>
      <header style={styles.header}>
        <span style={styles.headerTitle}>Operator Learning Assistant</span>
        <span style={styles.headerSub}>operator: {OPERATOR_ID}</span>
      </header>
      <div style={styles.body}>
        <ProfilePanel items={profile} />
        <ChatWindow messages={messages} onSend={send} busy={busy} />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    fontFamily: "'Inter', system-ui, sans-serif",
    background: "#0f1117",
    color: "#e2e8f0",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "12px 20px",
    borderBottom: "1px solid #1e2535",
    background: "#131820",
  },
  headerTitle: {
    fontWeight: 600,
    fontSize: 15,
    letterSpacing: "0.01em",
  },
  headerSub: {
    fontSize: 12,
    color: "#64748b",
    marginLeft: "auto",
  },
  body: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },
};
