.PHONY: tests help install venv lint dstart isort tcheck build commit-checks prepare distcheck pypibuild pypipush update-all-dockerhub-readmes
SHELL := /usr/bin/bash
.ONESHELL:


help:
	@printf "\ninstall\n\tinstall requirements\n"
	@printf "\nisort\n\tmake isort import corrections\n"
	@printf "\nlint\n\tmake linter check with black\n"
	@printf "\ntcheck\n\tmake static type checks with mypy\n"
	@printf "\ntests\n\tLaunch tests\n"
	@printf "\nprepare\n\tLaunch tests and commit-checks\n"
	@printf "\ncommit-checks\n\trun pre-commit checks on all files\n"
	@printf "\pypibuild \n\tbuild image package for pypi\n"
	@printf "\pypipush \n\push package to pypi\n"
	@printf "\nupdate-all-dockerhub-readmes \n\tupdate Docker Hub repo description from DOCKERHUB_OVERVIEW.md\n"
	@printf "\nbuild \n\tbuild docker image\n"
	@printf "\ndstart \n\tlaunch \"app\" in docker\n"




# check for "CI" not in os.environ || "GITHUB_RUN_ID" not in os.environ
venv_activated=if [ -z $${VIRTUAL_ENV+x} ] && [ -z $${GITHUB_RUN_ID+x} ] ; then printf "activating venv...\n" ; source .venv/bin/activate ; else printf "venv already activated or GITHUB_RUN_ID=$${GITHUB_RUN_ID} is set\n"; fi

install: venv

venv: .venv/touchfile

.venv/touchfile: requirements.txt requirements-dev.txt requirements-build.txt
	@if [ -z "$${GITHUB_RUN_ID}" ]; then \
		test -d .venv || python3.14 -m venv .venv; \
		source .venv/bin/activate; \
		pip install -r requirements-build.txt; \
		touch .venv/touchfile; \
	else \
  		echo "Skipping venv setup because GITHUB_RUN_ID is set"; \
  	fi


tests: venv
	@$(venv_activated)
	pytest .

lint: venv
	@$(venv_activated)
	black -l 120 .

isort: venv
	@$(venv_activated)
	isort .

tcheck: venv
	@$(venv_activated)
	mypy *.py scripts mqttcommander


.git/hooks/pre-commit: venv
	@$(venv_activated)
	pre-commit install

commit-checks: .git/hooks/pre-commit
	@$(venv_activated)
	pre-commit run --all-files

prepare: tests commit-checks

mqttcommander_SOURCES := mqttcommander/*.py
VENV_DEPS := requirements.txt requirements-dev.txt requirements-build.txt

# VERSION := $(shell egrep -m 1 ^version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | tr -d " " | cut -d'=' -f2)
# VERSION := $(shell echo ${venv_activated} && hatch version)
VERSION := $(shell $(venv_activated) > /dev/null 2>&1 && hatch version 2>/dev/null || echo HATCH_NOT_FOUND)

echo:
	@printf "$(VERSION)\n"

dist/mqttcommander-$(VERSION).tar.gz dist/mqttcommander-$(VERSION)-py3-none-any.whl dist/.touchfile: $(mqttcommander_mqttcommander) $(VENV_DEPS) pyproject.toml
	@$(venv_activated)
	echo VERSION: $(VERSION)
	hatch build --clean
	@touch dist/.touchfile


# Refuses to let a build artifact leave the machine if it carries a git-crypt
# protected path (those are PLAINTEXT in the working tree) or any file outside
# the allowlist that pyproject.toml declares. Gates `pypibuild` and `pypipush`.
distcheck: venv dist/mqttcommander-$(VERSION).tar.gz dist/mqttcommander-$(VERSION)-py3-none-any.whl
	@$(venv_activated)
	python scripts/check_dist_secrets.py

pypibuild: distcheck

dist/.touchfile_push: dist/mqttcommander-$(VERSION).tar.gz dist/mqttcommander-$(VERSION)-py3-none-any.whl
	@$(venv_activated)
	$(MAKE) distcheck
	hatch publish -r main
	@touch dist/.touchfile_push

pypipush: venv dist/.touchfile_push

build: venv
	./build.sh

dstart:
	# map config.local.yaml from current workdirectory into container
	docker run --network=host -it --rm --name mqttcommanderephemeral -v $$(pwd)/config.local.yaml:/app/config.local.yaml xomoxcc/mqttcommander:latest /bin/bash

update-all-dockerhub-readmes:
	@AUTH=$$(jq -r '.auths["https://index.docker.io/v1/"].auth' ~/.docker/config.json | base64 -d) && \
	USERNAME=$$(echo "$$AUTH" | cut -d: -f1) && \
	PASSWORD=$$(echo "$$AUTH" | cut -d: -f2-) && \
	TOKEN=$$(curl -s -X POST https://hub.docker.com/v2/users/login/ \
	  -H "Content-Type: application/json" \
	  -d '{"username":"'"$$USERNAME"'","password":"'"$$PASSWORD"'"}' \
	  | jq -r .token) && \
	for mapping in \
	  ".:xomoxcc/mqttcommander"; do \
	  DIR=$$(echo "$$mapping" | cut -d: -f1) && \
	  REPO=$$(echo "$$mapping" | cut -d: -f2) && \
	  FILE="$$DIR/DOCKERHUB_OVERVIEW.md" && \
	  if [ -f "$$FILE" ]; then \
	    echo "Updating $$REPO from $$FILE..." && \
	    curl -s -X PATCH "https://hub.docker.com/v2/repositories/$$REPO/" \
	      -H "Authorization: Bearer $$TOKEN" \
	      -H "Content-Type: application/json" \
	      -d "{\"full_description\": $$(jq -Rs . "$$FILE")}" \
	      | jq -r '.full_description | length | "  Updated: \(.) chars"'; \
	  else \
	    echo "Skipping $$REPO - $$FILE not found"; \
	  fi; \
	done
# From https://hatch.pypa.io/latest/publish/#authentication
# HATCH_INDEX_USER and HATCH_INDEX_AUTH

# UPLOAD (old twine):
# python3 -m twine upload --repository testpypi dist/*

# UPLOAD to pypitest with hatch:
# hatch publish -r test

# UPLOAD to pypi(main) with hatch:
# hatch publish -r main

# INSTALL from test
# python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps example-package-YOUR-USERNAME-HERE

# INSTALL from test (if not found on pypitest -> install from normal pypi
# python3 -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ mqttcommander==0.0.1

# INSTALL from pypi(main)
# python3 -m pip install mqttcommander==0.0.1


