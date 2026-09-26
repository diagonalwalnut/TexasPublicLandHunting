import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

type Props = {
  geojson: GeoJSON.FeatureCollection | null;
  matchingIds: Set<string>;
  selectedId: string | null;
  satellite: boolean;
  active: boolean;
  onSelect: (id: string) => void;
};

const OREGON_BOUNDS: maplibregl.LngLatBoundsLike = [
  [-124.7, 41.9],
  [-116.4, 46.4],
];

function rasterStyle(satellite: boolean): maplibregl.StyleSpecification {
  const tiles = satellite
    ? ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]
    : ["https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"];
  const attribution = satellite ? "Tiles © Esri" : "© OpenStreetMap © CARTO";
  return {
    version: 8,
    sources: { basemap: { type: "raster", tiles, tileSize: 256, attribution } },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

export default function OregonMap({ geojson, matchingIds, selectedId, satellite, active, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const dataRef = useRef(geojson);
  const matchRef = useRef(matchingIds);
  const selectedRef = useRef(selectedId);
  const onSelectRef = useRef(onSelect);
  dataRef.current = geojson;
  matchRef.current = matchingIds;
  selectedRef.current = selectedId;
  onSelectRef.current = onSelect;

  const paint = (map: maplibregl.Map) => {
    const data = dataRef.current;
    if (!data || !map.getSource("areas")) return;
    for (const feature of data.features) {
      const id = feature.id ?? feature.properties?.id;
      if (typeof id !== "string") continue;
      map.setFeatureState(
        { source: "areas", id },
        { match: matchRef.current.has(id), selected: id === selectedRef.current },
      );
    }
  };

  useEffect(() => {
    if (!containerRef.current) return;
    readyRef.current = false;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: rasterStyle(satellite),
      bounds: OREGON_BOUNDS,
      fitBoundsOptions: { padding: 24 },
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    map.on("load", () => {
      const empty: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
      map.addSource("areas", {
        type: "geojson",
        data: dataRef.current ?? empty,
        promoteId: "id",
      });
      map.addLayer({
        id: "areas-fill",
        type: "fill",
        source: "areas",
        paint: {
          "fill-color": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            "#c4a35a",
            ["boolean", ["feature-state", "match"], false],
            "#2f6b4f",
            "#8aa394",
          ],
          "fill-opacity": ["case", ["boolean", ["feature-state", "match"], false], 0.5, 0.15],
        },
      });
      map.addLayer({
        id: "areas-line",
        type: "line",
        source: "areas",
        paint: {
          "line-color": "#1c3b2c",
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 2.5, 1],
        },
      });
      map.on("click", "areas-fill", (event) => {
        const feature = event.features?.[0];
        const id = (feature?.id ?? feature?.properties?.id) as string | undefined;
        if (id) onSelectRef.current(String(id));
      });
      map.on("mouseenter", "areas-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "areas-fill", () => {
        map.getCanvas().style.cursor = "";
      });
      readyRef.current = true;
      paint(map);
    });
    return () => {
      readyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, [satellite]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !geojson) return;
    const source = map.getSource("areas") as maplibregl.GeoJSONSource | undefined;
    source?.setData(geojson);
    paint(map);
  }, [geojson, matchingIds, selectedId]);

  useEffect(() => {
    if (!active) return;
    const map = mapRef.current;
    if (!map) return;
    const id = window.setTimeout(() => map.resize(), 60);
    return () => window.clearTimeout(id);
  }, [active]);

  return <div ref={containerRef} className="h-full w-full" />;
}
