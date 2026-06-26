/**
 * Shared design tokens for the Operator Learning Assistant UI.
 *
 * Centralising the palette keeps the dark theme consistent across panels and
 * makes future re-theming a single-file change. The same values are mirrored as
 * CSS custom properties in index.css for use in className-based styling.
 */

export const color = {
  // Surfaces (darkest → lightest)
  bg: "#0f1117",
  surface: "#131820",
  surfaceRaised: "#1a2030",
  border: "#1e2535",
  borderSubtle: "#1a2030",
  borderStrong: "#334155",

  // Text
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textFaint: "#64748b",
  textDim: "#475569",
  textHeading: "#f1f5f9",

  // Accents
  accent: "#2563eb",
  accentText: "#60a5fa",
  success: "#4ade80",
  successDeep: "#16653f",
  warning: "#f59e0b",
  warningText: "#fbbf24",
  danger: "#f87171",
  dangerDeep: "#7f1d1d",
} as const;

/** Tier badge colours, shared by ProfilePanel and ShiftEndDiff. */
export const tierStyle: Record<string, { bg: string; color: string }> = {
  tentative: { bg: "#1e293b", color: "#94a3b8" },
  established: { bg: "#1e3a5f", color: "#60a5fa" },
  confirmed: { bg: "#14532d", color: "#4ade80" },
  superseded: { bg: "#2a1a1a", color: "#a1a1aa" },
};

export const radius = { sm: 4, md: 6, lg: 8, xl: 10, xxl: 12 } as const;
