import { useFleetStatusQuery } from "@/shared/api/fleetApi";
import type { VehicleStatus } from "@/shared/api/types";

const ORDER: VehicleStatus[] = ["idle", "moving", "charging", "fault"];
const COLORS: Record<VehicleStatus, string> = {
  idle: "border-slate-600 text-slate-200",
  moving: "border-emerald-600 text-emerald-200",
  charging: "border-sky-600 text-sky-200",
  fault: "border-rose-600 text-rose-200",
};

export function FleetStatusHeader() {
  const { data, isLoading, isError } = useFleetStatusQuery(undefined, {
    pollingInterval: 1500,
  });

  if (isLoading) return <Skeleton />;
  if (isError || !data) return <ErrorState />;

  return (
    <section aria-label="Fleet status">
      <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-slate-400">
        Fleet ({data.total})
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {ORDER.map((s) => (
          <div
            key={s}
            className={`rounded-lg border ${COLORS[s]} bg-slate-900 px-4 py-3`}
          >
            <div className="text-xs uppercase tracking-wider opacity-80">{s}</div>
            <div className="text-2xl font-semibold tabular-nums">{data.counts[s]}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-busy="true">
      {ORDER.map((s) => (
        <div key={s} className="h-16 animate-pulse rounded-lg bg-slate-900" />
      ))}
    </div>
  );
}

function ErrorState() {
  return (
    <div className="rounded-lg border border-rose-700 bg-rose-950 px-4 py-2 text-sm text-rose-200">
      Could not load fleet status.
    </div>
  );
}
