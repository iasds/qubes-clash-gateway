# Contributing to qubes-clash-gateway

Thank you for your interest in contributing! This is an educational project
exploring Qubes OS networking architecture. Contributions that improve
documentation, fix bugs, or add features are welcome.

## Development Setup

### Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- nftables (for testing firewall rules)
- shellcheck (for linting shell scripts)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/iasds/qubes-clash-gateway.git
cd qubes-clash-gateway

# Install with uv (recommended)
uv sync --dev

# Or with pip
pip install -e ".[dev]"
```

### Project Structure

```
├── clashctl/               # Python CLI tool
│   ├── __main__.py         # Entry point
│   ├── api.py              # mihomo REST API client
│   ├── config.py           # Constants, presets, colors
│   ├── data.py             # JSON/YAML file I/O
│   ├── i18n.py             # Internationalization
│   ├── monitor.py          # Health monitoring
│   ├── nodes.py            # Node parsing and speed test
│   ├── parser.py           # Subscription URI parser
│   ├── proxy.py            # Mode switching and service control
│   ├── ui.py               # Terminal UI
│   ├── web.py              # Web UI server
│   └── web_templates/      # HTML templates
├── config/
│   ├── config.yaml         # mihomo config template
│   ├── nftables-proxy.sh   # nftables transparent proxy rules
│   └── sudoers-clashctl    # sudoers config
├── scripts/
│   ├── lib.sh              # Shared shell utilities
│   └── test.sh             # Connectivity test
├── tests/                  # pytest test suite
│   ├── conftest.py         # Fixtures
│   ├── test_config.py      # Config module tests
│   ├── test_data.py        # Data I/O tests
│   ├── test_parser.py      # Subscription parser tests
│   └── test_proxy.py       # Proxy module tests
├── setup.sh                # One-click install
├── install.sh              # Basic install
├── uninstall.sh            # Uninstall
└── pyproject.toml          # Project metadata and tool config
```

## Running Tests

### pytest

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_parser.py

# Run a specific test
uv run pytest tests/test_parser.py::test_parse_vmess_uri

# Run with coverage
uv run pytest --cov=clashctl --cov-report=term-missing
```

The test suite targets 80% code coverage (configured in `pyproject.toml`).

### mypy (Type Checking)

```bash
# Run mypy on the clashctl package
uv run mypy clashctl/

# Or directly
mypy clashctl/
```

Configuration in `pyproject.toml`:
- `python_version = "3.8"` — minimum supported Python
- `ignore_missing_imports = true` — third-party stubs not required
- `check_untyped_defs = true` — checks functions without type hints

### shellcheck (Shell Linting)

```bash
# Lint all shell scripts
shellcheck setup.sh install.sh uninstall.sh config/nftables-proxy.sh scripts/*.sh

# With baseline (known issues)
shellcheck -S warning --shellcheck-baseline=shellcheck-baseline.txt *.sh scripts/*.sh
```

The `shellcheck-baseline.txt` file records known issues that are intentionally
accepted. When fixing a baseline issue, remove it from the file.

### Run All Checks

```bash
# Quick check before committing
uv run pytest -v && uv run mypy clashctl/ && shellcheck -S warning config/*.sh scripts/*.sh setup.sh install.sh uninstall.sh
```

## Code Style

### Python

- **PEP 8** — Follow the standard Python style guide
- **Line length** — 100 characters (soft limit)
- **Type hints** — Use type annotations for function signatures where practical
- **Docstrings** — All public functions must have docstrings (Google style)
- **Imports** — Group: stdlib, third-party, local. Sort alphabetically within groups

Example:

```python
"""Module docstring describing purpose."""

import json
import os
from typing import Any, Dict, Optional

from .config import API_BASE, C_GREEN


def get_status(name: str, verbose: bool = False) -> Dict[str, Any]:
    """Get the status of a named resource.

    Args:
        name: The resource name to query.
        verbose: If True, include detailed information.

    Returns:
        Dict with keys: name, status, details (if verbose).
    """
    result: Dict[str, Any] = {"name": name, "status": "ok"}
    if verbose:
        result["details"] = {}
    return result
```

### Shell Scripts

- **ShellCheck clean** — All scripts must pass shellcheck with `-S warning`
- **Use `set -euo pipefail`** — At the top of every script
- **Source `scripts/lib.sh`** — For shared utilities (colors, logging, error handling)
- **Quote variables** — Use `"$var"` everywhere, never bare `$var`
- **Use functions** — Break scripts into reusable functions

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` — New feature
- `fix` — Bug fix
- `docs` — Documentation only
- `style` — Code style (formatting, no logic change)
- `refactor` — Code restructuring (no behavior change)
- `test` — Adding or updating tests
- `chore` — Build, CI, tooling changes

**Examples:**
```
feat(parser): add wireguard URI support
fix(proxy): handle empty proxy list in apply_mode
docs(architecture): add Kill Switch flow diagram
test(parser): add trojan URI edge cases
chore(ci): add shellcheck to pre-commit
```

## Pull Request Workflow

### 1. Fork and Branch

```bash
# Fork on GitHub, then:
git clone https://github.com/<your-user>/qubes-clash-gateway.git
cd qubes-clash-gateway
git remote add upstream https://github.com/iasds/qubes-clash-gateway.git

# Create a feature branch
git checkout -b feat/my-feature
```

### 2. Make Changes

- Write code following the style guide above
- Add tests for new functionality
- Update documentation if behavior changes
- Keep commits atomic (one logical change per commit)

### 3. Verify

```bash
# Run tests
uv run pytest -v

# Type check
uv run mypy clashctl/

# Shell lint
shellcheck -S warning config/*.sh scripts/*.sh setup.sh install.sh uninstall.sh

# Manual smoke test (on a Qubes NetVM if possible)
clashctl /status
clashctl /help
```

### 4. Submit

```bash
git push origin feat/my-feature
```

Open a pull request against `main` on GitHub.

### 5. Review

A maintainer will review your PR. Common feedback:
- Missing tests
- Style inconsistencies
- Security concerns (especially around nftables rules)
- Documentation gaps

## Review Checklist

Before submitting a PR, verify:

- [ ] **Tests pass** — `uv run pytest` exits 0
- [ ] **Type check passes** — `uv run mypy clashctl/` exits 0
- [ ] **ShellCheck passes** — No new warnings
- [ ] **Docstrings** — All new public functions have docstrings
- [ ] **No hardcoded paths** — Use constants from `config.py`
- [ ] **Idempotent rules** — nftables scripts can be re-run safely
- [ ] **Kill Switch intact** — nftables changes don't create traffic leaks
- [ ] **Persistence considered** — New files go under `/rw/config/clash/` if they need to survive reboots
- [ ] **Commit messages** — Follow Conventional Commits format
- [ ] **Documentation updated** — README, docs/, or inline comments as needed

## Security Considerations

This project handles network traffic routing and firewall rules. Extra care is
needed for:

- **nftables rules** — Any change to `nftables-proxy.sh` must be reviewed for
  traffic leaks. The Kill Switch must remain functional. Test by stopping mihomo
  and verifying all AppVM traffic is blocked.
- **Port exclusions** — Adding new mihomo ports requires updating both the
  prerouting exclusion list AND the forward chain accept rules.
- **DNS handling** — Changes to DNS rules can create loops. Always test that
  mihomo's own DNS queries are not intercepted.
- **Subscription parsing** — User-supplied URLs are fetched and parsed. The
  parser must handle malformed input gracefully without crashes.

## Getting Help

- **Issues** — Open a GitHub issue for bugs or feature requests
- **Telegram** — [Qubes OS Chinese Community](https://t.me/qubeszh)
- **Security** — For security-sensitive issues, contact the maintainer directly

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](../LICENSE).
