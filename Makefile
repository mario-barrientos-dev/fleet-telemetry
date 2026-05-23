.PHONY: help up down logs build clean \
        backend-env backend-env-update backend-lint backend-format backend-typecheck backend-test backend-test-fast backend-migrate backend-seed backend-run \
        frontend-install frontend-lint frontend-typecheck frontend-test frontend-build frontend-run frontend-gen-types \
        ci

CONDA_ENV := fleet-telemetry
CONDA_RUN := conda run -n $(CONDA_ENV) --no-capture-output

help:
	@echo "Targets:"
	@echo "  up / down / logs / build   - docker compose lifecycle"
	@echo "  backend-env                - create the conda environment from environment.yml"
	@echo "  backend-env-update         - update existing conda env"
	@echo "  backend-*                  - tooling for backend (uses 'conda run -n fleet-telemetry')"
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

# ---- backend (conda) ----
backend-env:
	cd backend && conda env create -f environment.yml

backend-env-update:
	cd backend && conda env update -f environment.yml --prune

backend-lint:
	cd backend && $(CONDA_RUN) ruff check . && $(CONDA_RUN) ruff format --check .

backend-format:
	cd backend && $(CONDA_RUN) ruff format . && $(CONDA_RUN) ruff check --fix .

backend-typecheck:
	cd backend && $(CONDA_RUN) mypy app

backend-test:
	cd backend && $(CONDA_RUN) pytest -q

backend-test-fast:
	cd backend && $(CONDA_RUN) pytest -q -m "not integration"

backend-migrate:
	cd backend && $(CONDA_RUN) alembic upgrade head

backend-seed:
	cd backend && $(CONDA_RUN) python -m scripts.seed

backend-run:
	cd backend && $(CONDA_RUN) uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ---- frontend ----
frontend-install:
	cd frontend && pnpm install

frontend-lint:
	cd frontend && pnpm lint

frontend-typecheck:
	cd frontend && pnpm typecheck

frontend-test:
	cd frontend && pnpm test

frontend-build:
	cd frontend && pnpm build

frontend-run:
	cd frontend && pnpm dev

frontend-gen-types:
	cd frontend && pnpm gen:types

ci: backend-lint backend-typecheck backend-test frontend-lint frontend-typecheck frontend-test frontend-build
