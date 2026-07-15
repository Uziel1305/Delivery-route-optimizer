# Delivery Route Optimizer

A web app for managers to assign delivery stops to couriers with optimal routing.

FastAPI + SQLAlchemy + PostgreSQL, Celery + RabbitMQ, self-hosted OSRM (travel times), Photon (geocoding), React frontend — all in Docker Compose.

## Screenshots

**Sign in:**

![Login page](docs/images/login.jpg)

**Registration** — pick a role at sign-up; managers plan routes, couriers drive them:

![Manager registration](docs/images/register-manager.jpg)

![Courier registration](docs/images/register-courier.jpg)

**Manager home** — delivery days at a glance:

![Manager home with delivery days list](docs/images/manager-home.jpg)

**Couriers roster** — invite couriers by username and manage the team; each courier carries their own default start/end addresses:

![Couriers page with roster and invite-by-username](docs/images/manager-couriers.jpg)

**Courier invites** — the courier accepts or rejects a manager's invitation:

![Courier invites page with a pending invitation](docs/images/courier-invites.jpg)

**Delivery address book** — reusable saved locations, validated via Photon geocoding (city → street → house number):

![Delivery locations address book](docs/images/delivery-locations.jpg)

**Creating a delivery day** — pick a date and assign couriers:

![Creating a delivery day](docs/images/create-delivery-day.gif)

**Route generation** — generating returns instantly with a pending option; a Celery worker solves in the background and the optimized per-courier split appears on the map over real OSRM road times:

![Generating an optimized route split](docs/images/generate-route-split.gif)

**Refining an option** — move a stop to another courier (instant re-solve) or try the same day with a different number of couriers:

![Swapping a stop and generating with N couriers](docs/images/swap-and-try-n-couriers.gif)

**Courier's view** — the published route, stops in driving order:

![Courier route view with ordered stops and map](docs/images/courier-route.jpg)

## Running the stack

```bash
cp .env.example .env      # then edit secrets (or keep the dev defaults)
docker compose up --build
```

Services:
- Backend API — http://localhost:8000 (docs at `/docs`)
- Frontend — http://localhost:5173
- OSRM routing — http://localhost:5001
- RabbitMQ management — http://localhost:15672

**First run** downloads the Israel region OSM extract (~115 MB) and preprocesses it for OSRM (`osrm-download` → `osrm-init`). This happens once; subsequent runs reuse the `osrm_data` volume. The backend runs `alembic upgrade head` automatically on boot.

## Tests

```bash
# Unit tests — no services needed (framework-agnostic algorithm package)
pytest tests/optimization

# Integration tests — require the stack to be up (real Postgres + OSRM + Photon)
docker compose up -d
API_BASE_URL=http://localhost:8000 pytest tests/integration
```

The integration suite auto-skips if the backend isn't reachable.
