from pydantic import BaseModel


class SuggestionOut(BaseModel):
    label: str
    lat: float
    lon: float
    city: str | None = None


class ValidateAddressRequest(BaseModel):
    city: str
    street: str
    house_number: str


class FieldError(BaseModel):
    field: str
    message: str


class ValidateAddressResponse(BaseModel):
    valid: bool
    coordinate: SuggestionOut | None = None
    error: FieldError | None = None
