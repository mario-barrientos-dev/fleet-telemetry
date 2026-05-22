.PHONY: help up down logs build clean \
        backend-install backend-lint backend-format backend-typecheck backend-test backend-test-fast backend-migrate backend-seed backend-run \
        frontend-install frontend-lint frontend-typecheck frontend-test frontend-build frontend-run frontend-gen-types \
        ci

help:
	@echo "Targets:"
	@echo "  up / down / logs / build   - docker compose lifecycle"
	@echo "  backend-*                  - tooling for backend"
	@echo "  frontend-*                 - tooling for frontend"
	@echo "  ci                         - full lint + typecheck + test for both"

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f api web db

build:
	docker compose build

clean:
	docker compose down -v --remove-orphans

# ---- backend ----
backend-install:
	cd backend && uv sync

backend-lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

backend-format:
	cd backend && uv run ruff format . && uv run ruff check --fix .

backend-typecheck:
	cd backend && uv run mypy app

backend-test:
	cd backend && uv run pytest -q

backend-test-fast:
	cd backend && uv run pytest -q -m "not integration"

backend-migrate:
	cd backend && uv run alembic upgrade head

backend-seed:
	cd backend && uv run python -m scripts.seed

backend-run:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ---- frontend ----
frontend-install:
	cd frontend && pnpm install

frontend-lint:
	cd frontend && pnpm lint

frontend-typecheck:
	cd frontend && pnpm typecheck

frontend-test:
	cd frontend && pnpm test --run

frontend-build:
	cd frontend && pnpm build

frontend-run:
	cd frontend && pnpm dev

frontend-gen-types:
	cd frontend && pnpm gen:types

ci: backend-lint backend-typecheck backend-test frontend-lint frontend-typecheck frontend-test frontend-build
