import type { VehicleStatus } from "@/shared/api/types";

const STYLES: Record<VehicleStatus, string> = {
  idle: "bg-slate-700 text-slate-100",
  moving: "bg-emerald-600 text-emerald-50",
  charging: "bg-sky-600 text-sky-50",
  fault: "bg-rose-600 text-rose-50",
};

export function StatusBadge({ status }: { status: VehicleStatus }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium tracking-wide ${STYLES[status]}`}
    >
      {status}
    </span>
  );
}
