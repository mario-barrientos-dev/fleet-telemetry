import { FleetStatusHeader } from "@/features/fleet-status/FleetStatusHeader";
import { VehicleList } from "@/features/vehicle-list/VehicleList";
import { ZoneCountsPanel } from "@/features/zone-counts/ZoneCountsPanel";

export function Dashboard() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Fleet Telemetry</h1>
        <p className="text-sm text-slate-400">
          50 vehicles · 1 Hz telemetry · polling every 1.5 s
        </p>
      </header>
      <FleetStatusHeader />
      <VehicleList />
      <ZoneCountsPanel />
    </main>
  );
}
