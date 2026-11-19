import { type KeyboardEvent, useRef } from "react";
import { Board } from "./features/board/Board";
import { CloseView } from "./features/close/CloseView";
import { DesignsView } from "./features/designs/DesignsView";
import { DeskView } from "./features/desk/DeskView";
import { useResource } from "./shared/api";
import { fmt } from "./shared/format";
import { type Tab, useRoute } from "./shared/route";
import type { Board as BoardData } from "./shared/types";
import { Boundary } from "./shared/ui/Boundary";
import { Empty, ErrorState, Skeleton } from "./shared/ui/states";

const TABS: { id: Tab; label: string }[] = [
  { id: "close", label: "Close" },
  { id: "desk", label: "Desk" },
  { id: "designs", label: "Designs compared" },
];

export function App() {
  const [route, go] = useRoute();
  const board = useResource<BoardData>(route.day ? `/api/board?date=${route.day}` : "/api/board");
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const onTabKey = (e: KeyboardEvent, i: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const next = (i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length;
    const tab = TABS[next];
    if (!tab) return;
    go({ tab: tab.id });
    tabRefs.current[next]?.focus();
  };

  const data = board.data;
  const selected = data?.indices.find((i) => i.id === route.index) ?? data?.indices[0];
  const day = data?.date ?? null;

  return (
    <div className="min-h-screen lg:flex">
      <aside className="flex flex-col gap-6 bg-rail px-5 py-6 lg:w-rail lg:shrink-0">
        <header className="flex flex-col gap-1">
          <p className="stretch-expanded text-lead font-bold text-ink">Index market data hub</p>
          <p className="text-small text-muted">Golden prices from three vendors, published at 18:30 Frankfurt</p>
        </header>
        {board.loading && !data && <Skeleton rows={4} label="Loading the indices" />}
        {board.error && <ErrorState error={board.error} retry={board.retry} what="the indices" />}
        {data && data.indices.length > 0 && selected && (
          <Board
            board={data}
            selected={selected.id}
            onSelect={(id) => go({ index: id, tab: route.tab === "designs" ? "close" : route.tab })}
            onDay={(d) => go({ day: d })}
          />
        )}
      </aside>
      <main className="flex min-w-0 flex-1 flex-col gap-5 bg-sheet px-6 py-6 lg:px-7">
        <Boundary>
          {data && data.indices.length === 0 && (
            <Empty title="No closes published yet">
              Load a simulated quarter with <code>python -m imdh.eval.load</code>, then reload this page.
            </Empty>
          )}
          {selected && day && (
            <>
              <header className="flex flex-wrap items-end justify-between gap-4">
                <div className="flex flex-col gap-1">
                  <h1 className="stretch-expanded text-title font-bold text-ink">{selected.name}</h1>
                  <p className="text-muted">
                    {selected.return_type === "total" ? "Total return" : "Price return"},{" "}
                    {selected.weighting === "equal" ? "equal weight" : "capped market value"}, {selected.constituents}{" "}
                    constituents, close of {fmt.day(day)}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <p className="stretch-expanded text-level font-semibold text-ink">
                    {fmt.level(selected.level)}
                    <span className="ml-2 text-lead font-normal text-muted">{selected.currency}</span>
                  </p>
                  <p className="text-small text-muted">
                    {fmt.change(selected.change)} on the day, published {fmt.time(selected.published_at)}
                    {selected.corrected_at && (
                      <span className="text-desk">
                        {" "}
                        and corrected {fmt.time(selected.corrected_at)} from {fmt.level(selected.first_level)}
                      </span>
                    )}
                  </p>
                </div>
              </header>
              <div role="tablist" aria-label="Views" className="flex gap-1 border-b border-line">
                {TABS.map((t, i) => {
                  const on = route.tab === t.id;
                  return (
                    <button
                      key={t.id}
                      ref={(el) => {
                        tabRefs.current[i] = el;
                      }}
                      type="button"
                      role="tab"
                      id={`tab-${t.id}`}
                      aria-selected={on}
                      aria-controls={`panel-${t.id}`}
                      tabIndex={on ? 0 : -1}
                      onKeyDown={(e) => onTabKey(e, i)}
                      onClick={() => go({ tab: t.id })}
                      className={`-mb-px border-b-rule px-4 py-2 font-semibold ${
                        on ? "border-agreed text-ink" : "border-transparent text-muted hover:text-ink"
                      }`}
                    >
                      {t.label}
                      {t.id === "desk" && data?.desk && data.desk.looked_up > 0 && (
                        <span className="ml-2 rounded-soft bg-deskWash px-1 text-small text-desk">
                          {data.desk.looked_up}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
              <div role="tabpanel" id={`panel-${route.tab}`} aria-labelledby={`tab-${route.tab}`}>
                {route.tab === "close" && <CloseView index={selected} day={day} />}
                {route.tab === "desk" && <DeskView day={day} />}
                {route.tab === "designs" && <DesignsView />}
              </div>
            </>
          )}
        </Boundary>
      </main>
    </div>
  );
}
