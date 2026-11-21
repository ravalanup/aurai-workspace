# Contributing

- Python 3.11+. `pip install -e ".[dev]"`, then `ruff check .`, `ruff format --check .` and `pytest` before opening a pull request.
- Realm changes: edit `realm/aurai-realm.yaml`, run `aurai-workspace validate`, and `plan` against a dev Keycloak before `apply`. Never put passwords or secrets in the file; they come from environment variables.
- Open WebUI functions are single files with a metadata header; keep them dependency-light and covered by tests in `tests/`.
- Contract changes (`contracts/`) affect `aurai-knowledge-rag`: change the OpenAPI file, the tool and the tests together, and say so in the pull request.
- Charts and values: no secrets in templates; credentials come from Kubernetes Secrets. Run `helm lint` and `helm template` when Helm is available.
- No real names, customer data or credentials. People and teams in examples are fictional.
- Use clear, imperative commit messages.
