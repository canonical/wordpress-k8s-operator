format:
	@echo "Normalising python layout with black."
	@tox -e black

lint:
	@echo "Running flake8"
	@tox -e lint

integration:
	@echo "Running integration"
	@export WORKSPACE=${WORKSPACE}
	@tox -e integration

unittest:
	@tox -e unit

test: lint unittest clean

clean:
	@echo "Cleaning files"
	@git clean -fXd || true
	@rm -r /tmp/charm-k8s-wordpress/.tox

.PHONY: format lint test unittest integration clean
