import type { Config } from "tailwindcss";
import { color, font, line, measure, radius, size, space, type } from "./src/theme/tokens";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    colors: { ...color, transparent: "transparent", current: "currentColor" },
    fontFamily: { ui: [...font.ui] },
    fontSize: Object.fromEntries(
      Object.entries(type).map(([k, [s, lineHeight]]) => [k, [s, { lineHeight }]]),
    ),
    spacing: { ...space, px: line.hair, dot: size.dot, spark: size.spark, "spark-h": size.sparkHeight },
    borderRadius: radius,
    borderWidth: { DEFAULT: line.hair, 0: "0", rule: line.rule },
    extend: { maxWidth: measure, width: { rail: measure.rail } },
  },
  plugins: [],
} satisfies Config;
