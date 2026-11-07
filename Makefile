.PHONY: bootstrap check-refs scan-secrets gate ci lint typecheck test sim replay up seed smoke migrate run

bootstrap:
	uv sync

check-refs:
	uv run python scripts/check_refs.py

scan-secrets:
	uv run python scripts/scan_secrets.py

gate:
	uv run python scripts/check_antipatterns.py

ci: check-refs scan-secrets test

lint:
	uv run ruff check backend sim scripts

typecheck:
	uv run ruff check --select F,E9 backend sim scripts

test:
	uv run pytest -q

sim:
	uv run python -m sim.fmap
	uv run python -m sim.roi

replay:
	uv run python scripts/replay_decision.py --decision $(DECISION)

up:
	docker compose -f infra/docker-compose.yml --profile $(or $(COMPOSE_PROFILE),lite) up -d

seed:
	uv run python scripts/seed.py

smoke:
	uv run pytest backend/tests/golden -q

migrate:
	uv run alembic upgrade head

run:
	uv run uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload

