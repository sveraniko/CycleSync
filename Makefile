.PHONY: up down logs api bot format lint test

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

format:
	python -m compileall app tests

lint:
	python -m compileall app tests

test:
	pytest -q
