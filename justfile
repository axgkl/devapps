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

# Lint code with ruff. Todo...
lint:
    uv run ruff check .

# Fix linting issues automatically. A lot todo...
lint-fix:
    uv run ruff check --fix .

# Type check with pyright
typecheck:
    uv run pyright

# Check git status - fail if uncommitted changes
git-status:
    #!/usr/bin/env bash
    if [[ -n $(git status --porcelain) ]]; then
        echo "❌ Error: You have uncommitted changes. Commit or stash them before release."
        git status --short
        exit 1
    fi

# Clean build artifacts
clean:
    rm -rf dist/
    rm -rf build/
    rm -rf *.egg-info/
    find . -type d -name __pycache__ -delete
    find . -type f -name "*.pyc" -delete

# Run all checks (lint, format check, type check, tests)
#check: lint typecheck test
check: typecheck test

# Create git tag with version from pyproject.toml
tag:
    #!/usr/bin/env bash
    VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
    echo "Creating git tag $VERSION"
    git tag "$VERSION"
    git push origin "$VERSION"

# Prepare for release (clean, check, build, tag)
release: git-status clean check build tag publish
