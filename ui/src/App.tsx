import { useState, useCallback, useEffect } from "react";
import ConversationPanel from "./components/ConversationPanel";
import ProfilePanel from "./components/ProfilePanel";
import SynopsisPanel from "./components/SynopsisPanel";
import ShiftEndDiff from "./components/ShiftEndDiff";
import {
  sendUserMessage,
  sendSimulated,
  endShift,
  fetchOperators,
  fetchSynopsis,
  resetOperator,
  mockAlarm,
  closeSession,
} from "./api";
import type {
  Message,
  ProfileItem,
  Synopsis,
  Operator,
  ShiftEndResponse,
  Alarm,
} from "./types";

export default function App() {
  const [operators, setOperators] = useState<Operator[]>([]);
  const [operatorId, setOperatorId] = useState("op-demo-01");
  const [messages, setMessages] = useState<Message[]>([]);
  const [profileItems, setProfileItems] = useState<ProfileItem[]>([]);
  const [synopsis, setSynopsis] = useState<Synopsis | null>(null);
  const [busy, setBusy] = useState(false);
  const [shiftBusy, setShiftBusy] = useState(false);
  const [shiftDiff, setShiftDiff] = useState<ShiftEndResponse | null>(null);
  const [resetBusy, setResetBusy] = useState(false);
  const [activeAlarm, setActiveAlarm] = useState<Alarm | null>(null);
  const [alarmBusy, setAlarmBusy] = useState(false);

  useEffect(() => {
    fetchOperators().then(({ operators: ops }) => setOperators(ops)).catch(() => {});
    fetchSynopsis(operatorId).then(setSynopsis).catch(() => {});
  }, [operatorId]);

  const handleInteractionResponse = useCallback((res: Awaited<ReturnType<typeof sendUserMessage>>) => {
    const asstMsg: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      text: res.assistant_reply,
      signals: res.signals_extracted,
      ops: res.memory_operations,
    };
    setMessages((prev) => [...prev, asstMsg]);
    setProfileItems(res.profile.items);
  }, []);

  const handleSendUser = useCallback(async (text: string) => {
    if (busy) return;
    setBusy(true);
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", text };
    const placeholder: Message = { id: crypto.randomUUID(), role: "assistant", text: "", loading: true };
    setMessages((prev) => [...prev, userMsg, placeholder]);
    try {
      const res = await sendUserMessage(operatorId, text);
      setMessages((prev) => prev.filter((m) => m.id !== placeholder.id));
      handleInteractionResponse(res);
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) => m.id === placeholder.id ? { ...m, text: `[Error: ${e}]`, loading: false } : m)
      );
    } finally {
      setBusy(false);
    }
  }, [busy, operatorId, handleInteractionResponse]);

  const handleSendSimulated = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    const placeholder: Message = { id: crypto.randomUUID(), role: "assistant", text: "", loading: true };
    setMessages((prev) => [...prev, placeholder]);
    try {
      const res = await sendSimulated(operatorId);
      // Show simulated operator turn first, then assistant reply
      const simMsg: Message = { id: crypto.randomUUID(), role: "user", text: res.interaction.operator_message };
      setMessages((prev) => prev.filter((m) => m.id !== placeholder.id).concat(simMsg));
      handleInteractionResponse(res);
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) => m.id === placeholder.id ? { ...m, text: `[Error: ${e}]`, loading: false } : m)
      );
    } finally {
      setBusy(false);
    }
  }, [busy, operatorId, handleInteractionResponse]);

  const handleMockAlarm = useCallback(async () => {
    if (alarmBusy || busy) return;
    setAlarmBusy(true);
    try {
      const res = await mockAlarm(operatorId);
      setActiveAlarm(res.alarm);
      const sysMsg: Message = { id: crypto.randomUUID(), role: "system", text: res.system_message };
      setMessages((prev) => [...prev, sysMsg]);
      if (res.proactive_reply) {
        const asstMsg: Message = { id: crypto.randomUUID(), role: "assistant", text: res.proactive_reply };
        setMessages((prev) => [...prev, asstMsg]);
      }
    } finally {
      setAlarmBusy(false);
    }
  }, [alarmBusy, busy, operatorId]);

  const handleCloseSession = useCallback(async (outcome: "resolved_independently" | "escalated") => {
    if (busy) return;
    setBusy(true);
    const placeholder: Message = { id: crypto.randomUUID(), role: "assistant", text: "", loading: true };
    setMessages((prev) => [...prev, placeholder]);
    try {
      const res = await closeSession(operatorId, outcome);
      setMessages((prev) => prev.filter((m) => m.id !== placeholder.id));
      handleInteractionResponse(res);
      setActiveAlarm(null);
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) => m.id === placeholder.id ? { ...m, text: `[Error: ${e}]`, loading: false } : m)
      );
    } finally {
      setBusy(false);
    }
  }, [busy, operatorId, handleInteractionResponse]);

  const handleEndShift = useCallback(async () => {
    if (shiftBusy) return;
    setShiftBusy(true);
    try {
      const res = await endShift(operatorId);
      setShiftDiff(res);
      setProfileItems(res.profile_after.items);
      setSynopsis({ text: res.synopsis_after, generated_at: new Date().toISOString(), version: (synopsis?.version ?? 0) + 1 });
    } finally {
      setShiftBusy(false);
    }
  }, [shiftBusy, operatorId, synopsis]);

  const handleReset = useCallback(async () => {
    if (resetBusy || !confirm(`Reset all learned state for ${operatorId}?`)) return;
    setResetBusy(true);
    try {
      await resetOperator(operatorId);
      setMessages([]);
      setProfileItems([]);
      setSynopsis(null);
      setActiveAlarm(null);
    } finally {
      setResetBusy(false);
    }
  }, [resetBusy, operatorId]);

  const handleOperatorChange = (id: string) => {
    setOperatorId(id);
    setMessages([]);
    setProfileItems([]);
    setSynopsis(null);
    setActiveAlarm(null);
  };

  return (
    <div style={s.root}>
      <header style={s.header}>
        <span style={s.title}>Operator Learning Assistant</span>

        <select
          style={s.picker}
          value={operatorId}
          onChange={(e) => handleOperatorChange(e.target.value)}
        >
          {operators.length === 0 && <option value={operatorId}>{operatorId}</option>}
          {operators.map((op) => (
            <option key={op.id} value={op.id}>{op.name} — {op.machine_type}</option>
          ))}
        </select>

        {activeAlarm && (
          <span style={s.alarmBadge}>
            Active: {activeAlarm.code} ({activeAlarm.expected_disposition ?? "?"})
          </span>
        )}

        <div style={s.controls}>
          <button style={s.alarmBtn} onClick={handleMockAlarm} disabled={alarmBusy || busy}>
            {alarmBusy ? "Triggering…" : "Mock Alarm"}
          </button>
          <button style={s.resetBtn} onClick={handleReset} disabled={resetBusy}>
            {resetBusy ? "Resetting…" : "Reset"}
          </button>
          <button style={s.endShiftBtn} onClick={handleEndShift} disabled={shiftBusy}>
            {shiftBusy ? "Consolidating…" : "End Shift"}
          </button>
        </div>
      </header>

      <div style={s.body}>
        {/* Left: conversation */}
        <ConversationPanel
          messages={messages}
          onSendUser={handleSendUser}
          onSendSimulated={handleSendSimulated}
          onCloseSession={handleCloseSession}
          activeAlarm={!!activeAlarm}
          busy={busy}
        />

        {/* Right: profile + synopsis stacked */}
        <div style={s.rightSidebar}>
          <ProfilePanel items={profileItems} />
          <SynopsisPanel synopsis={synopsis} />
        </div>
      </div>

      {shiftDiff && (
        <ShiftEndDiff result={shiftDiff} onDismiss={() => setShiftDiff(null)} />
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  root: { display: "flex", flexDirection: "column", height: "100vh", fontFamily: "'Inter', system-ui, sans-serif", background: "#0f1117", color: "#e2e8f0" },
  header: { display: "flex", alignItems: "center", gap: 12, padding: "10px 20px", borderBottom: "1px solid #1e2535", background: "#131820", flexShrink: 0 },
  title: { fontWeight: 600, fontSize: 15, letterSpacing: "0.01em", marginRight: 4 },
  picker: { background: "#1a2030", border: "1px solid #1e2535", borderRadius: 6, color: "#e2e8f0", fontSize: 13, padding: "5px 10px", cursor: "pointer" },
  controls: { marginLeft: "auto", display: "flex", gap: 8 },
  alarmBadge: { fontSize: 11, fontWeight: 600, color: "#fbbf24", background: "#3a2e0f", border: "1px solid #78521b", borderRadius: 6, padding: "4px 10px", marginLeft: 12 },
  alarmBtn: { padding: "6px 12px", fontSize: 12, fontWeight: 600, border: "1px solid #f59e0b", borderRadius: 6, background: "transparent", color: "#fbbf24", cursor: "pointer" },
  resetBtn: { padding: "6px 12px", fontSize: 12, border: "1px solid #334155", borderRadius: 6, background: "transparent", color: "#64748b", cursor: "pointer" },
  endShiftBtn: { padding: "6px 14px", fontSize: 12, fontWeight: 600, border: "1px solid #2563eb", borderRadius: 6, background: "transparent", color: "#60a5fa", cursor: "pointer" },
  body: { display: "flex", flex: 1, overflow: "hidden" },
  rightSidebar: { display: "flex", flexDirection: "column", width: 260, minWidth: 220, borderLeft: "1px solid #1e2535", overflowY: "auto" },
};
