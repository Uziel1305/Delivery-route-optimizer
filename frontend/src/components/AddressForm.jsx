import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";

/**
 * Structured city / street / house-number entry with typeahead suggestions
 * (proxied Photon) and hard-block validation. On a valid address it calls
 * onResolved({ lat, lon, label }).
 */
export default function AddressForm({ onResolved, submitting, submitLabel = "Add stop" }) {
  const [city, setCity] = useState("");
  const [street, setStreet] = useState("");
  const [houseNumber, setHouseNumber] = useState("");

  const [citySuggestions, setCitySuggestions] = useState([]);
  const [streetSuggestions, setStreetSuggestions] = useState([]);
  const [showCity, setShowCity] = useState(false);
  const [showStreet, setShowStreet] = useState(false);

  const [fieldError, setFieldError] = useState(null); // { field, message }
  const [validating, setValidating] = useState(false);

  const cityDebounce = useRef();
  const streetDebounce = useRef();

  useEffect(() => {
    if (city.trim().length < 2) {
      setCitySuggestions([]);
      return;
    }
    clearTimeout(cityDebounce.current);
    cityDebounce.current = setTimeout(async () => {
      try {
        const res = await api.get(`/geocoding/suggest/cities?q=${encodeURIComponent(city)}`);
        setCitySuggestions(res.slice(0, 6));
      } catch {
        setCitySuggestions([]);
      }
    }, 250);
    return () => clearTimeout(cityDebounce.current);
  }, [city]);

  useEffect(() => {
    if (street.trim().length < 2 || city.trim().length < 2) {
      setStreetSuggestions([]);
      return;
    }
    clearTimeout(streetDebounce.current);
    streetDebounce.current = setTimeout(async () => {
      try {
        const res = await api.get(
          `/geocoding/suggest/streets?city=${encodeURIComponent(city)}&q=${encodeURIComponent(street)}`
        );
        setStreetSuggestions(res.slice(0, 6));
      } catch {
        setStreetSuggestions([]);
      }
    }, 250);
    return () => clearTimeout(streetDebounce.current);
  }, [street, city]);

  async function handleSubmit(e) {
    e.preventDefault();
    setFieldError(null);
    setValidating(true);
    try {
      const result = await api.post("/geocoding/validate", {
        city,
        street,
        house_number: houseNumber,
      });
      if (!result.valid) {
        setFieldError(result.error);
        return;
      }
      await onResolved({
        lat: result.coordinate.lat,
        lon: result.coordinate.lon,
        label: `${street} ${houseNumber}, ${city}`,
      });
      setStreet("");
      setHouseNumber("");
      setStreetSuggestions([]);
    } catch (err) {
      if (err instanceof ApiError && err.status === 502) {
        setFieldError({ field: "city", message: "Geocoding service unavailable, try again." });
      } else {
        setFieldError({ field: "city", message: "Validation failed." });
      }
    } finally {
      setValidating(false);
    }
  }

  const errFor = (f) => (fieldError?.field === f ? fieldError.message : null);

  return (
    <form onSubmit={handleSubmit}>
      <div className="field">
        <label>City</label>
        <div className="suggest-box">
          <input
            className={`input ${errFor("city") ? "error" : ""}`}
            value={city}
            placeholder="e.g. Tel Aviv"
            onChange={(e) => {
              setCity(e.target.value);
              setShowCity(true);
              setFieldError(null);
            }}
            onFocus={() => setShowCity(true)}
            onBlur={() => setTimeout(() => setShowCity(false), 150)}
          />
          {showCity && citySuggestions.length > 0 && (
            <div className="suggest-list">
              {citySuggestions.map((s, i) => (
                <div
                  key={i}
                  className="suggest-item"
                  onMouseDown={() => {
                    setCity(s.label);
                    setShowCity(false);
                  }}
                >
                  {s.label}
                </div>
              ))}
            </div>
          )}
        </div>
        {errFor("city") && <div className="field-error">{errFor("city")}</div>}
      </div>

      <div className="field">
        <label>Street</label>
        <div className="suggest-box">
          <input
            className={`input ${errFor("street") ? "error" : ""}`}
            value={street}
            placeholder="e.g. Rothschild Boulevard"
            onChange={(e) => {
              setStreet(e.target.value);
              setShowStreet(true);
              setFieldError(null);
            }}
            onFocus={() => setShowStreet(true)}
            onBlur={() => setTimeout(() => setShowStreet(false), 150)}
          />
          {showStreet && streetSuggestions.length > 0 && (
            <div className="suggest-list">
              {streetSuggestions.map((s, i) => (
                <div
                  key={i}
                  className="suggest-item"
                  onMouseDown={() => {
                    setStreet(s.label);
                    setShowStreet(false);
                  }}
                >
                  {s.label}
                  {s.city ? <span style={{ color: "#94a3b8" }}> · {s.city}</span> : null}
                </div>
              ))}
            </div>
          )}
        </div>
        {errFor("street") && <div className="field-error">{errFor("street")}</div>}
      </div>

      <div className="field">
        <label>House number</label>
        <input
          className={`input ${errFor("house_number") ? "error" : ""}`}
          value={houseNumber}
          placeholder="e.g. 1"
          onChange={(e) => {
            setHouseNumber(e.target.value);
            setFieldError(null);
          }}
        />
        {errFor("house_number") && <div className="field-error">{errFor("house_number")}</div>}
      </div>

      <button className="btn btn-primary btn-block" disabled={validating || submitting || !city || !street || !houseNumber}>
        {validating ? "Validating address…" : submitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
