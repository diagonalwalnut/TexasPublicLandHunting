import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

type Props = {
  matchingIds: Set<string>;
  selectedId: string | null;
  regionFilter: string;
  onSelectUnit: (id: string) => void;
  onSelectRegion: (region: string) => void;
  satellite: boolean;
};

const TEXAS_BOUNDS: maplibregl.LngLatBoundsLike = [
  [-106.8, 25.7],
  [-93.3, 36.6],
];

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

export default function HuntMap({
  matchingIds,
  selectedId,
  regionFilter,
  onSelectUnit,
  onSelectRegion,
  satellite,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const featureIdsRef = useRef<string[]>([]);
  const readyRef = useRef(false);
  const matchingRef = useRef(matchingIds);
  const selectedRef = useRef(selectedId);
  const regionRef = useRef(regionFilter);
  const callbacks = useRef({ onSelectUnit, onSelectRegion });
  matchingRef.current = matchingIds;
  selectedRef.current = selectedId;
  regionRef.current = regionFilter;
  callbacks.current = { onSelectUnit, onSelectRegion };

  const applyState = (map: maplibregl.Map) => {
    if (!map.getSource("units")) return;
    for (const id of featureIdsRef.current) {
      map.setFeatureState(
        { source: "units", id },
        { match: matchingRef.current.has(id), selected: id === selectedRef.current },
      );
    }
    const region = regionRef.current;
    const filter = region ? (["==", ["get", "name"], region] as maplibregl.FilterSpecification) : null;
    if (map.getLayer("regions-fill")) map.setFilter("regions-fill", filter);
    if (map.getLayer("regions-line")) map.setFilter("regions-line", filter);
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

    map.on("load", async () => {
      const [units, regions] = await Promise.all([
        fetch("data/units.geojson").then((r) => r.json()),
        fetch("data/regions.geojson").then((r) => r.json()),
      ]);
      featureIdsRef.current = (units.features as { properties?: { id?: string }; id?: string }[]).map(
        (f) => String(f.id ?? f.properties?.id ?? ""),
      );
      map.addSource("regions", { type: "geojson", data: regions });
      map.addSource("units", { type: "geojson", data: units, promoteId: "id" });

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
        id: "units-fill",
        type: "fill",
        source: "units",
        filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
        paint: {
          "fill-color": "#2f6b4f",
          "fill-opacity": ["case", ["boolean", ["feature-state", "match"], true], 0.45, 0.08],
        },
      });
      map.addLayer({
        id: "units-line",
        type: "line",
        source: "units",
        filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
        paint: {
          "line-color": ["case", ["boolean", ["feature-state", "selected"], false], "#c4a35a", "#1c3b2c"],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 1.2],
        },
      });
      map.addLayer({
        id: "units-point",
        type: "circle",
        source: "units",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": ["case", ["boolean", ["feature-state", "selected"], false], 8, 5.5],
          "circle-color": "#2f6b4f",
          "circle-stroke-color": "#f4efe4",
          "circle-stroke-width": 1.5,
          "circle-opacity": ["case", ["boolean", ["feature-state", "match"], true], 1, 0.25],
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
      map.on("click", "regions-fill", (e) => {
        const unitHit = map.queryRenderedFeatures(e.point, {
          layers: ["units-fill", "units-point"],
        });
        if (unitHit.length) return;
        const name = e.features?.[0]?.properties?.name;
        if (name) callbacks.current.onSelectRegion(String(name));
      });

      for (const layer of ["units-fill", "units-point", "regions-fill"]) {
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

  return <div ref={containerRef} className="h-full w-full" />;
}
