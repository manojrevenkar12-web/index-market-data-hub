/** A 30-day line of the index level. Decorative next to the number it summarises, so hidden from readers. */
export function Spark({ values, tone }: { values: number[]; tone: "up" | "down" }) {
  if (values.length < 2) return null;
  const w = 88;
  const h = 24;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const pts = values
    .map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - lo) / span) * (h - 4)).toFixed(1)}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-spark-h w-spark" aria-hidden="true">
      <polyline
        points={pts}
        fill="none"
        strokeWidth="1.5"
        strokeLinejoin="round"
        className={tone === "up" ? "stroke-agreed" : "stroke-ink"}
      />
    </svg>
  );
}
