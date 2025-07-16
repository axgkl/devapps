# justfile for devapps project

# Default recipe to list available commands
default:
    @just --list

# Run ops command with arguments
ops *args:
    uv run ops {{args}}

# Run tests with pytest
test *args:
    uv run pytest tests {{args}}

# Build the package
build:
    uv build

# Publish to PyPI using pass for token
publish:
    uv publish --token "$(pass pypitoken)"

# Install/sync dependencies
sync:
    uv sync

# Install with dev dependencies
sync-dev:
    uv sync --extra dev

# Format code with ruff
format:
    uv run ruff format .

# Lint code with ruff
lint:
    uv run ruff check .

# Fix linting issues automatically
lint-fix:
    uv run ruff check --fix .

# Type check with pyright
typecheck:
    uv run pyright

# Clean build artifacts
clean:
    rm -rf dist/
    rm -rf build/
    rm -rf *.egg-info/
    find . -type d -name __pycache__ -delete
    find . -type f -name "*.pyc" -delete

# Run all checks (lint, format check, type check, tests)
check: lint typecheck test

# Prepare for release (clean, check, build)
release: clean check build
