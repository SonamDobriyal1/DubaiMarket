"use client";

import { useEffect, useRef } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Map, Marker } from "maplibre-gl";

export type MapPin = {
  community_id: string;
  community_name: string;
  latitude: number;
  longitude: number;
  color: string;
};

const RASTER_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
};

export default function MapCanvas({ pins, selectedId, onSelect }: { pins: MapPin[]; selectedId?: string; onSelect: (id: string) => void }) {
  const node = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const markerClassRef = useRef<typeof Marker | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const fittedRef = useRef(false);
  const onSelectRef = useRef(onSelect);
  const pinsRef = useRef(pins);
  const selectedRef = useRef(selectedId);
  onSelectRef.current = onSelect;
  pinsRef.current = pins;
  selectedRef.current = selectedId;

  useEffect(() => {
    let cancelled = false;
    let map: Map | null = null;
    (async () => {
      const maplibregl = await import("maplibre-gl");
      maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
      if (cancelled || !node.current) return;
      map = new maplibregl.Map({
        container: node.current,
        style: RASTER_STYLE,
        center: [55.27, 25.12],
        zoom: 10.2,
        minZoom: 8,
        maxZoom: 15,
        canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
      map.on("load", () => {
        if (cancelled || !map) return;
        mapRef.current = map;
        markerClassRef.current = maplibregl.Marker;
        map.resize();
        placeMarkers(map, maplibregl.Marker, pinsRef.current, selectedRef.current, markersRef, onSelectRef);
        fitCommunities(map, maplibregl, pinsRef.current);
      });
    })();
    return () => {
      cancelled = true;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      mapRef.current = null;
      map?.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const MarkerClass = markerClassRef.current;
    if (!map || !MarkerClass) return;
    placeMarkers(map, MarkerClass, pins, selectedId, markersRef, onSelectRef);
    if (!fittedRef.current && pins.length) {
      fittedRef.current = true;
      void import("maplibre-gl").then((maplibregl) => {
        if (mapRef.current === map) fitCommunities(map, maplibregl, pins);
      });
    }
  }, [pins, selectedId]);

  const openedAt = useRef(0);
  const focusKey = pins.find((pin) => pin.community_id === selectedId);
  const focusToken = focusKey ? `${focusKey.community_id}:${focusKey.latitude}:${focusKey.longitude}` : "";
  useEffect(() => {
    if (!openedAt.current) openedAt.current = Date.now();
    const map = mapRef.current;
    const pin = pinsRef.current.find((item) => item.community_id === selectedRef.current);
    if (!map || !pin || !focusToken) return;
    if (Date.now() - openedAt.current < 1200) return;
    map.flyTo({ center: [pin.longitude, pin.latitude], zoom: Math.max(map.getZoom(), 12), duration: 650 });
  }, [focusToken]);

  return <div ref={node} className="h-full w-full [&_.maplibregl-ctrl-bottom-left]:bottom-36 [&_.maplibregl-ctrl-bottom-right]:bottom-36 xl:[&_.maplibregl-ctrl-bottom-left]:bottom-40 xl:[&_.maplibregl-ctrl-bottom-right]:bottom-40" />;
}

function fitCommunities(map: Map, maplibregl: typeof import("maplibre-gl"), pins: MapPin[]) {
  if (!pins.length) return;
  const bounds = new maplibregl.LngLatBounds();
  for (const pin of pins) bounds.extend([pin.longitude, pin.latitude]);
  const narrow = map.getContainer().clientWidth < 1280;
  map.fitBounds(bounds, {
    padding: narrow ? { top: 210, bottom: 168, left: 16, right: 16 } : { top: 120, bottom: 200, left: 48, right: 360 },
    maxZoom: narrow ? 11 : 12,
    duration: 0,
  });
}

function placeMarkers(
  map: Map,
  MarkerClass: typeof Marker,
  pins: MapPin[],
  selectedId: string | undefined,
  markersRef: { current: Marker[] },
  onSelectRef: { current: (id: string) => void },
) {
  markersRef.current.forEach((marker) => marker.remove());
  markersRef.current = pins.map((pin) => {
    const selected = pin.community_id === selectedId;
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-label", pin.community_name);
    button.title = pin.community_name;
    button.style.cssText = [
      "display:flex",
      "flex-direction:column",
      "align-items:center",
      "gap:2px",
      "border:0",
      "background:transparent",
      "padding:0",
      "cursor:pointer",
    ].join(";");
    const dot = document.createElement("span");
    dot.style.cssText = [
      `width:${selected ? 18 : 14}px`,
      `height:${selected ? 18 : 14}px`,
      "border-radius:999px",
      `background:${pin.color}`,
      "border:2px solid #fff",
      "box-shadow:0 1px 4px rgba(15,23,42,.45)",
    ].join(";");
    button.append(dot);
    if (selected) {
      const label = document.createElement("span");
      label.textContent = pin.community_name;
      label.style.cssText = [
        "max-width:160px",
        "overflow:hidden",
        "text-overflow:ellipsis",
        "white-space:nowrap",
        "border-radius:999px",
        "background:rgba(255,255,255,.95)",
        "padding:1px 6px",
        "font:600 11px/1.3 Inter,sans-serif",
        "color:#0f172a",
        "box-shadow:0 1px 2px rgba(15,23,42,.15)",
      ].join(";");
      button.append(label);
    }
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      onSelectRef.current(pin.community_id);
    });
    const marker = new MarkerClass({ element: button, anchor: "center" }).setLngLat([pin.longitude, pin.latitude]).addTo(map);
    marker.getElement().style.zIndex = selected ? "3" : "1";
    return marker;
  });
}
