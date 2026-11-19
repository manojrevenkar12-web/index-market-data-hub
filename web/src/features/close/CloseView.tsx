/** One index on one trade date: its constituents' golden prices, where each came from and why. */
import { AnimatePresence, motion } from "framer-motion";
import { useResource } from "../../shared/api";
import { fmt } from "../../shared/format";
import type { BoardIndex, Constituents } from "../../shared/types";
import { Empty, ErrorState, Skeleton } from "../../shared/ui/states";
import { motionTokens } from "../../theme/motion";
import { METHOD, Provenance } from "./Provenance";

export function CloseView({ index, day }: { index: BoardIndex; day: string }) {
  const res = useResource<Constituents>(`/api/indices/${index.id}/constituents?date=${day}`);
  if (res.loading && !res.data) return <Skeleton rows={10} label="Loading constituents" />;
  if (res.error) return <ErrorState error={res.error} retry={res.retry} what="the constituents" />;
  const rows = res.data?.rows ?? [];
  if (rows.length === 0)
    return (
      <Empty title="No golden prices for this date">
        The hub has not recorded a close for {index.name} on {fmt.day(day)}.
      </Empty>
    );
  const flagged = rows.filter((r) => r.method !== "consensus").length;
  return (
    <section aria-labelledby="close-title" className="flex flex-col gap-4">
      <h2 id="close-title" className="text-lead font-semibold text-ink">
        {rows.length} constituents, {flagged === 0 ? "every price agreed by two vendors" : `${flagged} not settled by agreement`}
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="stretch-condensed border-b border-line text-small text-muted">
              <th scope="col" className="py-2 pr-4 font-semibold">Instrument</th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">Weight</th>
              <th scope="col" className="py-2 pr-4 text-right font-semibold">Golden price</th>
              <th scope="col" className="py-2 pr-4 font-semibold">Vendors</th>
              <th scope="col" className="py-2 pr-4 font-semibold">How it was set</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {rows.map((r) => (
                <motion.tr
                  key={r.instrument}
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: motionTokens.quick, ease: motionTokens.ease }}
                  className="border-b border-line align-top"
                >
                  <td className="whitespace-nowrap py-2 pr-4">
                    <span className="font-semibold text-ink">{r.ticker}</span>
                    <span className="ml-2 text-small text-muted">{r.isin}</span>
                  </td>
                  <td className="whitespace-nowrap py-2 pr-4 text-right">{fmt.weight(r.weight)}</td>
                  <td className="whitespace-nowrap py-2 pr-4 text-right text-ink">
                    {fmt.price(r.price)} <span className="text-small text-muted">{r.currency}</span>
                    {r.version > 1 && (
                      <span className="ml-2 rounded-soft bg-deskWash px-1 text-small text-desk">restated</span>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    <Provenance row={r} />
                  </td>
                  <td className="py-2 pr-4">
                    <span className={`font-semibold ${METHOD[r.method].tone}`}>{METHOD[r.method].label}</span>
                    {r.reasons.length > 0 && <p className="text-small text-muted">{r.reasons.join("; ")}</p>}
                  </td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </section>
  );
}
