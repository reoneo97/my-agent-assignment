import type { Synopsis } from "../types";

interface Props {
  synopsis: Synopsis | null;
}

export default function SynopsisPanel({ synopsis }: Props) {
  return (
    <div style={s.panel}>
      <div style={s.heading}>
        Synopsis
        {synopsis && <span style={s.version}>v{synopsis.version}</span>}
      </div>
      {synopsis ? (
        <>
          <p style={s.text}>{synopsis.text}</p>
          <p style={s.ts}>{new Date(synopsis.generated_at).toLocaleString()}</p>
        </>
      ) : (
        <p style={s.empty}>Run "End Shift" to generate a synopsis.</p>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  panel: { width: 260, minWidth: 220, borderTop: "1px solid #1e2535", background: "#131820", padding: 0, display: "flex", flexDirection: "column" },
  heading: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 14px 10px", fontSize: 11, fontWeight: 700, color: "#64748b", borderBottom: "1px solid #1e2535", letterSpacing: "0.08em", textTransform: "uppercase" as const },
  version: { fontWeight: 400, color: "#334155", fontSize: 10 },
  text: { fontSize: 12, color: "#94a3b8", lineHeight: 1.65, padding: "12px 14px 4px", margin: 0 },
  ts: { fontSize: 10, color: "#334155", padding: "0 14px 12px", margin: 0 },
  empty: { fontSize: 12, color: "#475569", padding: "12px 14px", margin: 0 },
};
