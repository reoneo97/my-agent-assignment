import type { MemoryItemSummary, TierStatus } from "../types";

interface Props {
  items: MemoryItemSummary[];
}

const TIER_COLORS: Record<TierStatus, { bg: string; text: string }> = {
  tentative:   { bg: "#1e293b", text: "#94a3b8" },
  established: { bg: "#1e3a5f", text: "#60a5fa" },
  confirmed:   { bg: "#14532d", text: "#4ade80" },
};

const CATEGORY_LABELS: Record<string, string> = {
  INSTRUCTION_MODALITY: "Modality",
  ESCALATION:           "Escalation",
  TROUBLESHOOTING:      "Troubleshoot",
  SHIFT_PATTERN:        "Shift",
  LEARNING_NEED:        "Learning",
  ISSUE_CONFIDENCE:     "Confidence",
};

export default function ProfilePanel({ items }: Props) {
  return (
    <aside style={styles.panel}>
      <div style={styles.heading}>
        Operator Profile
        <span style={styles.count}>{items.length} item{items.length !== 1 ? "s" : ""}</span>
      </div>

      {items.length === 0 ? (
        <p style={styles.empty}>No profile yet.<br />Send a message to start learning.</p>
      ) : (
        <ul style={styles.list}>
          {items.map((item) => {
            const tier = TIER_COLORS[item.status] ?? TIER_COLORS.tentative;
            return (
              <li key={item.id} style={styles.item}>
                <div style={styles.itemTop}>
                  <span style={{ ...styles.badge, background: tier.bg, color: tier.text }}>
                    {item.status}
                  </span>
                  <span style={styles.categoryLabel}>
                    {CATEGORY_LABELS[item.category] ?? item.category}
                  </span>
                  <span style={styles.count}>n={item.evidence_count}</span>
                </div>
                <p style={styles.itemText}>{item.text}</p>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    width: 280,
    minWidth: 240,
    borderRight: "1px solid #1e2535",
    background: "#131820",
    display: "flex",
    flexDirection: "column",
    overflowY: "auto",
  },
  heading: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 16px 10px",
    fontSize: 13,
    fontWeight: 600,
    color: "#94a3b8",
    borderBottom: "1px solid #1e2535",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
  },
  count: {
    fontSize: 11,
    color: "#475569",
    fontWeight: 400,
  },
  empty: {
    fontSize: 12,
    color: "#475569",
    padding: "20px 16px",
    lineHeight: 1.6,
    margin: 0,
  },
  list: {
    listStyle: "none",
    margin: 0,
    padding: "8px 0",
  },
  item: {
    padding: "10px 14px",
    borderBottom: "1px solid #1a2030",
  },
  itemTop: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    marginBottom: 5,
  },
  badge: {
    fontSize: 10,
    fontWeight: 600,
    padding: "2px 6px",
    borderRadius: 4,
    letterSpacing: "0.04em",
  },
  categoryLabel: {
    fontSize: 10,
    color: "#64748b",
    flex: 1,
  },
  itemText: {
    fontSize: 12,
    color: "#cbd5e1",
    margin: 0,
    lineHeight: 1.5,
  },
};
