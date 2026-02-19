.PHONY: mypy sync-requirements test

mypy:
	uv run mypy src/tannhauser

sync-requirements:
	uv add -r requirements.txt
	uv add --dev -r requirements-dev.txt

test:
	uv run pytest --cov=tannhauser tests/
