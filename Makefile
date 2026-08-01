.PHONY: up down logs test lint migrate upgrade backup restore

up:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec -T app sh -c 'DATABASE_URL="$${DATABASE_URL%/*}/$${DATABASE_URL##*/}_test" pytest'

lint:
	ruff check .
	ruff format --check .
	mypy src

migrate:
	docker compose exec -T app alembic revision --autogenerate -m "$(m)"

upgrade:
	docker compose exec -T app alembic upgrade head

backup:
	@mkdir -p backups
	docker compose exec -T postgres sh -c 'pg_dump -U "$$POSTGRES_USER" "$$POSTGRES_DB"' \
		> backups/$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup written to backups/"

restore:
	@test -n "$(f)" || (echo 'usage: make restore f=backups/<file>.sql' && exit 1)
	docker compose exec -T postgres sh -c 'psql -U "$$POSTGRES_USER" "$$POSTGRES_DB"' < $(f)
