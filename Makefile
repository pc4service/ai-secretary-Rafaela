.PHONY: up down build logs test test-chat health shell knowledge index-knowledge

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f backend

test:
	docker compose exec -T -w /app backend python -m pytest

test-chat:
	./scripts/test_chat.sh

health:
	curl -s http://localhost:8000/health | python3 -m json.tool

knowledge:
	curl -s http://localhost:8000/api/v1/knowledge/status | python3 -m json.tool
	@# /search returns internal content, so it needs a session cookie
	curl -s -c /tmp/rafaela.jar -X POST http://localhost:8000/api/v1/login/demo > /dev/null
	curl -s -b /tmp/rafaela.jar "http://localhost:8000/api/v1/knowledge/search?q=follow-up" | python3 -m json.tool

index-knowledge:
	docker compose exec backend python -c "from app.services.knowledge import index_knowledge_to_qdrant; print(index_knowledge_to_qdrant(recreate=True))"

shell:
	docker compose exec backend bash
