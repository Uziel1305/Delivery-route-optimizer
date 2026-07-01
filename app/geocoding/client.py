import httpx

from app.config import get_settings

settings = get_settings()

# Photon's public instance rejects the default python-httpx User-Agent with a
# 403; a descriptive UA (per its usage policy) is required.
_USER_AGENT = "DeliveryRouteOptimizer/0.1 (Bar-Ilan project; geocoding proxy)"


class PhotonError(Exception):
    """Raised when the upstream Photon service is unreachable or errors."""


class PhotonClient:
    """Thin wrapper around the Photon (Komoot) public geocoding API.

    Backend proxies every call — never call Photon directly from the
    frontend — to avoid CORS, enable caching/debouncing, and hide the
    external dependency.
    """

    def __init__(self, base_url: str | None = None, timeout_seconds: float = 10.0):
        self.base_url = (base_url or settings.photon_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        query: str,
        *,
        countrycode: str,
        layers: list[str] | None = None,
        lat: float | None = None,
        lon: float | None = None,
        limit: int = 8,
    ) -> list[dict]:
        params: dict = {"q": query, "limit": limit, "countrycode": countrycode}
        if layers:
            params["layer"] = layers
        if lat is not None and lon is not None:
            params["lat"] = lat
            params["lon"] = lon

        try:
            response = httpx.get(
                f"{self.base_url}/api",
                params=params,
                timeout=self.timeout_seconds,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PhotonError(f"Photon request failed: {exc}") from exc
        payload = response.json()
        return payload.get("features", [])


photon_client = PhotonClient()


def extract_label(feature: dict) -> str:
    props = feature.get("properties", {})
    return props.get("name") or props.get("street") or props.get("city") or ""


def extract_coordinate(feature: dict) -> tuple[float, float]:
    """Photon returns GeoJSON [lon, lat] — this returns (lat, lon)."""
    coords = feature["geometry"]["coordinates"]
    return coords[1], coords[0]
