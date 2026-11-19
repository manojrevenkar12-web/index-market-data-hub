/** Motion answers a person's action: rows re-sort when the day or index changes. Nothing moves on its own. */
export const motionTokens = {
  quick: 0.16,
  settle: 0.3,
  ease: [0.2, 0.7, 0.2, 1] as const,
} as const;
