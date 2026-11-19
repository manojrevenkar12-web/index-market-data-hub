/** What the hub sent to the desk on one date, highest risk first, and what the desk found. */
import { useResource } from "../../shared/api";
import { fmt } from "../../shared/format";
import type { Desk } from "../../shared/types";
import { Empty, ErrorState, Skeleton } from "../../shared/ui/states";

export function DeskView({ day }: { day: string }) {
  const res = useResource<Desk>(`/api/desk?date=${day}`);
  if (res.loading && !res.data) return <Skeleton rows={5} label="Loading the desk queue" />;
  if (res.error) return <ErrorState error={res.error} retry={res.retry} what="the desk queue" />;
  const items = res.data?.items ?? [];
  if (items.length === 0)
    return (
      <Empty title="Nothing went to the desk">
        On {fmt.day(day)} every constituent price and corporate action was settled by vendor agreement or the hub's
        checks.
      </Empty>
    );
  return (
    <section aria-labelledby="desk-title" className="flex flex-col gap-4">
      <h2 id="desk-title" className="text-lead font-semibold text-ink">
        {items.filter((i) => i.looked_up).length} of {items.length} questions looked up before the close
      </h2>
      <ol className="flex flex-col">
        {items.map((it, n) => (
          <li
            key={`${it.instrument}-${it.topic}-${n}`}
            className="grid grid-cols-[8rem_1fr_auto] items-baseline gap-4 border-b border-line py-3"
          >
            <span className="font-semibold text-ink">
              {it.ticker}
              <span className="ml-2 text-small font-normal text-muted">{it.topic === "price" ? "price" : "action"}</span>
            </span>
            <span>
              {it.reason}
              {it.topic === "price" && it.looked_up && it.answer != null && (
                <span className="block text-small text-muted">
                  Hub had {fmt.price(it.provisional)}, the exchange says {fmt.price(it.answer)}
                </span>
              )}
            </span>
            <span
              className={`rounded-soft px-2 text-small font-semibold ${
                it.looked_up ? "bg-deskWash text-desk" : "bg-rail text-muted"
              }`}
            >
              {it.looked_up ? "Looked up" : "Not reached"}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
