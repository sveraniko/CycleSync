.PHONY: up down logs api bot format lint test db-upgrade db-downgrade db-revision db-current db-reset-local catalog-ingest search-rebuild reminders-materialize reminders-dispatch check-connectivity

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

api:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

bot:
	python -m app.run_bot

catalog-ingest:
	python -m scripts.run_catalog_ingest

search-rebuild:
	python -m scripts.rebuild_search_projection

reminders-materialize:
	python -m scripts.materialize_reminders

reminders-dispatch:
	python -m scripts.dispatch_reminders

check-connectivity:
	python -m scripts.check_connectivity

format:
	python -m black app tests
	python -m ruff check --fix app tests

lint:
	python -m black --check app tests
	python -m ruff check app tests

test:
	pytest -q

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-revision:
	alembic revision --autogenerate -m "$(MSG)"

db-current:
	alembic current

db-reset-local:
	docker compose down -v
	docker compose up -d postgres redis
	sleep 5
	alembic upgrade head
