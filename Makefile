lint:
	black -l 120 -t py37 reactive/
	flake8 reactive/

build: lint
	charm build --no-local-layers
