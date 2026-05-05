# Copilot Instructions for wordpress-k8s-operator

## Build, Test, and Lint

This project uses `tox` (with `uv` backend) for all development tasks. Install prerequisites:

```bash
uv python install
uv tool install tox --with tox-uv
```

Commands:

```bash
tox                      # Run all checks: lint, unit, static, coverage-report
tox -e fmt               # Auto-format code with ruff
tox -e lint              # Lint (codespell + ruff format check + ruff check + mypy)
tox -e unit              # Run unit tests with coverage
tox -e static            # Security analysis with bandit
tox -e integration       # Integration tests (requires Juju + MicroK8s)
```

Run a single unit test:

```bash
tox -e unit -- tests/unit/test_charm.py::test_function_name
```

Run a single integration test:

```bash
tox -e integration -- tests/integration/test_core.py::test_function_name
```

Build the charm:

```bash
charmcraft pack
```

## Architecture

This is a **Juju Kubernetes charm** that deploys WordPress in a sidecar container pattern using the `ops` framework.

### Core Components

- **`src/charm.py`** — Main charm class (`WordpressCharm`). Contains all event handlers, reconciliation logic, and WordPress management (WP-CLI interactions, plugin/theme management, database setup). Uses a single `_reconciliation` method as the convergence handler for most events.
- **`src/state.py`** — Charm state module using pydantic for validation. Extracts and validates configuration from the Juju model (e.g., proxy settings).
- **`src/cos.py`** — COS (Canonical Observability Stack) integration: Prometheus scraping, Loki log forwarding, Grafana dashboards.
- **`src/exceptions.py`** — Custom exceptions that map to Juju status changes (`BlockedStatus`, `WaitingStatus`, `MaintenanceStatus`). Raising these exceptions during reconciliation sets the unit status and terminates the current event handler early.
- **`src/types_.py`** — Internal named tuples for command execution results and database configuration.

### Charm Libraries (lib/charms/)

Vendored charm libraries providing interfaces for integrations: `data_platform_libs` (MySQL), `grafana_k8s`, `loki_k8s`, `nginx_ingress_integrator`, `prometheus_k8s`, `observability_libs`.

### Key Relations

- `database` — MySQL client interface (required)
- `nginx-route` — Ingress via nginx-ingress-integrator
- `wordpress-replica` — Peer relation for leader-elected consensus (shared secrets/salts)
- `metrics-endpoint`, `grafana-dashboard`, `logging` — COS observability stack

### Testing Structure

- **Unit tests** (`tests/unit/`) — Use `ops.testing.Harness` with a mock system (`wordpress_mock.py`) that simulates the WordPress container filesystem and database.
- **Integration tests** (`tests/integration/`) — Use `pytest-operator` to deploy the charm against a real Juju/K8s cluster.

## Key Conventions

- **Reconciliation pattern**: Most events funnel into `_reconciliation()` which brings the charm to the desired state idempotently. Status exceptions control early termination.
- **Copyright headers**: All Python files must start with `# Copyright <year> Canonical Ltd.` and `# See LICENSE file for licensing details.`
- **Docstrings**: Google-style pydocstrings are enforced by ruff (`D` rules). Use `Args:`, `Returns:`, `Raises:`, `Attrs:` sections.
- **Line length**: 99 characters max.
- **Python target**: 3.10+ (no newer syntax sugar like `X | Y` union types due to ruff UP ignores).
- **Test docstrings**: Follow `arrange/act/assert` pattern in test docstrings describing the test scenario.
- **Coverage**: Minimum 90% coverage is enforced on unit tests.
- **CHANGELOG.md**: Must be updated for any new feature, fix, or significant change.
