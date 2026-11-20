# Baseline Record

Baseline and environment record for EGTA-CS5351-Group20, so every later result can
be tied to a fixed upstream version and a reproducible environment (NFR-08).

## Upstream repository

- Repository: `TauricResearch/TradingAgents`
- Upstream URL: https://github.com/TauricResearch/TradingAgents
- Locked commit SHA: `9fa1196fffbcfd9de5146d2dd2869df84ab99838` (`9fa1196`)
- Upstream version (`tradingagents.__version__`): `0.7.1`
- How the SHA was obtained:
  ```
  $ git rev-parse upstream/main
  9fa1196fffbcfd9de5146d2dd2869df84ab99838
  $ git rev-parse main
  9fa1196fffbcfd9de5146d2dd2869df84ab99838
  ```
  `main` and `upstream/main` point at the same commit at the time of recording, so
  the project baseline is that exact upstream commit. (Links to upstream source
  elsewhere should reference this SHA for permanence rather than `main`.)

## Project environment

- Conda env: `egta` (Python 3.12.16) at `/root/miniconda3/envs/egta`
- Installed tooling versions:
  - Python `3.12.16`
  - pydantic `2.14.4`
  - pytest `9.2.0`
  - ruff `0.17.6`
- Installation method:
  ```
  conda create -n egta python=3.12 -y
  conda activate egta
  pip install -e ".[dev]"
  ```
- Import check:
  ```
  $ python -c "import tradingagents; print('TradingAgents import OK')"
  TradingAgents import OK
  ```
- Note: `pydantic` is not pinned by a lock file (it arrives transitively via
  `langchain-core`/`langgraph`). Tracked as DEBT-D1 in `docs/debt-register.md`.

## Baseline test results

Upstream test suite status is reported truthfully:

- Upstream suite (`tests/`, run with `python -m pytest tests -m "not integration"`):
  **Not run** in this session. (Reported as not-run rather than as passing.)
- EGTA offline contract tests (`test/offline/contracts/`), run in the `egta` env:
  ```
  $ python -m pytest test/offline/contracts -v
  34 passed in 0.06s          # exit 0
  $ python -m ruff check src/egta/contracts test/offline/contracts
  All checks passed!          # exit 0
  ```

## License and attribution

- Upstream `LICENSE`: **Apache License 2.0** (see repository `LICENSE`).
- Attribution: the project builds on `TauricResearch/TradingAgents` at the SHA above;
  upstream license and attribution are retained (`LICENSE`, `NOTICE`/README
  provenance preserved). New EGTA code under `src/` is added alongside the
  upstream packages without removing or relicensing upstream files.
