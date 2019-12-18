lint:
	@echo "Normalising python layout with black."
	@tox -e black
	@echo "Running flake8"
	@tox -e lint

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
