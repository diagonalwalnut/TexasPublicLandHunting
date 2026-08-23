import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

type Props = {
  matchingIds: Set<string>;
  selectedId: string | null;
  regionFilter: string;
  onSelectUnit: (id: string) => void;
  onSelectRegion: (region: string) => void;
  satellite: boolean;
  active: boolean;
};

const TEXAS_BOUNDS: maplibregl.LngLatBoundsLike = [
  [-106.8, 25.7],
  [-93.3, 36.6],
];

type UnitProps = { id?: string; lon?: number | null; lat?: number | null; region?: string };
type RegionProps = { name?: string; lon?: number; lat?: number };
type FeatureLike = {
  id?: string | number;
  properties?: UnitProps & RegionProps;
  geometry?: { type: string; coordinates: unknown };
};

function rasterStyle(satellite: boolean): maplibregl.StyleSpecification {
  const tiles = satellite
    ? ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]
    : ["https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"];
  const attribution = satellite ? "Tiles © Esri" : "© OpenStreetMap © CARTO";
  return {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      basemap: { type: "raster", tiles, tileSize: 256, attribution },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

function geometryBbox(coordinates: unknown): maplibregl.LngLatBounds | null {
  const bounds = new maplibregl.LngLatBounds();
  let any = false;
  const walk = (value: unknown) => {
    if (Array.isArray(value) && typeof value[0] === "number" && typeof value[1] === "number") {
      bounds.extend([value[0], value[1]]);
      any = true;
      return;
    }
    if (Array.isArray(value)) value.forEach(walk);
  };
  walk(coordinates);
  return any ? bounds : null;
}

const POLY_GEOM: maplibregl.FilterSpecification = [
  "in",
  ["geometry-type"],
  ["literal", ["Polygon", "MultiPolygon"]],
];
const POINT_GEOM: maplibregl.FilterSpecification = ["==", ["geometry-type"], "Point"];

function withMatch(
  geom: maplibregl.FilterSpecification,
  match: maplibregl.FilterSpecification | null,
): maplibregl.FilterSpecification {
  return match ? (["all", geom, match] as maplibregl.FilterSpecification) : geom;
}

export default function HuntMap({
  matchingIds,
  selectedId,
  regionFilter,
  onSelectUnit,
  onSelectRegion,
  satellite,
  active,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const featureIdsRef = useRef<string[]>([]);
  const unitsRef = useRef<FeatureLike[]>([]);
  const regionsRef = useRef<FeatureLike[]>([]);
  const readyRef = useRef(false);
  const matchingRef = useRef(matchingIds);
  const selectedRef = useRef(selectedId);
  const regionRef = useRef(regionFilter);
  const fittedKeyRef = useRef<string | null>(null);
  const callbacks = useRef({ onSelectUnit, onSelectRegion });
  matchingRef.current = matchingIds;
  selectedRef.current = selectedId;
  regionRef.current = regionFilter;
  callbacks.current = { onSelectUnit, onSelectRegion };

  const matchFilter = (): maplibregl.FilterSpecification | null => {
    const ids = [...matchingRef.current];
    if (ids.length === 0) return ["==", ["get", "id"], "__none__"];
    if (ids.length === featureIdsRef.current.length) return null;
    return ["in", ["get", "id"], ["literal", ids]];
  };

  const matchingBounds = (): maplibregl.LngLatBounds | null => {
    const bounds = new maplibregl.LngLatBounds();
    let any = false;
    for (const feature of unitsRef.current) {
      const id = String(feature.id ?? feature.properties?.id ?? "");
      if (!matchingRef.current.has(id)) continue;
      const box = feature.geometry ? geometryBbox(feature.geometry.coordinates) : null;
      if (box) {
        bounds.extend(box);
        any = true;
        continue;
      }
      const lon = feature.properties?.lon;
      const lat = feature.properties?.lat;
      if (lon != null && lat != null) {
        bounds.extend([lon, lat]);
        any = true;
      }
    }
    return any ? bounds : null;
  };

  const applyState = (map: maplibregl.Map) => {
    if (!map.getSource("units")) return;
    const match = matchFilter();
    if (map.getLayer("units-fill")) map.setFilter("units-fill", withMatch(POLY_GEOM, match));
    if (map.getLayer("units-line")) map.setFilter("units-line", withMatch(POLY_GEOM, match));
    if (map.getLayer("units-point")) map.setFilter("units-point", withMatch(POINT_GEOM, match));

    for (const id of featureIdsRef.current) {
      map.setFeatureState(
        { source: "units", id },
        { match: matchingRef.current.has(id), selected: id === selectedRef.current },
      );
    }

    const region = regionRef.current;
    let regionFilterExpr: maplibregl.FilterSpecification | null = null;
    if (region) {
      regionFilterExpr = ["==", ["get", "name"], region];
    } else {
      const names = new Set<string>();
      for (const feature of unitsRef.current) {
        const id = String(feature.id ?? feature.properties?.id ?? "");
        if (!matchingRef.current.has(id)) continue;
        const name = feature.properties?.region;
        if (name) names.add(name);
      }
      if (names.size > 0 && names.size < regionsRef.current.length) {
        regionFilterExpr = ["in", ["get", "name"], ["literal", [...names]]];
      }
    }
    if (map.getLayer("regions-fill")) map.setFilter("regions-fill", regionFilterExpr);
    if (map.getLayer("regions-line")) map.setFilter("regions-line", regionFilterExpr);
    if (map.getLayer("region-labels")) map.setFilter("region-labels", regionFilterExpr);
  };

  const fitToSelection = (map: maplibregl.Map) => {
    const selected = selectedRef.current;
    const region = regionRef.current;
    const matchKey = [...matchingRef.current].sort().join(",");
    const key = selected
      ? `unit:${selected}`
      : `filter:${region}:${matchKey}`;
    if (key === fittedKeyRef.current) return;
    fittedKeyRef.current = key;
    if (selected) {
      const feature = unitsRef.current.find((f) => String(f.id ?? f.properties?.id ?? "") === selected);
      const lon = feature?.properties?.lon;
      const lat = feature?.properties?.lat;
      if (lon != null && lat != null) {
        map.flyTo({ center: [lon, lat], zoom: 10.2, duration: 700 });
        return;
      }
    }
    const filtered =
      matchingRef.current.size > 0 && matchingRef.current.size < featureIdsRef.current.length;
    if (filtered) {
      const bounds = matchingBounds();
      if (bounds) {
        map.fitBounds(bounds, { padding: 70, duration: 700, maxZoom: 9.2 });
        return;
      }
    }
    if (region) {
      const feature = regionsRef.current.find((f) => f.properties?.name === region);
      const bounds = feature?.geometry ? geometryBbox(feature.geometry.coordinates) : null;
      if (bounds) {
        map.fitBounds(bounds, { padding: 60, duration: 700, maxZoom: 8.5 });
        return;
      }
    }
    map.fitBounds(TEXAS_BOUNDS, { padding: 40, duration: 700 });
  };

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: rasterStyle(satellite),
      center: [-99.2, 31.3],
      zoom: 5.2,
      maxBounds: [
        [-110, 23],
        [-90, 39],
      ],
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "imperial" }));
    mapRef.current = map;
    fittedKeyRef.current = null;

    map.on("load", async () => {
      const [units, regions] = await Promise.all([
        fetch("data/units.geojson").then((r) => r.json()),
        fetch("data/regions.geojson").then((r) => r.json()),
      ]);
      unitsRef.current = units.features as FeatureLike[];
      regionsRef.current = regions.features as FeatureLike[];
      featureIdsRef.current = unitsRef.current.map((f) => String(f.id ?? f.properties?.id ?? ""));
      map.addSource("regions", { type: "geojson", data: regions });
      map.addSource("units", { type: "geojson", data: units, promoteId: "id" });
      const regionPoints = {
        type: "FeatureCollection",
        features: regionsRef.current
          .filter((f) => f.properties?.lon != null && f.properties?.lat != null)
          .map((f) => ({
            type: "Feature",
            properties: f.properties,
            geometry: { type: "Point", coordinates: [f.properties!.lon, f.properties!.lat] },
          })),
      };
      map.addSource("region-labels", { type: "geojson", data: regionPoints as GeoJSON.FeatureCollection });

      map.addLayer({
        id: "regions-fill",
        type: "fill",
        source: "regions",
        paint: {
          "fill-color": ["coalesce", ["get", "color"], "#2f6b4f"],
          "fill-opacity": 0.14,
        },
      });
      map.addLayer({
        id: "regions-line",
        type: "line",
        source: "regions",
        paint: {
          "line-color": ["coalesce", ["get", "color"], "#2f6b4f"],
          "line-width": 1.5,
          "line-opacity": 0.7,
        },
      });
      map.addLayer({
        id: "region-labels",
        type: "symbol",
        source: "region-labels",
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Open Sans Bold"],
          "text-size": 13,
          "text-letter-spacing": 0.04,
          "text-allow-overlap": false,
          "text-max-width": 10,
        },
        paint: {
          "text-color": "#f4f1ea",
          "text-halo-color": "rgba(16, 24, 16, 0.85)",
          "text-halo-width": 1.4,
        },
      });
      map.addLayer({
        id: "units-fill",
        type: "fill",
        source: "units",
        filter: POLY_GEOM,
        paint: {
          "fill-color": ["case", ["boolean", ["feature-state", "selected"], false], "#c4a35a", "#2f6b4f"],
          "fill-opacity": 0.55,
        },
      });
      map.addLayer({
        id: "units-line",
        type: "line",
        source: "units",
        filter: POLY_GEOM,
        paint: {
          "line-color": ["case", ["boolean", ["feature-state", "selected"], false], "#c4a35a", "#1c3b2c"],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 1.4],
        },
      });
      map.addLayer({
        id: "units-point",
        type: "circle",
        source: "units",
        filter: POINT_GEOM,
        paint: {
          "circle-radius": ["case", ["boolean", ["feature-state", "selected"], false], 8, 6],
          "circle-color": ["case", ["boolean", ["feature-state", "selected"], false], "#c4a35a", "#2f6b4f"],
          "circle-stroke-color": "#f4efe4",
          "circle-stroke-width": 1.5,
          "circle-opacity": 1,
        },
      });

      const pickUnit = (e: maplibregl.MapLayerMouseEvent) => {
        const f = e.features?.[0];
        const id = (f?.id ?? f?.properties?.id) as string | undefined;
        if (id) callbacks.current.onSelectUnit(String(id));
      };
      map.on("click", "units-fill", pickUnit);
      map.on("click", "units-line", pickUnit);
      map.on("click", "units-point", pickUnit);
      const pickRegion = (e: maplibregl.MapLayerMouseEvent) => {
        const unitHit = map.queryRenderedFeatures(e.point, {
          layers: ["units-fill", "units-point"],
        });
        if (unitHit.length) return;
        const name = e.features?.[0]?.properties?.name;
        if (name) callbacks.current.onSelectRegion(String(name));
      };
      map.on("click", "regions-fill", pickRegion);
      map.on("click", "region-labels", (e) => {
        const name = e.features?.[0]?.properties?.name;
        if (name) callbacks.current.onSelectRegion(String(name));
      });

      for (const layer of ["units-fill", "units-point", "regions-fill", "region-labels"]) {
        map.on("mouseenter", layer, () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", layer, () => {
          map.getCanvas().style.cursor = "";
        });
      }

      readyRef.current = true;
      applyState(map);
      map.fitBounds(TEXAS_BOUNDS, { padding: 40, duration: 0 });
      fittedKeyRef.current = "texas";
      if (selectedRef.current || regionRef.current || matchingRef.current.size < featureIdsRef.current.length) {
        fitToSelection(map);
      }
    });

    return () => {
      readyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, [satellite]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    applyState(map);
  }, [matchingIds, selectedId, regionFilter]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    fitToSelection(map);
  }, [matchingIds, selectedId, regionFilter]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !active) return;
    map.resize();
    applyState(map);
  }, [active]);

  return <div ref={containerRef} className="h-full w-full" />;
}
