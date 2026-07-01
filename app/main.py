from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.couriers.router import router as couriers_router
from app.geocoding.router import router as geocoding_router
from app.jobs.router import router as jobs_router

app = FastAPI(title="Delivery Route Optimizer")

app.include_router(auth_router)
app.include_router(couriers_router)
app.include_router(geocoding_router)
app.include_router(jobs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
