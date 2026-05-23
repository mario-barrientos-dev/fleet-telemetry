import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type {
  FleetStatusOut,
  VehiclesOut,
  ZoneCountsOut,
  AnomaliesOut,
} from "@/shared/api/types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export const fleetApi = createApi({
  reducerPath: "fleetApi",
  baseQuery: fetchBaseQuery({ baseUrl: API_BASE_URL }),
  refetchOnMountOrArgChange: true,
  endpoints: (build) => ({
    fleetStatus: build.query<FleetStatusOut, void>({
      query: () => "/api/v1/fleet/status",
    }),
    vehicles: build.query<VehiclesOut, void>({
      query: () => "/api/v1/vehicles",
    }),
    zoneCounts: build.query<ZoneCountsOut, void>({
      query: () => "/api/v1/zones/counts",
    }),
    anomalies: build.query<AnomaliesOut, { vehicle_id?: string } | void>({
      query: (args) => {
        const params = new URLSearchParams();
        if (args?.vehicle_id) params.set("vehicle_id", args.vehicle_id);
        const qs = params.toString();
        return `/api/v1/anomalies${qs ? `?${qs}` : ""}`;
      },
    }),
  }),
});

export const {
  useFleetStatusQuery,
  useVehiclesQuery,
  useZoneCountsQuery,
  useAnomaliesQuery,
} = fleetApi;
