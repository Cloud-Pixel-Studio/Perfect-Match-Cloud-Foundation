SHELL := /usr/bin/env bash
ENV_FILE ?= $(HOME)/.config/pmcloud/dev.env
COMPOSE := docker compose --env-file "$(ENV_FILE)"

.PHONY: configure up down logs health lint typecheck test build security-focused checkpoint

configure:
	./scripts/prepare-local.sh "$(ENV_FILE)"

up: configure
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

health:
	./scripts/health-check.sh "$(ENV_FILE)"

lint:
	cd apps/api && uv run ruff format --check . && uv run ruff check .
	pnpm lint
	shellcheck scripts/*.sh security/opengrep/test-rules.sh

typecheck:
	cd apps/api && uv run mypy src tests
	pnpm typecheck

test:
	cd apps/api && uv run pytest
	pnpm test

build:
	pnpm build
	$(COMPOSE) config --quiet
	$(COMPOSE) build

security-focused:
	./security/opengrep/test-rules.sh
	opengrep scan --config security/opengrep/rules.yml --exclude security/tests/fixtures .
	gitleaks dir --config .gitleaks.toml --redact --no-banner .

checkpoint:
	./scripts/checkpoint.sh "$(ENV_FILE)"
