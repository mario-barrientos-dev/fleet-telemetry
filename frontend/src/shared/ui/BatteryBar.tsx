export function BatteryBar({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  let fill = "bg-emerald-500";
  if (clamped < 15) fill = "bg-rose-500";
  else if (clamped < 35) fill = "bg-amber-500";

  return (
    <div className="flex items-center gap-2">
      <div
        className="h-2 w-24 overflow-hidden rounded bg-slate-800"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className={`h-full ${fill}`} style={{ width: `${clamped}%` }} />
      </div>
      <span className="w-9 text-right text-xs tabular-nums text-slate-300">{clamped}%</span>
    </div>
  );
}
