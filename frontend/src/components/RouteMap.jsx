import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Palette used to color each courier's route distinctly.
export const ROUTE_COLORS = [
  "#4f46e5", "#16a34a", "#d97706", "#dc2626", "#0891b2",
  "#7c3aed", "#db2777", "#65a30d", "#ea580c", "#0d9488",
];

function depotIcon() {
  return L.divIcon({
    className: "",
    html: `<div style="background:#0f172a;color:#fff;width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,.35);border:2px solid #fff">★</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

function stopIcon(color, index) {
  return L.divIcon({
    className: "",
    html: `<div style="background:${color};color:#fff;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,.35);border:2px solid #fff">${index}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 13);
    } else {
      map.fitBounds(points, { padding: [40, 40] });
    }
  }, [points, map]);
  return null;
}

/**
 * depot: {lat, lon}
 * routes: [{ color, label, stops: [{lat, lon, label, seq}] }]
 */
export default function RouteMap({ depot, routes = [] }) {
  const allPoints = [
    [depot.lat, depot.lon],
    ...routes.flatMap((r) => r.stops.map((s) => [s.lat, s.lon])),
  ];

  return (
    <div className="map-container">
      <MapContainer center={[depot.lat, depot.lon]} zoom={13} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds points={allPoints} />

        <Marker position={[depot.lat, depot.lon]} icon={depotIcon()}>
          <Popup>Depot</Popup>
        </Marker>

        {routes.map((route, ri) => {
          const line = [
            [depot.lat, depot.lon],
            ...route.stops.map((s) => [s.lat, s.lon]),
            [depot.lat, depot.lon],
          ];
          return (
            <div key={ri}>
              <Polyline positions={line} pathOptions={{ color: route.color, weight: 4, opacity: 0.7 }} />
              {route.stops.map((s, si) => (
                <Marker key={si} position={[s.lat, s.lon]} icon={stopIcon(route.color, s.seq ?? si + 1)}>
                  <Popup>
                    <strong>#{s.seq ?? si + 1}</strong> {s.label}
                    {route.label ? <div style={{ color: "#64748b" }}>{route.label}</div> : null}
                  </Popup>
                </Marker>
              ))}
            </div>
          );
        })}
      </MapContainer>
    </div>
  );
}
