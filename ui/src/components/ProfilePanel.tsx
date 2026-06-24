import type { ProfileItem, TierStatus } from "../types";

interface Props {
  items: ProfileItem[];
}

const TIER: Record<TierStatus, { bg: string; color: string }> = {
  tentative:   { bg: "#1e293b", color: "#94a3b8" },
  established: { bg: "#1e3a5f", color: "#60a5fa" },
  confirmed:   { bg: "#14532d", color: "#4ade80" },
};

const CAT_LABELS: Record<string, string> = {
  INSTRUCTION_MODALITY: "Modality",
  ESCALATION:           "Escalation",
  TROUBLESHOOTING:      "Troubleshoot",
  SHIFT_PATTERN:        "Shift",
  LEARNING_NEED:        "Learning",
  ISSUE_CONFIDENCE:     "Confidence",
};

function groupBy<T>(items: T[], key: (t: T) => string): Record<string, T[]> {
  return items.reduce<Record<string, T[]>>((acc, item) => {
    const k = key(item);
    (acc[k] ??= []).push(item);
    return acc;
  }, {});
}

export default function ProfilePanel({ items }: Props) {
  const grouped = groupBy(items, (i) => i.category);

  return (
    <div style={s.panel}>
      <div style={s.heading}>
        Live Profile
        <span style={s.count}>{items.length} item{items.length !== 1 ? "s" : ""}</span>
      </div>

      {items.length === 0 ? (
        <p style={s.empty}>No profile yet.</p>
      ) : (
        Object.entries(grouped).map(([cat, catItems]) => (
          <div key={cat} style={s.group}>
            <p style={s.catLabel}>{CAT_LABELS[cat] ?? cat}</p>
            {catItems.map((item) => {
              const tier = TIER[item.status] ?? TIER.tentative;
              return (
                <div key={item.id} style={s.item}>
                  <div style={s.itemTop}>
                    <span style={{ ...s.badge, background: tier.bg, color: tier.color }}>
                      {item.status}
                    </span>
                    <span style={s.evidence}>n={item.evidence_count}</span>
                  </div>
                  <p style={s.itemText}>{item.text}</p>
                  {item.status === "tentative" && (
                    <p style={s.caution}>confirm if relevant</p>
                  )}
                </div>
              );
            })}
          </div>
        ))
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  panel: { width: 260, minWidth: 220, borderRight: "1px solid #1e2535", background: "#131820", display: "flex", flexDirection: "column", overflowY: "auto" },
  heading: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 14px 10px", fontSize: 11, fontWeight: 700, color: "#64748b", borderBottom: "1px solid #1e2535", letterSpacing: "0.08em", textTransform: "uppercase" as const },
  count: { fontWeight: 400, color: "#334155" },
  empty: { fontSize: 12, color: "#475569", padding: "16px 14px", margin: 0 },
  group: { borderBottom: "1px solid #1a2030", paddingBottom: 4 },
  catLabel: { fontSize: 10, fontWeight: 700, color: "#475569", letterSpacing: "0.08em", textTransform: "uppercase" as const, margin: "10px 14px 4px" },
  item: { padding: "6px 14px 8px" },
  itemTop: { display: "flex", alignItems: "center", gap: 6, marginBottom: 4 },
  badge: { fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 4, letterSpacing: "0.04em" },
  evidence: { fontSize: 10, color: "#475569" },
  itemText: { margin: 0, fontSize: 12, color: "#cbd5e1", lineHeight: 1.5 },
  caution: { margin: "3px 0 0", fontSize: 10, color: "#78716c", fontStyle: "italic" },
};
