.PHONY: up down logs test lint migrate upgrade

up:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	pytest

lint:
	ruff check .
	ruff format --check .
	mypy src

migrate:
	alembic revision --autogenerate -m "$(m)"

upgrade:
	alembic upgrade head
