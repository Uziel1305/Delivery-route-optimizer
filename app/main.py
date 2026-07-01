from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import get_settings
from app.couriers.router import router as couriers_router
from app.geocoding.router import router as geocoding_router
from app.jobs.router import router as jobs_router

settings = get_settings()

app = FastAPI(title="Delivery Route Optimizer")

# The React frontend runs on a different origin (localhost:5173) than the API
# (localhost:8000), so the browser needs CORS headers to read API responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(couriers_router)
app.include_router(geocoding_router)
app.include_router(jobs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
