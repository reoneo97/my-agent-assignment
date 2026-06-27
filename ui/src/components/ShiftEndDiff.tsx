import { useEffect, useRef } from "react";
import type { ShiftEndResponse } from "../types";
import { tierBadge } from "../theme";

interface Props {
  result: ShiftEndResponse;
  onDismiss: () => void;
}

export default function ShiftEndDiff({ result, onDismiss }: Props) {
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

  return (
    <div style={s.overlay} onClick={onDismiss}>
      <div
        style={s.modal}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shift-diff-title"
      >
        <div style={s.header}>
          <span id="shift-diff-title" style={s.title}>End of Shift — Consolidation</span>
          <button ref={closeRef} style={s.close} onClick={onDismiss} aria-label="Close consolidation summary">✕</button>
        </div>

        {result.no_significant_updates ? (
          <p style={s.noUpdates}>No significant updates this shift.</p>
        ) : (
          <>
            {result.changes.tier_transitions.length > 0 && (
              <section style={s.section}>
                <p style={s.sectionLabel}>Tier Transitions</p>
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

            {result.changes.new_items.length > 0 && (
              <section style={s.section}>
                <p style={s.sectionLabel}>New Items</p>
                {result.changes.new_items.map((item) => (
                  <div key={item.id} style={s.row}>
                    <span style={{ ...s.tier, ...tierColor(item.status) }}>{item.status}</span>
                    <span style={s.itemText}>{item.text}</span>
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

        <section style={s.section}>
          <p style={s.sectionLabel}>Synopsis</p>
          <div style={s.synopsisGrid}>
            <div>
              <p style={s.synLabel}>Before</p>
              <p style={s.synText}>{result.synopsis_before}</p>
            </div>
            <div>
              <p style={{ ...s.synLabel, color: "#4ade80" }}>After</p>
              <p style={{ ...s.synText, color: "#cbd5e1" }}>{result.synopsis_after}</p>
            </div>
          </div>
        </section>

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
  modal: { background: "#131820", border: "1px solid #1e2535", borderRadius: 12, padding: 24, width: 580, maxWidth: "90vw", maxHeight: "80vh", overflowY: "auto", boxShadow: "0 24px 60px rgba(0,0,0,0.5)" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  title: { fontSize: 15, fontWeight: 600, color: "#e2e8f0" },
  close: { background: "none", border: "none", color: "#64748b", fontSize: 16, cursor: "pointer" },
  noUpdates: { color: "#64748b", fontSize: 13, textAlign: "center", padding: "20px 0" },
  section: { marginBottom: 20 },
  sectionLabel: { fontSize: 10, fontWeight: 700, color: "#475569", letterSpacing: "0.08em", textTransform: "uppercase" as const, marginBottom: 8 },
  row: { display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 6, flexWrap: "wrap" as const },
  itemId: { fontFamily: "monospace", color: "#475569", fontSize: 11 },
  tier: { fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 4 },
  arrow: { color: "#475569", fontSize: 11 },
  itemText: { color: "#cbd5e1", flex: 1 },
  synopsisGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 },
  synLabel: { fontSize: 10, fontWeight: 700, color: "#64748b", letterSpacing: "0.06em", textTransform: "uppercase" as const, marginBottom: 6 },
  synText: { fontSize: 12, color: "#94a3b8", lineHeight: 1.6, margin: 0 },
  dismissBtn: { marginTop: 8, width: "100%", background: "#1e2535", border: "none", borderRadius: 8, color: "#94a3b8", padding: "10px", fontSize: 13, cursor: "pointer" },
};
