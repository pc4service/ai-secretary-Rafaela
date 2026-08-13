.PHONY: up down build logs test health shell

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f backend

test:
	./scripts/test_chat.sh

health:
	curl -s http://localhost:8000/health | python3 -m json.tool

shell:
	docker compose exec backend bash
