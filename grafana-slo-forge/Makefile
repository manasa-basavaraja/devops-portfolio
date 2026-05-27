.PHONY: help install test lint generate up down apply-checkout

PYTHON ?= python

help:
	@echo "Targets:"
	@echo "  install         install python deps"
	@echo "  test            run pytest"
	@echo "  generate        write rules + dashboard for both example specs into out/"
	@echo "  up              start prometheus + grafana via docker compose"
	@echo "  down            stop the docker compose stack"
	@echo "  apply-checkout  push checkout-api dashboard to local grafana"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

generate:
	$(PYTHON) -m src.cli generate examples/checkout-api.yaml --out-dir out/
	$(PYTHON) -m src.cli generate examples/payments-api.yaml --out-dir out/

up:
	docker compose up -d
	@echo "Prometheus:  http://localhost:9090"
	@echo "Grafana:     http://localhost:3000  (admin / admin)"

down:
	docker compose down

# Convenience: wraps `apply` for the bundled example. Expects GRAFANA_TOKEN
# to be set, or omit it entirely against an unauthenticated local grafana.
apply-checkout:
	$(PYTHON) -m src.cli apply examples/checkout-api.yaml \
		--grafana-url $${GRAFANA_URL:-http://localhost:3000} \
		--grafana-token $${GRAFANA_TOKEN:-} \
		--rules-out out/checkout-api.rules.yaml
