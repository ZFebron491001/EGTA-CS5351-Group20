# Debt Register

Known technical and process debt, with impact and the condition under which each
entry expires. Owner identifiers follow the A–E role map in `execution_plan_261111.md`.

| ID | Category | Description | Impact | Opened | Expiry condition | Status |
|---|---|---|---|---|---|---|
| DEBT-D1 | Reproducibility debt | The project Conda env `egta` is now established and version-recorded (Python 3.12.16, pydantic 2.14.4, pytest 9.2.0, ruff 0.17.6); `pydantic` is still **not pinned by a lock file** (arrives transitively via `langchain-core`/`langgraph`). The earlier `/tmp/egta-venv` evidence is superseded. | Residual risk limited to version drift of transitive deps: a pass in `egta` is reproducible only while the unpinned transitive versions match. The pydantic/lock gap is resolved before G0. | 2026-11-20 | Remaining (pinning) part must be resolved before the **G0** gate by adding a lock (`pip-compile`/`uv lock`/`conda env export`) and committing it. Owner: E, with environment setup on the human side. | Partially resolved (env established + versions recorded; pydantic lock pending) |
