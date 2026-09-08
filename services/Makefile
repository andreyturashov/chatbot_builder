# ==============================================================================
# Services Makefile - Local Development Commands
# ==============================================================================

SHELL := /bin/bash
ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
SERVICES_DIR := $(ROOT_DIR)/services
API_DIR := $(SERVICES_DIR)/api
DOCKER_COMPOSE := docker compose -f $(ROOT_DIR)/docker-compose.yml

.PHONY: help install sync run-api test-api test lint format check pre-commit docker-up docker-down docker-logs clean

# Default target: help
help: ## Display this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(SERVICES_DIR)/Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ------------------------------------------------------------------------------
# Dependency Management (uv)
# ------------------------------------------------------------------------------
sync: ## Sync dependencies for all services using uv
	@echo "==> Syncing dependencies in services/api..."
	@cd $(API_DIR) && uv sync

install: sync ## Alias for sync

# ------------------------------------------------------------------------------
# Local Service Runners
# ------------------------------------------------------------------------------
run-api: ## Run the Main API service locally with auto-reload (port 8000)
	@echo "==> Starting Main API service at http://localhost:8000 (docs at /docs)..."
	@cd $(API_DIR) && uv run uvicorn app.main:app --reload --port 8000

# ------------------------------------------------------------------------------
# Testing & Quality Assurance
# ------------------------------------------------------------------------------
test-api: ## Run unit tests for services/api
	@echo "==> Running tests in services/api..."
	@cd $(API_DIR) && uv run pytest

test: test-api ## Run all tests across all services

lint: ## Run Ruff linter on all services
	@echo "==> Checking code style with Ruff..."
	@cd $(API_DIR) && uv run ruff check .

format: ## Format and auto-fix code style with Ruff
	@echo "==> Formatting code with Ruff..."
	@cd $(API_DIR) && uv run ruff check --fix .
	@cd $(API_DIR) && uv run ruff format .

check: lint test ## Run all linting and test checks

pre-commit: ## Run all pre-commit hooks across the repository
	@echo "==> Running pre-commit hooks..."
	@cd $(ROOT_DIR) && pre-commit run --all-files

# ------------------------------------------------------------------------------
# Docker Infrastructure
# ------------------------------------------------------------------------------
docker-up: ## Start backing infrastructure (PostgreSQL pgvector, Redis)
	@echo "==> Starting Docker containers..."
	@$(DOCKER_COMPOSE) up -d

docker-down: ## Stop backing infrastructure containers
	@echo "==> Stopping Docker containers..."
	@$(DOCKER_COMPOSE) down

docker-logs: ## Tail logs from Docker containers
	@$(DOCKER_COMPOSE) logs -f

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------
clean: ## Remove temporary cache and build files
	@echo "==> Cleaning cache directories..."
	@find $(ROOT_DIR) -type d -name "__pycache__" -exec rm -rf {} +
	@find $(ROOT_DIR) -type d -name ".pytest_cache" -exec rm -rf {} +
	@find $(ROOT_DIR) -type d -name ".ruff_cache" -exec rm -rf {} +
	@find $(ROOT_DIR) -type d -name ".mypy_cache" -exec rm -rf {} +
	@echo "==> Clean complete."
