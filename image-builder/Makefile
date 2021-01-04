DIST_RELEASE ?= bionic
VERSION ?= 5.6

build-image:
	@echo "Building the image."
	@docker build \
		--no-cache=true \
		--build-arg DIST_RELEASE=$(DIST_RELEASE) \
		--build-arg VERSION=$(VERSION) \
		-t wordpress:$(DIST_RELEASE)-$(VERSION) \
		.
lint: clean
	@echo "Running flake8"
	@tox -e lint

test: lint
	@echo "Running unit tests"
	@tox -e unit

clean:
	@echo "Cleaning files"
	@rm -rf ./.tox
	@rm -rf ./.pytest_cache
	@rm -rf ./files/plugins/*
	@rm -rf ./files/themes/*
	@rm -rf ./files/__pycache__
	@rm -rf ./tests/unit/__pycache__
	@mkdir -p ./files/plugins
	@mkdir -p ./files/themes

.PHONY: build lint clean
