import { useZoneCountsQuery } from "@/shared/api/fleetApi";

export function ZoneCountsPanel() {
  const { data, isLoading, isError } = useZoneCountsQuery(undefined, {
    pollingInterval: 1500,
  });

  if (isLoading) return <Skeleton />;
  if (isError || !data) return <ErrorState />;

  return (
    <section aria-label="Zone entry counts">
      <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-slate-400">
        Zone entries
      </h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {data.data.map((z) => (
          <div
            key={z.zone_id}
            className="rounded-md border border-slate-800 bg-slate-900 px-3 py-2"
          >
            <div className="truncate text-xs text-slate-400">{z.zone_id}</div>
            <div className="text-lg font-semibold tabular-nums text-slate-100">
              {z.entry_count}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-busy="true">
      {Array.from({ length: 20 }).map((_, i) => (
        <div key={i} className="h-14 animate-pulse rounded-md bg-slate-900" />
      ))}
    </div>
  );
}

function ErrorState() {
  return (
    <div className="rounded-lg border border-rose-700 bg-rose-950 px-4 py-2 text-sm text-rose-200">
      Could not load zone counts.
    </div>
  );
}
