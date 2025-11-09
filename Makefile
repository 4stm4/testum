.PHONY: help build up down logs test lint clean migrate generate-key

help:
	@echo "Available commands:"
	@echo "  make build          - Build Docker images"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make logs           - View logs"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run linters"
	@echo "  make migrate        - Run database migrations"
	@echo "  make generate-key   - Generate Fernet encryption key"
	@echo "  make clean          - Clean up containers and volumes"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	docker-compose exec app pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	docker-compose exec app flake8 app/ --max-line-length=120 --exclude=__pycache__
	docker-compose exec app black app/ --check

format:
	docker-compose exec app black app/

migrate:
	docker-compose exec app alembic upgrade head

migration:
	docker-compose exec app alembic revision --autogenerate -m "$(MSG)"

generate-key:
	@python3 -c "from cryptography.fernet import Fernet; print('FERNET_KEY=' + Fernet.generate_key().decode())"

clean:
	docker-compose down -v
	rm -rf app/__pycache__ app/*/__pycache__

shell:
	docker-compose exec app /bin/bash

db-shell:
	docker-compose exec db psql -U postgres -d ocultum

redis-cli:
	docker-compose exec redis redis-cli
