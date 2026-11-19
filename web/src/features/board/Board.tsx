/** The fixing board: every index's close on the chosen trade date. Selecting one opens it on the right. */
import { motion } from "framer-motion";
import { fmt } from "../../shared/format";
import type { Board as BoardData } from "../../shared/types";
import { Spark } from "../../shared/ui/Spark";
import { motionTokens } from "../../theme/motion";

type Props = {
  board: BoardData;
  selected: string;
  onSelect: (id: string) => void;
  onDay: (day: string) => void;
};

export function Board({ board, selected, onSelect, onDay }: Props) {
  return (
    <nav aria-label="Indices" className="flex flex-col gap-5">
      <label className="flex flex-col gap-1">
        <span className="stretch-condensed text-small font-semibold text-muted">Trade date</span>
        <select
          value={board.date ?? ""}
          onChange={(e) => onDay(e.target.value)}
          className="rounded-soft border border-line bg-sheet px-3 py-2 text-ink"
        >
          {[...board.days].reverse().map((d) => (
            <option key={d} value={d}>
              {fmt.day(d)}
            </option>
          ))}
        </select>
      </label>
      <ul className="flex flex-col gap-1">
        {board.indices.map((ix, i) => {
          const active = ix.id === selected;
          return (
            <motion.li
              key={ix.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05, duration: motionTokens.settle, ease: motionTokens.ease }}
            >
              <button
                type="button"
                aria-current={active ? "true" : undefined}
                onClick={() => onSelect(ix.id)}
                className={`flex w-full flex-col gap-1 rounded-soft border-l-rule px-4 py-3 text-left ${
                  active ? "border-agreed bg-sheet" : "border-transparent hover:bg-sheet"
                }`}
              >
                <span className="flex items-baseline justify-between gap-2">
                  <span className="font-semibold text-ink">{ix.name}</span>
                  <span className="text-small text-muted">{ix.id}</span>
                </span>
                <span className="flex items-end justify-between gap-3">
                  <span className="stretch-expanded text-lead font-semibold text-ink">
                    {fmt.level(ix.level)}
                    <span className="ml-2 text-small font-normal text-muted">{ix.currency}</span>
                  </span>
                  <Spark values={ix.spark} tone={ix.change >= 0 ? "up" : "down"} />
                </span>
                <span className="flex items-center gap-2 text-small">
                  <span className={ix.change >= 0 ? "text-agreed" : "text-copy"}>{fmt.change(ix.change)}</span>
                  {ix.corrected_at && (
                    <span className="rounded-soft bg-deskWash px-2 text-desk">
                      Corrected {fmt.time(ix.corrected_at)}
                    </span>
                  )}
                </span>
              </button>
            </motion.li>
          );
        })}
      </ul>
      {board.desk && (
        <p className="text-small text-muted">
          Desk on this date: {board.desk.looked_up} looked up, {board.desk.open} left to the hub's own checks.
        </p>
      )}
    </nav>
  );
}
