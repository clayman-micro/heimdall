.PHONY: build clean clean-test clean-pyc clean-build proto

NAME	:= ghcr.io/clayman-micro/heimdall
VERSION ?= latest


clean: clean-build clean-image clean-pyc clean-test

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-image:
	docker images -qf dangling=true | xargs docker rmi

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test:
	rm -fr .tox/
	rm -f .coverage
	rm -fr tests/coverage
	rm -f tests/coverage.xml

install: clean
	poetry install

lint:
	poetry run flake8 src/heimdall tests
	poetry run mypy src/heimdall tests

run:
	poetry run python3 -m heimdall --conf-dir=./conf --debug server run --host=0.0.0.0 \
		-t 'develop' \
		-t 'traefik.enable=true' \
		-t 'traefik.http.routers.heimdall.rule=Host(`wallet.dev.clayman.pro`, `shortner.dev.clayman.pro`, `passport.dev.clayman.pro`)' \
		-t 'traefik.http.routers.heimdall.entrypoints=web' \
		-t 'traefik.http.routers.heimdall.service=heimdall' \
		-t 'traefik.http.routers.heimdall.middlewares=heimdall-redirect@consulcatalog' \
		-t 'traefik.http.routers.heimdall-secure.rule=Host(`wallet.dev.clayman.pro`, `shortner.dev.clayman.pro`, `passport.dev.clayman.pro`)' \
		-t 'traefik.http.routers.heimdall-secure.entrypoints=websecure' \
		-t 'traefik.http.routers.heimdall-secure.service=heimdall' \
		-t 'traefik.http.routers.heimdall-secure.tls=true' \
		-t 'traefik.http.middlewares.heimdall-redirect.redirectscheme.scheme=https' \
		-t 'traefik.http.middlewares.heimdall-redirect.redirectscheme.permanent=true'

test:
	tox

dist: clean-build
	poetry build

build:
	docker build -t ${NAME} .
	docker tag ${NAME} ${NAME}:$(VERSION)

publish: build
	docker login -u $(DOCKER_USER) -p $(DOCKER_PASS) ghcr.io
	docker push ${NAME}:$(VERSION)

deploy:
	docker run --rm -it -v ${PWD}:/github/workspace --workdir /github/workspace \
		-e HEIMDALL_VERSION=$(VERSION) \
		-e VAULT_ADDR=$(VAULT_ADDR) \
		-e VAULT_ROLE_ID=$(VAULT_ROLE_ID) \
		-e VAULT_SECRET_ID=$(VAULT_SECRET_ID) \
		ghcr.io/clayman-micro/action-deploy -i ansible/inventory ansible/deploy.yml
