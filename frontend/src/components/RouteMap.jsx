import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Palette used to color each courier's route distinctly.
export const ROUTE_COLORS = [
  "#4f46e5", "#16a34a", "#d97706", "#dc2626", "#0891b2",
  "#7c3aed", "#db2777", "#65a30d", "#ea580c", "#0d9488",
];

function terminalIcon(color, glyph) {
  return L.divIcon({
    className: "",
    html: `<div style="background:${color};color:#fff;width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,.35);border:2px solid #fff">${glyph}</div>`,
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
 * routes: [{ color, label, start: {lat, lon, label}?, end: {lat, lon, label}?,
 *            stops: [{lat, lon, label, seq}] }]
 * Each route runs its courier's start -> stops -> end; start/end markers are
 * colored like the route (▶ = start, ⏹ = end).
 */
export default function RouteMap({ routes = [] }) {
  const allPoints = routes.flatMap((r) => [
    ...(r.start ? [[r.start.lat, r.start.lon]] : []),
    ...r.stops.map((s) => [s.lat, s.lon]),
    ...(r.end ? [[r.end.lat, r.end.lon]] : []),
  ]);
  const center = allPoints[0] || [32.08, 34.78];

  return (
    <div className="map-container">
      <MapContainer center={center} zoom={13} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds points={allPoints} />

        {routes.map((route, ri) => {
          const line = [
            ...(route.start ? [[route.start.lat, route.start.lon]] : []),
            ...route.stops.map((s) => [s.lat, s.lon]),
            ...(route.end ? [[route.end.lat, route.end.lon]] : []),
          ];
          return (
            <div key={ri}>
              <Polyline positions={line} pathOptions={{ color: route.color, weight: 4, opacity: 0.7 }} />
              {route.start && (
                <Marker position={[route.start.lat, route.start.lon]} icon={terminalIcon(route.color, "▶")}>
                  <Popup>
                    <strong>Start</strong> {route.start.label}
                    {route.label ? <div style={{ color: "#64748b" }}>{route.label}</div> : null}
                  </Popup>
                </Marker>
              )}
              {route.stops.map((s, si) => (
                <Marker key={si} position={[s.lat, s.lon]} icon={stopIcon(route.color, s.seq ?? si + 1)}>
                  <Popup>
                    <strong>#{s.seq ?? si + 1}</strong> {s.label}
                    {route.label ? <div style={{ color: "#64748b" }}>{route.label}</div> : null}
                  </Popup>
                </Marker>
              ))}
              {route.end && (
                <Marker position={[route.end.lat, route.end.lon]} icon={terminalIcon(route.color, "⏹")}>
                  <Popup>
                    <strong>End</strong> {route.end.label}
                    {route.label ? <div style={{ color: "#64748b" }}>{route.label}</div> : null}
                  </Popup>
                </Marker>
              )}
            </div>
          );
        })}
      </MapContainer>
    </div>
  );
}
