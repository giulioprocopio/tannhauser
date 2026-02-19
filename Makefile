.PHONY: sync-requirements

sync-requirements:
	uv add -r requirements.txt
	uv add --dev -r requirements-dev.txt
