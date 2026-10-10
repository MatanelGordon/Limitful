SHELL := /bin/sh

.DEFAULT_GOAL := help

.PHONY: help doctor setup build test lint format format-check check clean \
	setup-csharp setup-typescript setup-rust setup-go setup-python \
	build-csharp build-typescript build-rust build-go build-python \
	test-csharp test-typescript test-rust test-go test-python \
	lint-csharp lint-typescript lint-rust lint-go lint-python \
	format-csharp format-typescript format-rust format-go format-python \
	format-check-csharp format-check-typescript format-check-rust \
	format-check-go format-check-python clean-csharp clean-typescript \
	clean-rust clean-go clean-python

help:
	@echo "Limitful monorepo commands"
	@echo "  make doctor        Check required development tools"
	@echo "  make setup         Restore/install every workspace"
	@echo "  make build         Build every package scaffold"
	@echo "  make test          Run every test runner"
	@echo "  make lint          Run every language linter"
	@echo "  make format-check  Verify formatting without changing files"
	@echo "  make format        Format all language workspaces"
	@echo "  make check         Run format-check, lint, build, and test"
	@echo "  make clean         Remove generated build output"
	@echo "Each command also has a -csharp, -typescript, -rust, -go, or -python target."

doctor:
	@for command in dotnet npm cargo go uv; do \
		command -v "$$command" >/dev/null 2>&1 || { echo "Missing required tool: $$command"; exit 1; }; \
	done
	@echo "All required development tools are available."

setup: setup-csharp setup-typescript setup-rust setup-go setup-python

setup-csharp:
	dotnet restore csharp/Limitful.sln

setup-typescript:
	npm --prefix typescript ci

setup-rust:
	cargo fetch --manifest-path rust/Cargo.toml

setup-go:
	go -C go mod download

setup-python:
	uv --directory python sync --all-packages

build: build-csharp build-typescript build-rust build-go build-python

build-csharp:
	dotnet build csharp/Limitful.sln --configuration Release

build-typescript:
	npm --prefix typescript run build

build-rust:
	cargo build --manifest-path rust/Cargo.toml --workspace

build-go:
	go -C go build ./...

build-python:
	uv --directory python build --package limitful --out-dir dist

test: test-csharp test-typescript test-rust test-go test-python

test-csharp:
	dotnet test csharp/Limitful.sln --configuration Release

test-typescript:
	npm --prefix typescript run test

test-rust:
	cargo test --manifest-path rust/Cargo.toml --workspace

test-go:
	go -C go test ./...

test-python:
	uv --directory python run pytest main/tests

lint: lint-csharp lint-typescript lint-rust lint-go lint-python

lint-csharp:
	dotnet format csharp/Limitful.sln --verify-no-changes --verbosity minimal

lint-typescript:
	npm --prefix typescript run lint

lint-rust:
	cargo clippy --manifest-path rust/Cargo.toml --workspace --all-targets -- -D warnings

lint-go:
	go -C go vet ./...

lint-python:
	uv --directory python run ruff check .

format: format-csharp format-typescript format-rust format-go format-python

format-csharp:
	dotnet format csharp/Limitful.sln --verbosity minimal

format-typescript:
	npm --prefix typescript run format

format-rust:
	cargo fmt --manifest-path rust/Cargo.toml --all

format-go:
	find go -type f -name '*.go' -exec gofmt -w {} +

format-python:
	uv --directory python run ruff format .

format-check: format-check-csharp format-check-typescript format-check-rust format-check-go format-check-python

format-check-csharp:
	dotnet format csharp/Limitful.sln --verify-no-changes --verbosity minimal

format-check-typescript:
	npm --prefix typescript run format:check

format-check-rust:
	cargo fmt --manifest-path rust/Cargo.toml --all --check

format-check-go:
	@test -z "$$(find go -type f -name '*.go' -exec gofmt -l {} +)"

format-check-python:
	uv --directory python run ruff format --check .

check: format-check lint build test

clean: clean-csharp clean-typescript clean-rust clean-go clean-python

clean-csharp:
	dotnet clean csharp/Limitful.sln

clean-typescript:
	npm --prefix typescript run clean

clean-rust:
	cargo clean --manifest-path rust/Cargo.toml

clean-go:
	go -C go clean ./...

clean-python:
	$(RM) -r python/dist python/build python/.pytest_cache python/.ruff_cache
	find python -type d -name __pycache__ -prune -exec $(RM) -r {} +
