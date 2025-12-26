.PHONY: up down logs test clean help

# Default target
help:
	@echo "Available targets:"
	@echo "  make up     - Start the services with docker-compose"
	@echo "  make down   - Stop and remove containers and volumes"
	@echo "  make logs   - Follow container logs"
	@echo "  make test   - Run tests (if any)"
	@echo "  make clean  - Clean up all containers, volumes, and images"

# Start docker-compose services
up:
	docker compose up -d --build

# Stop and remove containers and volumes
down:
	docker compose down -v

# Follow logs
logs:
	docker compose logs -f api

# Run tests (placeholder - add your tests here)
test:
	@echo "Running tests..."
	@echo "No tests configured yet. Add your test commands here."

# Clean everything
clean:
	docker compose down -v
	docker system prune -f
