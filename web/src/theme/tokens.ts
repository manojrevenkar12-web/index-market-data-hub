/**
 * The hub's tokens. A fixing sheet in cool fog and blue-black ink. Cobalt marks what vendors agreed on,
 * amber what the hub repaired or held, violet what the desk looked up or corrected, red what was outvoted.
 * Every colour, size, width and duration in the app comes from here.
 */
export const color = {
  paper: "#EEF1F5",
  sheet: "#FFFFFF",
  rail: "#E2E7EE",
  ink: "#172434",
  copy: "#2B3747",
  muted: "#566375",
  line: "#CDD5DF",
  agreed: "#1E56B3",
  agreedWash: "#DCE6F7",
  held: "#8A5100",
  heldWash: "#F7EBD6",
  desk: "#6B3FC4",
  deskWash: "#ECE5FA",
  outvoted: "#B42318",
  outvotedWash: "#FBE4E1",
  focus: "#1E56B3",
} as const;

export const font = {
  ui: ["Archivo Variable", "Archivo", "system-ui", "sans-serif"],
} as const;

/** One family, three widths: expanded for levels and titles, condensed for column heads, normal for the rest. */
export const width = { condensed: "75%", normal: "100%", expanded: "125%" } as const;

/** Type scale: 1.25 ratio from a 15px base. [size, line-height] */
export const type = {
  small: ["0.8125rem", "1.35"],
  body: ["0.9375rem", "1.5"],
  lead: ["1.1875rem", "1.35"],
  title: ["1.875rem", "1.1"],
  level: ["2.5rem", "1"],
} as const;

export const space = {
  0: "0",
  1: "0.25rem",
  2: "0.5rem",
  3: "0.75rem",
  4: "1rem",
  5: "1.5rem",
  6: "2rem",
  7: "3rem",
  8: "4rem",
} as const;

export const radius = { none: "0", soft: "4px", dot: "999px" } as const;
export const measure = { prose: "64ch", rail: "22rem" } as const;
export const line = { hair: "1px", rule: "2px" } as const;
export const size = { dot: "1.375rem", spark: "5.5rem", sparkHeight: "1.5rem" } as const;
