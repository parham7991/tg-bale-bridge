.PHONY: help install dev test lint run login docker-build docker-up clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime dependencies
	pip install -r requirements.txt

dev:  ## Install runtime + dev dependencies
	pip install -r requirements.txt -r requirements-dev.txt

test:  ## Run the test suite
	pytest -q

lint:  ## Lint with ruff
	ruff check .

run:  ## Start the bridge
	python main.py

login:  ## One-time Telegram session login
	python login.py

docker-build:  ## Build the docker image
	docker compose build

docker-up:  ## Start with docker compose
	docker compose up -d

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache __pycache__ */__pycache__ *.egg-info dist build
