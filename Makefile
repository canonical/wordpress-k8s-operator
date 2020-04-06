lint:
	@echo "Normalising python layout with black."
	@tox -e black
	@echo "Running flake8"
	@tox -e lint

unittest:
	@tox -e unit -vvv

test: lint unittest

clean:
	@echo "Cleaning files"
	@git clean -fXd

.PHONY: lint test unittest clean
