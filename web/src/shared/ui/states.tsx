/** Loading, error and empty states shared by every screen. */
import type { ReactNode } from "react";
import type { ApiError } from "../api";

export function Skeleton({ rows = 6, label }: { rows?: number; label: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-2 py-4">
      {Array.from({ length: rows }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: placeholder rows have no identity
        <div key={i} className="h-5 rounded-soft bg-rail motion-safe:animate-pulse" />
      ))}
    </div>
  );
}

export function ErrorState({ error, retry, what }: { error: ApiError; retry: () => void; what: string }) {
  return (
    <div role="alert" className="flex max-w-prose flex-col items-start gap-3 border-l-rule border-outvoted py-2 pl-4">
      <p className="text-lead font-semibold text-ink">Could not load {what}.</p>
      <p className="text-copy">{error.message}</p>
      <button
        type="button"
        onClick={retry}
        className="rounded-soft bg-ink px-4 py-2 font-semibold text-sheet hover:bg-agreed"
      >
        Try again
      </button>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex max-w-prose flex-col gap-2 py-6">
      <p className="text-lead font-semibold text-ink">{title}</p>
      <div className="text-copy">{children}</div>
    </div>
  );
}
