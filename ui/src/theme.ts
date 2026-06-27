/**
 * Tier badge colours — the single source of truth, shared by ProfilePanel and
 * ShiftEndDiff. Use `tierBadge(status)` so any unknown/legacy status degrades
 * gracefully to the neutral `tentative` style instead of crashing.
 */
export const tierStyle: Record<string, { bg: string; color: string }> = {
  tentative: { bg: "#1e293b", color: "#94a3b8" },
  established: { bg: "#1e3a5f", color: "#60a5fa" },
  confirmed: { bg: "#14532d", color: "#4ade80" },
  superseded: { bg: "#2a1a1a", color: "#a1a1aa" },
};

/** Resolve a tier badge style with a safe fallback for unknown statuses. */
export const tierBadge = (status: string): { bg: string; color: string } =>
  tierStyle[status] ?? tierStyle.tentative;

