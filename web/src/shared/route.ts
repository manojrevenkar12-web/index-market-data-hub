/** The view lives in the URL hash, so a link opens the same index, tab and date: #/UKS20/close/2026-09-25 */
import { useCallback, useEffect, useState } from "react";

export type Tab = "close" | "desk" | "designs";
export type Route = { index: string | null; tab: Tab; day: string | null };

const TABS: Tab[] = ["close", "desk", "designs"];

export function parse(hash: string): Route {
  const [index, tab, day] = hash.replace(/^#\/?/, "").split("/");
  return {
    index: index || null,
    tab: TABS.includes(tab as Tab) ? (tab as Tab) : "close",
    day: day && /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : null,
  };
}

export function useRoute(): [Route, (next: Partial<Route>) => void] {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback(
    (next: Partial<Route>) => {
      const r = { ...route, ...next };
      window.location.hash = `/${r.index ?? ""}/${r.tab}${r.day ? `/${r.day}` : ""}`;
    },
    [route],
  );
  return [route, go];
}
