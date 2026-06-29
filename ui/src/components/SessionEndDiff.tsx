import { useEffect, useRef } from "react";
import type { ShiftEndResponse } from "../types";
import { tierBadge } from "../theme";

type Outcome = "resolved_independently" | "escalated";

interface Props {
  result: ShiftEndResponse;
  outcome: Outcome;
  alarmCode?: string;
  onDismiss: () => void;
}

const OUTCOME_META: Record<Outcome, { label: string; color: string; bg: string; border: string }> = {
  resolved_independently: { label: "Resolved independently", color: "#4ade80", bg: "#0f2417", border: "#1c5235" },
  escalated: { label: "Escalated", color: "#fbbf24", bg: "#2a2009", border: "#78521b" },
};

export default function SessionEndDiff({ result, outcome, alarmCode, onDismiss }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

  // Close on Escape and move focus to the dismiss control when the modal opens.
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDismiss]);

  const meta = OUTCOME_META[outcome];
  const noUpdates = result.no_significant_updates;

  return (
    <div style={s.overlay} onClick={onDismiss}>
      <div
        style={s.modal}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-diff-title"
      >
        <div style={s.header}>
          <span id="session-diff-title" style={s.title}>Alarm Resolution</span>
          <button ref={closeRef} style={s.close} onClick={onDismiss} aria-label="Close alarm resolution summary">✕</button>
        </div>

        {/* Outcome banner — what just happened on the shopfloor */}
        <div style={{ ...s.outcomeBanner, background: meta.bg, border: `1px solid ${meta.border}` }}>
          {alarmCode && <span style={s.alarmCode}>{alarmCode}</span>}
          <span style={{ ...s.outcomeLabel, color: meta.color }}>{meta.label}</span>
          <span style={s.sessionNote}>session closed</span>
        </div>

        {/* What the assistant learned from this session */}
        <p style={s.learnedLabel}>What we learned this session</p>

        {noUpdates ? (
          <p style={s.noUpdates}>No new behavioural signals from this session.</p>
        ) : (
          <>
            {result.changes.new_items.length > 0 && (
              <section style={s.section}>
                <p style={s.sectionLabel}>New Signals</p>
                {result.changes.new_items.map((item) => (
                  <div key={item.id} style={s.row}>
                    <span style={{ ...s.tier, ...tierColor(item.status) }}>{item.status}</span>
                    <span style={s.itemText}>{item.text}</span>
                  </div>
                ))}
              </section>
            )}

            {result.changes.tier_transitions.length > 0 && (
              <section style={s.section}>
                <p style={s.sectionLabel}>Confidence Changes</p>
                {result.changes.tier_transitions.map((t, i) => (
                  <div key={i} style={s.row}>
                    <span style={s.itemId}>{t.item_id.slice(0, 8)}…</span>
                    <span style={{ ...s.tier, ...tierColor(t.from_status) }}>{t.from_status}</span>
                    <span style={s.arrow}>→</span>
                    <span style={{ ...s.tier, ...tierColor(t.to_status) }}>{t.to_status}</span>
                  </div>
                ))}
              </section>
            )}

            {result.changes.superseded.length > 0 && (
              <section style={s.section}>
                <p style={s.sectionLabel}>Superseded</p>
                {result.changes.superseded.map((sup, i) => (
                  <div key={i} style={s.row}>
                    <span style={s.itemId}>{sup.item_id.slice(0, 8)}…</span>
                    <span style={s.arrow}>superseded</span>
                  </div>
                ))}
              </section>
            )}
          </>
        )}

        <p style={s.footnote}>Shift synopsis is regenerated at End Shift.</p>

        <button style={s.dismissBtn} onClick={onDismiss}>Dismiss</button>
      </div>
    </div>
  );
}

function tierColor(status: string): React.CSSProperties {
  const { bg, color } = tierBadge(status);
  return { background: bg, color };
}

const s: Record<string, React.CSSProperties> = {
  overlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100, animation: "fadeInUp 0.18s ease both" },
  modal: { background: "#131820", border: "1px solid #1e2535", borderRadius: 12, padding: 24, width: 520, maxWidth: "90vw", maxHeight: "80vh", overflowY: "auto", boxShadow: "0 24px 60px rgba(0,0,0,0.5)" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  title: { fontSize: 15, fontWeight: 600, color: "#e2e8f0" },
  close: { background: "none", border: "none", color: "#64748b", fontSize: 16, cursor: "pointer" },
  outcomeBanner: { display: "flex", alignItems: "center", gap: 10, borderRadius: 8, padding: "10px 14px", marginBottom: 20 },
  alarmCode: { fontFamily: "monospace", fontSize: 12, fontWeight: 700, color: "#e2e8f0" },
  outcomeLabel: { fontSize: 13, fontWeight: 600 },
  sessionNote: { marginLeft: "auto", fontSize: 11, color: "#64748b" },
  learnedLabel: { fontSize: 10, fontWeight: 700, color: "#475569", letterSpacing: "0.08em", textTransform: "uppercase" as const, marginBottom: 12 },
  noUpdates: { color: "#64748b", fontSize: 13, textAlign: "center", padding: "16px 0" },
  section: { marginBottom: 18 },
  sectionLabel: { fontSize: 10, fontWeight: 700, color: "#475569", letterSpacing: "0.08em", textTransform: "uppercase" as const, marginBottom: 8 },
  row: { display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 6, flexWrap: "wrap" as const },
  itemId: { fontFamily: "monospace", color: "#475569", fontSize: 11 },
  tier: { fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 4 },
  arrow: { color: "#475569", fontSize: 11 },
  itemText: { color: "#cbd5e1", flex: 1 },
  footnote: { fontSize: 11, color: "#475569", fontStyle: "italic", margin: "4px 0 12px" },
  dismissBtn: { marginTop: 4, width: "100%", background: "#1e2535", border: "none", borderRadius: 8, color: "#94a3b8", padding: "10px", fontSize: 13, cursor: "pointer" },
};
