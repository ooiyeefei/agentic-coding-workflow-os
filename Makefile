UV ?= uv

.PHONY: install test lint type run clean

install:
	$(UV) sync

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .

type:
	$(UV) run pyright

run:
	$(UV) run spanweave --help

clean:
	rm -rf .pytest_cache .ruff_cache .venv build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

