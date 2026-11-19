/** Every design on the same vendor files, scored against the simulated truth. */
import { useResource } from "../../shared/api";
import type { Report, Results } from "../../shared/types";
import { Empty, ErrorState, Skeleton } from "../../shared/ui/states";

const LABELS: Record<string, string> = {
  single_vendor: "One vendor",
  primary_backup: "Primary with backup",
  median_consensus: "Median of three vendors",
  hub_no_desk: "Hub without desk lookups",
  hub_unranked_desk: "Hub, desk in id order",
  hub_no_action_check: "Hub without action checks",
  hub_no_stale_or_unit_check: "Hub without stale or unit checks",
  hub_undated_symbology: "Hub with undated identifiers",
  hub: "Hub",
};

function Bar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.max((value / max) * 100, value > 0 ? 2 : 0) : 0;
  return (
    <span className="block h-2 w-full rounded-soft bg-rail" aria-hidden="true">
      <span className="block h-2 rounded-soft bg-ink" style={{ width: `${pct}%` }} />
    </span>
  );
}

function Table({ report, title }: { report: Report; title: string }) {
  const names = Object.keys(LABELS).filter((n) => report.designs[n]);
  const max = Math.max(...names.map((n) => report.designs[n]?.wrong_index_closes ?? 0));
  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <h2 className="text-lead font-semibold text-ink">{title}</h2>
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="stretch-condensed border-b border-line text-small text-muted">
            <th scope="col" className="py-2 pr-4 font-semibold">Design</th>
            <th scope="col" className="py-2 pr-4 text-right font-semibold">Index closes off by more than 1 bp</th>
            <th scope="col" className="w-1/5 py-2 pr-4 font-semibold"><span className="sr-only">Bar</span></th>
            <th scope="col" className="py-2 pr-4 text-right font-semibold">Worst error</th>
            <th scope="col" className="py-2 pr-4 text-right font-semibold">Wrong actions</th>
            <th scope="col" className="py-2 text-right font-semibold">Desk lookups</th>
          </tr>
        </thead>
        <tbody>
          {names.map((n) => {
            const d = report.designs[n];
            if (!d) return null;
            const hub = n === "hub";
            return (
              <tr key={n} className={`border-b border-line ${hub ? "font-semibold text-ink" : "font-normal"}`}>
                <th scope="row" className={`py-2 pr-4 text-left ${hub ? "font-semibold" : "font-normal"}`}>{LABELS[n]}</th>
                <td className="py-2 pr-4 text-right">{d.wrong_index_closes}</td>
                <td className="py-2 pr-4"><Bar value={d.wrong_index_closes} max={max} /></td>
                <td className="py-2 pr-4 text-right">{d.max_index_error_bps.toLocaleString("en-GB")} bp</td>
                <td className="py-2 pr-4 text-right">{d.wrong_actions}</td>
                <td className="py-2 text-right">{d.desk_lookups}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

export function DesignsView() {
  const res = useResource<Results>("/api/results");
  if (res.loading && !res.data) return <Skeleton rows={9} label="Loading the design comparison" />;
  if (res.error) return <ErrorState error={res.error} retry={res.retry} what="the design comparison" />;
  if (!res.data?.dev)
    return (
      <Empty title="No evaluation yet">
        Run <code>python -m imdh.eval.cli evaluate</code> to score every design on the development market.
      </Empty>
    );
  return (
    <div className="flex flex-col gap-7">
      <Table report={res.data.dev} title={`Development market, ${res.data.dev.world.business_days} business days`} />
      {res.data.heldout && (
        <Table
          report={res.data.heldout}
          title={`Held-out market, run once, ${res.data.heldout.world.business_days} business days`}
        />
      )}
    </div>
  );
}
