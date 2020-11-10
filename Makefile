wordpress.charm: src/*.py requirements.txt
	@echo "Building Kubernetes WordPress Charm."
	@charmcraft build

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
	@rm -r ./build || true

.PHONY: format lint test unittest integration clean
