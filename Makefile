lint:
	black -l 120 -t py37 reactive/
	flake8 reactive/

unittest:
	@tox -e unit

test: lint unittest

build: lint
	charm build

clean:
	@echo "Cleaning files"
	@rm -rf ./.tox
	@rm -rf ./.pytest_cache
	@rm -rf ./tests/unit/__pycache__ ./reactive/__pycache__ ./lib/__pycache__
	@rm -rf ./.coverage ./.unit-state.db


.PHONY: lint test unittest build clean
