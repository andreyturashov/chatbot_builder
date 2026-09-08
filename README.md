# AI Chatbot Builder

[![CI & Coverage](https://github.com/andreyturashov/chatbot_builder/actions/workflows/ci.yml/badge.svg)](https://github.com/andreyturashov/chatbot_builder/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/andreyturashov/chatbot_builder/graph/badge.svg?token=)](https://codecov.io/gh/andreyturashov/chatbot_builder)

A modern platform for automatically generating smart business chatbots from raw visual and textual artifacts (screenshots, menus, price lists, PDFs, presentations, chat logs).

---

## Architecture Overview

- **Main API (`services/api`)**: FastAPI service managing users, bots, scenarios, corrections, deployments, and live RAG chat runtime.
- **Processing Service (`services/processor`)**: FastAPI service handling multimodal file ingestion (Vision LLM, OCR, PDF parsing), semantic chunking, embeddings, and scenario generation.
- **Events Bus**: Redis Streams for persistent event-driven service communication.
- **Databases**: PostgreSQL 16 with `pgvector` per service.
- **Storage**: MinIO / S3 for uploaded assets.

---

## Quickstart

### 1. Prerequisites
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker & Docker Compose

### 2. Available Make Commands

```bash
# View all commands
make help

# Sync and install dependencies
make sync

# Run tests with 100% coverage
make test

# Start the Main API service locally
make run-api

# Start backing infrastructure (Postgres with pgvector, Redis)
make docker-up
```
