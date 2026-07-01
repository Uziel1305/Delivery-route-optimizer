from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import require_role
from app.auth.models import User, UserRole
from app.geocoding.client import extract_coordinate, extract_label, photon_client
from app.geocoding.schemas import (
    FieldError,
    SuggestionOut,
    ValidateAddressRequest,
    ValidateAddressResponse,
)

router = APIRouter(prefix="/geocoding", tags=["geocoding"])


def _require_country(user: User) -> str:
    if not user.country:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="country not set — complete onboarding first",
        )
    return user.country


def _city_matches(feature: dict, city: str) -> bool:
    feature_city = feature.get("properties", {}).get("city")
    return not feature_city or city.lower() in feature_city.lower()


@router.get("/suggest/cities", response_model=list[SuggestionOut])
def suggest_cities(q: str, manager: User = Depends(require_role(UserRole.MANAGER))):
    country = _require_country(manager)
    features = photon_client.search(q, countrycode=country, layers=["city", "district", "locality"])
    return [
        SuggestionOut(label=extract_label(f), lat=lat, lon=lon)
        for f in features
        for lat, lon in [extract_coordinate(f)]
    ]


@router.get("/suggest/streets", response_model=list[SuggestionOut])
def suggest_streets(
    q: str,
    city: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
):
    country = _require_country(manager)

    city_features = photon_client.search(
        city, countrycode=country, layers=["city", "district", "locality"], limit=1
    )
    if not city_features:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="city not recognized")
    city_lat, city_lon = extract_coordinate(city_features[0])

    # Photon's `q` is free-text, not structured fields, so the city name is
    # folded into the query and mismatched results are post-filtered below.
    combined_query = f"{city} {q}"
    features = photon_client.search(
        combined_query, countrycode=country, layers=["street"], lat=city_lat, lon=city_lon
    )

    results = []
    for f in features:
        if not _city_matches(f, city):
            continue
        lat, lon = extract_coordinate(f)
        results.append(
            SuggestionOut(label=extract_label(f), lat=lat, lon=lon, city=f.get("properties", {}).get("city"))
        )
    return results


@router.post("/validate", response_model=ValidateAddressResponse)
def validate_address(
    payload: ValidateAddressRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
):
    """Hard-block cascade: re-resolve city, then street within that city,
    then house number within that street. Whichever step fails determines
    which field the UI flags red. OSM house-number coverage is incomplete in
    some regions — a small number of real addresses may be rejected, an
    accepted tradeoff for this design.
    """
    country = _require_country(manager)

    city_features = photon_client.search(
        payload.city, countrycode=country, layers=["city", "district", "locality"], limit=1
    )
    if not city_features:
        return ValidateAddressResponse(valid=False, error=FieldError(field="city", message="City not recognized"))
    city_lat, city_lon = extract_coordinate(city_features[0])

    street_query = f"{payload.city} {payload.street}"
    street_features = [
        f
        for f in photon_client.search(
            street_query, countrycode=country, layers=["street"], lat=city_lat, lon=city_lon, limit=5
        )
        if _city_matches(f, payload.city)
    ]
    if not street_features:
        return ValidateAddressResponse(
            valid=False, error=FieldError(field="street", message="Street not recognized in this city")
        )
    street_lat, street_lon = extract_coordinate(street_features[0])

    house_query = f"{payload.city} {payload.street} {payload.house_number}"
    house_features = photon_client.search(
        house_query, countrycode=country, layers=["house"], lat=street_lat, lon=street_lon, limit=3
    )
    if not house_features:
        return ValidateAddressResponse(
            valid=False,
            error=FieldError(field="house_number", message="House number not recognized on this street"),
        )

    lat, lon = extract_coordinate(house_features[0])
    return ValidateAddressResponse(
        valid=True,
        coordinate=SuggestionOut(label=extract_label(house_features[0]), lat=lat, lon=lon, city=payload.city),
    )
