// Hand-written types mirroring backend Pydantic schemas. Regenerate via
// `pnpm gen:types` (requires backend running) once a snapshot is needed for
// CI; until then, this file is the source of truth.

export type VehicleStatus = "idle" | "moving" | "charging" | "fault";
export type Severity = "info" | "warning" | "critical";

export interface FleetStatusOut {
  counts: Record<VehicleStatus, number>;
  total: number;
  as_of: string;
}

export interface AnomalyLite {
  kind: string;
  severity: Severity;
  ts: string;
  details: Record<string, unknown>;
}

export interface VehicleOut {
  vehicle_id: string;
  status: VehicleStatus;
  battery_pct: number;
  last_seen_at: string;
  last_lat: number;
  last_lon: number;
  last_anomaly: AnomalyLite | null;
}

export interface VehiclesOut {
  data: VehicleOut[];
}

export interface ZoneCountOut {
  zone_id: string;
  entry_count: number;
}

export interface ZoneCountsOut {
  data: ZoneCountOut[];
  as_of: string;
}

export interface AnomalyOut {
  id: string;
  vehicle_id: string;
  ts: string;
  kind: string;
  severity: Severity;
  details: Record<string, unknown>;
  source_event_id: string | null;
}

export interface AnomaliesOut {
  data: AnomalyOut[];
}
