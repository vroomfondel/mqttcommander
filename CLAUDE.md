# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MQTTCommander is a Python CLI tool for managing Tasmota IoT devices via MQTT. It wraps the `mqttstuff` library to provide high-level operations like device discovery, command dispatch, and OTA firmware upgrades.

## Development Setup

Requires **Python 3.14**. Uses Hatch as build backend.

```bash
make install          # creates .venv with Python 3.14, installs all deps
source .venv/bin/activate
pip install -e .      # editable install for development
```

## Common Commands

```bash
make tests            # pytest .
make lint             # black -l 120 .
make isort            # isort .
make tcheck           # mypy *.py scripts mqttcommander
make commit-checks    # pre-commit run --all-files
make prepare          # tests + commit-checks
make pypibuild        # hatch build --clean
make build            # Docker multi-arch build via build.sh
make dstart           # run Docker container with --network=host
```

Run a single test: `pytest tests/test_base.py::test_name -v`

## Code Style

- **Black** with 120-char line limit
- **isort** for import sorting
- **mypy** for static type checking

## Architecture

```
CLI (mqttcommander/cli.py)  ← argparse subcommands
        ↓
MqttCommander class (mqttcommander/tasmotacommander.py)  ← core orchestrator
        ↓
mqttstuff library  ← MosquittoClientWrapper, MQTTLastDataReader, MWMqttMessage
        ↓
paho-mqtt  ← MQTT protocol
```

- **`mqttcommander/models.py`** — Pydantic v2 models for Tasmota devices. Uses `AliasChoices` to handle abbreviated Tasmota JSON fields (e.g., `fn`→`friendly_name`, `dn`→`device_name`).
- **`config.py`** (root) — `pydantic-settings` with YAML source: loads `config.yaml` then `config.local.yaml`, env vars override with `__` delimiter.
- **`main.py`** (root) — Docker/script entry point: reads config then calls CLI.
- **`mqttcommander/Helper.py`** — JSON utilities, version comparison.
- **`Helper.py`** (root) — `update_deep` dict merge, exception helpers.

### Key Patterns

- **Two-pass retained message processing**: `get_all_tasmota_devices_from_retained()` iterates messages twice — first populates `tasmota/discovery/#` config/sensors, second matches `tele/+/LWT` for online status.
- **Threading for command/response**: `send_cmds_to_online_tasmotas()` uses `threading.Condition` with 10s timeout to correlate command responses.
- **Loguru with skiplog filter**: Logger disabled by default (`glogger.disable(__name__)`). Callers must `logger.enable("mqttcommander")`. The `skiplog` extra suppresses verbose logs when `noisy=False`.
- **Fresh MQTT connections for retained messages**: Each `get_all_retained_msgs` call creates a new connection to ensure the broker delivers retained messages to a clean session.

## CLI Subcommands

`mqttcommander` requires `--host`, `--port`, `--username`, `--password` for MQTT connection, then one of:
`list-retained-msgs`, `list-tasmotas`, `list-online`, `send-cmd`, `upgrade-online`, `trigger-lwt-send`, `readfromfile`

## CI Pipeline

Black check and mypy+pytest run in parallel on push/PR. Docker multi-arch build (amd64+arm64) triggers only after mypy+pytest succeeds on `main`, pushing to `xomoxcc/mqttcommander` on Docker Hub.

## File Conventions

- `*.local.*` files are git-ignored (e.g., `config.local.yaml`, `scripts/include.local.sh`)
- Only the `mqttcommander/` package directory is included in built distributions
- Version is defined in `mqttcommander/__init__.py`
