"use client";

import dynamic from "next/dynamic";
import { mapHasVerifiedGeometry } from "@/lib/api/client";
import type { MapPayload } from "@/lib/api/types";
import type { MapPin } from "./map-canvas";

const MapCanvas = dynamic(() => import("./map-canvas"), { ssr: false, loading: () => <div className="h-full w-full animate-pulse bg-[#d7e3ea]" /> });

export function DubaiMap({ payload, pins, selectedId, onSelect }: { payload: MapPayload; pins: MapPin[]; selectedId?: string; onSelect: (id: string) => void }) {
  if (!mapHasVerifiedGeometry(payload)) {
    return (
      <div className="flex h-full items-center justify-center bg-[#e7eef2] p-8 text-center">
        <div className="max-w-lg rounded-2xl bg-white/95 p-6 text-slate-700 shadow-xl">
          <p className="text-lg font-semibold text-slate-900">No verified map positions</p>
          <p className="mt-2 text-sm leading-6">{payload.geometry_note || "Communities stay off the map until a real place match is available."}</p>
        </div>
      </div>
    );
  }
  return <MapCanvas pins={pins} selectedId={selectedId} onSelect={onSelect} />;
}
