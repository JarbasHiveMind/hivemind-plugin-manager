# Contributing

## Repository

`https://github.com/JarbasHiveMind/hivemind-plugin-manager`

Default branch: `dev`. Pull requests target `dev`, not `master`.

---

## Setup

```bash
git clone https://github.com/JarbasHiveMind/hivemind-plugin-manager
cd hivemind-plugin-manager
git checkout dev
pip install -e ".[dev]"          # or: pip install -e . && pip install pytest pytest-cov
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests live in `tests/`:

| File | What it covers |
|---|---|
| `tests/test_database.py` | `Client`, `cast2client`, `AbstractDB`, `AbstractRemoteDB` |
| `tests/test_factories.py` | all four factories, `find_plugins`, `HiveMindPluginTypes` |
| `tests/test_protocols.py` | `ClientCallbacks`, `AgentProtocol`, `NetworkProtocol`, `BinaryDataHandlerProtocol` |

---

## Coverage Gate

The CI coverage workflow enforces a minimum of **70 % line coverage**. Check before opening
a PR:

```bash
pytest tests/ --cov=hivemind_plugin_manager --cov-report=term-missing
```

---

## CI Workflows

All workflows are in `.github/workflows/`. They use reusable workflows from
`OpenVoiceOS/gh-automations@dev`.

| Workflow file | Trigger | Purpose |
|---|---|---|
| `build_tests.yml` | push / PR | run `pytest` across Python versions |
| `coverage.yml` | push / PR | measure coverage, fail below threshold |
| `lint.yml` | push / PR | `flake8` / `pylint` style checks |
| `license_check.yml` | push / PR | verify all dependencies are permissively licensed |
| `pip_audit.yml` | push / PR | scan for known vulnerabilities in dependencies |
| `conventional-label.yaml` | PR open/edit | auto-label PRs by conventional-commit prefix |
| `repo-health.yml` | schedule | general repository health checks |
| `release-preview.yml` | push to `dev` | publish an alpha pre-release |
| `release_workflow.yml` | manual / tag | cut a versioned release |
| `publish_stable.yml` | release published | publish to PyPI |

---

## Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <short description>

feat(database): add AbstractRemoteDB password rotation helper
fix(factory): raise KeyError with available plugin list
docs: add binary protocol guide
test(protocols): cover BinaryDataHandlerProtocol post_init branch
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.

The `conventional-label.yaml` workflow auto-labels PRs based on the commit prefix.

---

## Versioning

Version is read from `hivemind_plugin_manager/version.py`:

```python
VERSION_MAJOR = 0
VERSION_MINOR = 4
VERSION_BUILD = 1
VERSION_ALPHA = 1   # 0 = stable release
```

Source: `hivemind_plugin_manager/version.py:1`

`setup.py:7` assembles the version string as `{MAJOR}.{MINOR}.{BUILD}` with an `a{ALPHA}`
suffix when `VERSION_ALPHA > 0`.

Bump the appropriate component in `version.py` before opening a release PR.

---

## Adding a New Plugin Type

If a future HiveMind version requires a fifth plugin type:

1. Add a new member to `HiveMindPluginTypes` in `__init__.py:10`.
2. Create a new abstract base dataclass in either `database.py` or `protocols.py`.
3. Add a new factory class following the pattern of `DatabaseFactory` (`__init__.py:17`).
4. Add tests in a new `tests/test_<type>.py` file.
5. Update `docs/README.md`, `docs/concepts.md`, and add a new `docs/plugins/<type>.md`.
