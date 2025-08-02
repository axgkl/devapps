# devapps


<!-- badges -->
[![docs pages][docs pages_img]][docs pages] [![gh-ci][gh-ci_img]][gh-ci] [![pkg][pkg_img]][pkg] [![code_style][code_style_img]][code_style] 

[docs pages]: https://axgkl.github.io/devapps/
[docs pages_img]: https://axgkl.github.io/devapps/img/badge_docs.svg
[gh-ci]: https://github.com/AXGKl/devapps/actions/workflows/ci.yml
[gh-ci_img]: https://github.com/AXGKl/devapps/actions/workflows/ci.yml/badge.svg
[pkg]: https://pypi.com/
[pkg_img]: https://axgkl.github.io/devapps/img/badge_pypi.svg
[code_style]: https://github.com/astral-sh/ruff
[code_style_img]: https://axgkl.github.io/devapps/img/badge_ruff.svg
<!-- badges -->


Enabler repo for dev *and* ops friendly apps, in a normalized way.

Includes:

- logging (structlog)
- cli flags handling (abseil, with addons)
- docutools (mkdocs-material)
- project setup
- (test) resources management, including daemons and container filesystem layers

and more.




Documentation: https://axgkl.github.io/devapps/

## Update 2025-07: Installation

### Modern Installation (Recommended)

For development and contribution, we now support modern tooling:

- **[uv](https://docs.astral.sh/uv/)** for fast Python package and project management
- **[just](https://just.systems/)** for convenient command running

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just (if not already installed) 
# macOS:
brew install just
# Or see: https://just.systems/man/en/chapter_1.html

# Clone and setup
git clone https://github.com/axgkl/devapps.git
cd devapps
uv sync --extra dev

# Available commands
just --list
```

### Legacy Installation

⚠️ **Note**: Documentation still shows installation using bash scripts and poetry/conda. The modern uv + just approach above is now preferred for development.