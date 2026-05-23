import { useVehiclesQuery } from "@/shared/api/fleetApi";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { BatteryBar } from "@/shared/ui/BatteryBar";
import type { VehicleOut } from "@/shared/api/types";

export function VehicleList() {
  const { data, isLoading, isError } = useVehiclesQuery(undefined, {
    pollingInterval: 1500,
  });

  if (isLoading) return <Skeleton />;
  if (isError || !data) return <ErrorState />;

  return (
    <section aria-label="Vehicles">
      <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-slate-400">
        Vehicles ({data.data.length})
      </h2>
      <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
        <table className="w-full text-sm">
          <thead className="bg-slate-950 text-xs uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">Vehicle</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Battery</th>
              <th className="px-3 py-2 text-left">Last anomaly</th>
            </tr>
          </thead>
          <tbody>
            {data.data.map((v) => (
              <VehicleRow key={v.vehicle_id} v={v} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function VehicleRow({ v }: { v: VehicleOut }) {
  return (
    <tr className="border-t border-slate-800">
      <td className="px-3 py-2 font-mono text-slate-200">{v.vehicle_id}</td>
      <td className="px-3 py-2">
        <StatusBadge status={v.status} />
      </td>
      <td className="px-3 py-2">
        <BatteryBar pct={v.battery_pct} />
      </td>
      <td className="px-3 py-2 text-slate-300">
        {v.last_anomaly ? (
          <span
            className={
              v.last_anomaly.severity === "critical"
                ? "text-rose-300"
                : v.last_anomaly.severity === "warning"
                  ? "text-amber-300"
                  : "text-slate-400"
            }
          >
            {v.last_anomaly.kind}{" "}
            <span className="text-slate-500">
              · {new Date(v.last_anomaly.ts).toLocaleTimeString()}
            </span>
          </span>
        ) : (
          <span className="text-slate-600">—</span>
        )}
      </td>
    </tr>
  );
}

function Skeleton() {
  return (
    <div className="h-72 animate-pulse rounded-lg bg-slate-900" aria-busy="true" />
  );
}

function ErrorState() {
  return (
    <div className="rounded-lg border border-rose-700 bg-rose-950 px-4 py-2 text-sm text-rose-200">
      Could not load vehicles.
    </div>
  );
}
