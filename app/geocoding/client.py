import httpx

from app.config import get_settings

settings = get_settings()


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

        response = httpx.get(f"{self.base_url}/api", params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
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
