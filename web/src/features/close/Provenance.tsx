/**
 * Where a golden price came from, one mark per vendor: filled when the vendor's quote was used, amber ring when the
 * hub repaired its unit, struck through when it was outvoted, dashed when the vendor sent nothing in time.
 */
import { VENDORS } from "../../shared/format";
import type { ConstituentRow } from "../../shared/types";

type State = "used" | "repaired" | "outvoted" | "absent";

const STYLE: Record<State, string> = {
  used: "bg-agreed text-sheet border-agreed",
  repaired: "bg-heldWash text-held border-held",
  outvoted: "bg-outvotedWash text-outvoted border-outvoted line-through",
  absent: "bg-transparent text-muted border-line border-dashed",
};

const SAY: Record<State, string> = {
  used: "used",
  repaired: "repaired and used",
  outvoted: "outvoted",
  absent: "no quote by the close",
};

export function vendorState(row: ConstituentRow, vendor: string): State {
  const c = row.candidates.find((x) => x.vendor === vendor);
  if (!c) return "absent";
  if (row.sources.includes(vendor)) return c.repaired ? "repaired" : "used";
  return "outvoted";
}

export function Provenance({ row }: { row: ConstituentRow }) {
  const states = VENDORS.map((v) => ({ v, s: vendorState(row, v.id) }));
  return (
    <ul className="flex gap-1" aria-label={states.map(({ v, s }) => `${v.name} ${SAY[s]}`).join(", ")}>
      {states.map(({ v, s }) => (
        <li
          key={v.id}
          aria-hidden="true"
          title={`${v.name}: ${SAY[s]}`}
          className={`flex h-dot w-dot items-center justify-center rounded-dot border text-small font-semibold ${STYLE[s]}`}
        >
          {v.letter}
        </li>
      ))}
    </ul>
  );
}

export const METHOD: Record<ConstituentRow["method"], { label: string; tone: string }> = {
  consensus: { label: "Vendors agree", tone: "text-muted" },
  single: { label: "One vendor", tone: "text-copy" },
  closest: { label: "Closest to peers", tone: "text-held" },
  carried: { label: "Held at last price", tone: "text-held" },
  desk: { label: "Desk looked up", tone: "text-desk" },
  primary: { label: "Primary vendor", tone: "text-copy" },
  backup: { label: "Backup vendor", tone: "text-copy" },
  median: { label: "Median", tone: "text-copy" },
};
