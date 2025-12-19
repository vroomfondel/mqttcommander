![mypy and pytests](https://github.com/vroomfondel/mqttcommander/actions/workflows/mypynpytests.yml/badge.svg)
[![BuildAndPushMultiarch](https://github.com/vroomfondel/mqttcommander/actions/workflows/buildmultiarchandpush.yml/badge.svg)](https://github.com/vroomfondel/mqttcommander/actions/workflows/buildmultiarchandpush.yml)
![Cumulative Clones](https://img.shields.io/endpoint?logo=github&url=https://gist.githubusercontent.com/vroomfondel/65da30603d04548c80d1e67042b60a6f/raw/mqttcommander_clone_count.json)
[![Docker Pulls](https://img.shields.io/docker/pulls/xomoxcc/mqttcommander?logo=docker)](https://hub.docker.com/r/xomoxcc/mqttcommander/tags)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/mqttcommander?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=PyPi+Downloads)](https://pepy.tech/projects/mqttcommander)

[![https://github.com/vroomfondel/mqttcommander/raw/main/Gemini_Generated_Image_mqttcommander_wjpr8gwjpr8gwjpr_250x250.png](https://github.com/vroomfondel/mqttcommander/raw/main/Gemini_Generated_Image_mqttcommander_wjpr8gwjpr8gwjpr_250x250.png)](https://github.com/vroomfondel/mqttcommander)



# MQTTCommander

Convenience tools for discovering and commanding Tasmota devices over MQTT, plus a small CLI and a ready-to-use Docker image. This project now depends on the external library `mqttstuff` for the generic MQTT client/wrapper utilities — the `mqttstuff` source is no longer embedded in this repo and is pulled via the package manager.

Key capabilities:

- Connecting/subscribing and publishing via the `mqttstuff` wrapper
- Reading “last/most recent” messages with timeout-based collection
- Inspecting and commanding Tasmota devices via their MQTT topics
- Pydantic-based configuration (YAML + environment overrides)
- Developer helpers for JSON pretty-printing, deep updates, and logging configuration

- This repository: `mqttcommander`
- External dependency: `mqttstuff` (https://github.com/vroomfondel/mqttstuff)

## Overview

MQTTCommander builds on top of `paho-mqtt` through the external `mqttstuff` library to simplify common patterns:

- A `mqttstuff.mosquittomqttwrapper.MosquittoClientWrapper` to configure, connect, subscribe, and publish with minimal boilerplate
- A `mqttstuff.mosquittomqttwrapper.MQTTLastDataReader` utility to retrieve the most recent messages quickly
- A `mqttcommander.tasmotacommander.MqttCommander` toolkit to discover Tasmota devices from retained topics and interact with them in bulk
- Pydantic settings in `config.py` to load credentials and broker details from `config.yaml`/`config.local.yaml` and/or environment

The project also includes a Dockerfile for a batteries-included container image useful for testing and running these tools in a consistent environment.

### Repository layout

```
.
├─ mqttcommander/
│  ├─ __init__.py
│  ├─ cli.py
│  ├─ tasmotacommander.py
│  ├─ models.py
│  ├─ Helper.py
│  └─ py.typed
├─ config.py                    # Pydantic settings + logging setup
├─ main.py                      # Entry example/utility
├─ requirements*.txt
├─ pyproject.toml
├─ Makefile
├─ Dockerfile
├─ config.yaml                  # default config (example)
├─ config.local.yaml            # local overrides (git-ignored; example provided)
└─ tests/
```

## Installation

Options:

- From PyPI:
  - `python -m pip install mqttcommander`
  - This will also install `mqttstuff` as a dependency.

- From source (editable):
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements-dev.txt`
  - `pip install -e .`

- Build distributions with Hatch:
  - `make pypibuild`
  - Artifacts are created under `dist/`

## Quick Start

Simple publish and subscribe using the wrapper:

```python
from mqttstuff import MosquittoClientWrapper

client = MosquittoClientWrapper(
    host="localhost", port=1883, username="user", password="pass",
    topics=["test/topic"],
)

def on_any_message(msg, userdata):
    # msg is an instance of MWMqttMessage with convenient fields
    print(msg.topic, msg.value)

client.set_on_msg_callback(on_any_message, rettype="valuemsg")
client.connect_and_start_loop_forever()

# elsewhere or in another process
client.publish_one("test/topic", {"hello": "world"}, retain=False)
```

Read last retained or recent messages with a timeout:

```python
from mqttstuff import MQTTLastDataReader

data = MQTTLastDataReader.get_most_recent_data_with_timeout(
    host="localhost", port=1883, username="user", password="pass",
    topics=["tele/+/STATE", "stat/+/STATUS"],
    retained="only",  # "yes" | "no" | "only"
    rettype="str_raw", # or "json", "valuemsg", "str", "int", "float"
)
print(data)
```

## Configuration

Configuration is defined with Pydantic Settings in `config.py` and loaded from:

1. Environment variables
2. `config.local.yaml` (if present)
3. `config.yaml`

You can override paths with environment variables:

- `MQTTCOMMANDER_CONFIG_DIR_PATH` – base config dir
- `MQTTCOMMANDER_CONFIG_PATH` – path to main YAML config
- `MQTTCOMMANDER_CONFIG_LOCAL_PATH` – path to local override YAML

The `Mqtt` section is expected to contain common fields like `host`, `port`, `username`, `password`, and optional topic lists. See the file headers in `config.py` for details.

## Python Modules

Each Python module provided by this repository is documented here with a focused explanation of its purpose and usage.

### Package: `mqttstuff` (external dependency)

Key classes and responsibilities:

- `MWMqttMessage` (Pydantic model)
  - Normalized container for incoming/outgoing MQTT messages
  - Helpers like `from_pahomsg(...)` and fields for `topic`, `qos`, `retain`, `payload`, `value`, `created_at`, and optional `metadata`

- `MosquittoClientWrapper`
  - Thin wrapper around `paho.mqtt.client.Client`
  - Simplifies connection setup and topic subscriptions via `set_topics([...])`
  - Register callbacks per-topic (`add_message_callback(topic, callback, rettype=...)`) or a global callback (`set_on_msg_callback`)
  - Publish utilities:
    - `publish_one(topic, value, created_at=None, metadata=None, rettype="valuemsg", retain=False, timeout=None)`
    - `publish_multiple(list[MWMqttMessage], timeout=None)`
  - Connection loop helpers:
    - `connect_and_start_loop_forever(topics=None, timeout_connect_seconds=None)`
    - `wait_for_connect_and_start_loop()`
  - Convenience: automatic payload conversion for int/float/str/JSON/valuemsg

- `MQTTLastDataReader`
  - Static helper to retrieve the most recent messages within a configurable timeout window
  - Supports retained-only, no-retained, or mixed operation via `retained` parameter
  - Returns results in different representations via `rettype` and `fallback_rettype`

Example – per-topic callback with type conversion:

```python
from mqttstuff import MosquittoClientWrapper

client = MosquittoClientWrapper(
    host="localhost", port=1883, username="user", password="pass",
    topics=["home/+/temperature"],
)

def on_temperature(msg, userdata):
    # msg.value is already a number if rettype="int"/"float"
    print("Temp:", msg.value)

client.add_message_callback("home/+/temperature", on_temperature, rettype="float")
client.connect_and_start_loop_forever()
```

### Package: `mqttcommander`

Tools to discover and command Tasmota devices using their MQTT topics.

Highlights:

- Data models for timers, timezone/DST config, device config and sensors
- `MqttCommander` to collect retained messages across topics, filter noisy subtrees, and start processing loops
- Discovery helpers:
  - `get_all_tasmota_devices_from_retained(...)`
  - `filter_online_tasmotas_from_retained(...)`
  - `update_online_tasmotas(...)`
- Command helpers to send one or many commands to all online devices:
  - `send_cmds_to_online_tasmotas(tasmotas, to_be_used_commands=[...], values_to_send=[...])`
- Firmware management:
  - `ensure_freshest_firmware(online_tasmotas, dry_run=False)`
- Timezone utilities to ensure consistent device settings:
  - `ensure_correct_timezone_settings_for_tasmotas(online_tasmotas)`
- JSON utilities and pretty-printers for review and persistence:
  - `write_tasmota_devices_file(...)`
  - `read_tasmotas_from_latest_file(...)`

Example – list online devices and send a command:

```python
from mqttcommander import MqttCommander

comm = MqttCommander(host="localhost", port=1883, username="user", password="pass")
all_devs = comm.get_all_tasmota_devices_from_retained(topics=["tele/+/STATE"], noisy=False)
online = comm.filter_online_tasmotas_from_retained(all_devs)
comm.send_cmds_to_online_tasmotas(online, to_be_used_commands=["Power"], values_to_send=[["Toggle"]])
```

### Module: `config`

- Centralized configuration and Loguru logging setup
- Uses `pydantic-settings` to read from environment and YAML
- Timezone helpers and constants (e.g., `TZBERLIN`)
- Environment variables `LOGURU_LEVEL`, `MQTTCOMMANDER_CONFIG_*` are respected

Typical usage:

```python
from config import Settings

settings = Settings()  # loads from env + config.local.yaml + config.yaml
print(settings.MQTT.host, settings.MQTT.port)
```

### Module: `Helper`

Small utilities used across the project:

- `ComplexEncoder` for JSON serialization of complex types (UUID, datetimes, dict/list pretty rendering)
- `print_pretty_dict_json`, `get_pretty_dict_json`, `get_pretty_dict_json_no_sort`
- `update_deep(base, u)` for deep dict/list merge/update
- `get_exception_tb_as_string(exc)` for converting exception tracebacks to strings
- `get_loguru_logger_info()` to introspect Loguru handlers and filters

## Docker

The repository contains a ready-to-use Dockerfile at the repository root designed for local development and CI usage.

### What the Docker image includes

- Base: `python:${python_version}-${debian_version}` (defaults `3.14-trixie`)
- Useful packages: `htop`, `procps`, `iputils-ping`, `locales`, `vim`, `tini`
- Python dependencies from `requirements.txt` and `requirements-dev.txt`
- Source code copied into `/app` and `PYTHONPATH=/app`
- Loguru-friendly environment with `tini` as entrypoint

### Build arguments

- `python_version` – default `3.14`
- `debian_version` – default `trixie`
- `UID`, `GID`, `UNAME` – user configuration in the image (defaults: 1234/1234/pythonuser)
- `TARGETOS`, `TARGETARCH`, `TARGETPLATFORM` – auto-populated by BuildKit/buildx for multi-arch
- `gh_ref`, `gh_sha`, `buildtime` – injected into environment variables (`GITHUB_REF`, `GITHUB_SHA`, `BUILDTIME`)

### Building the image

Basic build:

```bash
docker build -t xomoxcc/mqttcommander:latest .
```

Pass custom Python/Debian versions:

```bash
docker build \
  --build-arg python_version=3.12 \
  --build-arg debian_version=bookworm \
  -t xomoxcc/mqttcommander:py312 .
```

Embed source metadata (useful in CI):

```bash
docker build \
  --build-arg gh_ref="${GITHUB_REF}" \
  --build-arg gh_sha="${GITHUB_SHA}" \
  --build-arg buildtime="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t xomoxcc/mqttcommander:with-meta .
```

Multi-architecture build with buildx (example for amd64 and arm64):

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/youruser/xomoxcc-mqttcommander:latest \
  --push .
```

Note: This repository already provides a `docker-config/` buildx context. You can reuse your existing builder or create a new one:

```bash
docker buildx create --name mbuilder --use || true
docker buildx inspect --bootstrap
```

### Running the image

The image uses `tini` as entrypoint and runs the application by default via:

```
ENTRYPOINT ["tini", "--", "python", "main.py"]
```

Implications:

- By default, the container starts `python main.py` inside `/app`.
- To run a shell or the CLI directly instead, override the entrypoint with `--entrypoint`.
- Environment variables like `MQTTCOMMANDER_CONFIG_DIR_PATH` can be used to point the app to your configs.
- main.py is a wrapper to inject values read from config.yaml/config.local.yaml/ENV (in that order; "the latter overrides values from the earlier") into the call to mqttcommander.cli:main

Examples:

```bash
# Run the default app (python main.py via tini) with your config
docker run --rm -it \
  -e LOGURU_LEVEL=INFO \
  -e MQTTCOMMANDER_CONFIG_DIR_PATH=/app \
  -v "$(pwd)/config.local.yaml:/app/config.local.yaml:ro" \
  xomoxcc/mqttcommander:latest

# Start a shell for inspection (override entrypoint)
docker run --rm -it \
  -e LOGURU_LEVEL=DEBUG \
  -e MQTTCOMMANDER_CONFIG_DIR_PATH=/app \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  --entrypoint tini xomoxcc/mqttcommander:latest -- \
  /bin/bash

# Run the mqttcommander CLI directly
docker run --rm -it \
  -e LOGURU_LEVEL=DEBUG \
  --entrypoint tini xomoxcc/mqttcommander:latest -- \
  mqttcommander --host broker --port 1883 --username user --password pass list-online

# Run a Python one-liner using the mqttstuff wrapper (installed as dependency)
docker run --rm -it \
  --entrypoint tini xomoxcc/mqttcommander:latest -- \
  python -c "from mqttstuff import MQTTLastDataReader as R; print(R.get_most_recent_data_with_timeout('broker',1883,'user','pass',['tele/+/STATE'], retained='only'))"
```

Recommendation: You should always try to run python(especially python, but imho all other processes as well) through an entrypoint via tini to ensure proper signal handling (STOP/KILL/TERM/INT) and process reaping for/inside the conainer.
```bash
# Run the default app (python main.py via tini) with your config
docker run --rm -it \
  --network=host \
  -e LOGURU_LEVEL=DEBUG \  
  -v "$(pwd)/config.local.yaml:/app/config.local.yaml:ro" \  
  --entrypoint tini xomoxcc/mqttcommander:latest -- \
  python main.py list-retained-msgs --grace-s 10
```


### Why Docker here is useful

- Ensures consistent Python/dependency versions across dev machines and CI
- Provides a preconfigured environment for quick experiments against an MQTT broker
- Makes multi-arch builds straightforward with buildx

## Development

Helpful `Makefile` targets:

- `make help` – list available targets with short descriptions
- `make install` – create virtualenv and install development requirements
- `make venv` – ensure `.venv` exists and dev requirements are installed
- `make tests` – run pytest
- `make lint` – run Black code formatter
- `make isort` – fix and check import order
- `make tcheck` – run mypy type checks over `*.py`, `scripts/`, and `mqttcommander/`
- `make commit-checks` – run pre-commit hooks on all files
- `make prepare` – run tests and commit-checks (useful before committing/PRs)
- `make pypibuild` – build sdist and wheel with Hatch into `dist/`
- `make pypipush` – publish built artifacts with Hatch (configure credentials first)
- `make build` – build the Docker image via `./build.sh`
- `make dstart` – start ephemeral container (host network), mapping `config.local.yaml` into `/app`

## TasmotaCommander usage examples

### Via CLI

The image and PyPI package install a console script `mqttcommander`. Common actions:

```bash
# 1) List discovered Tasmota devices from retained discovery topics
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  list-tasmotas

# 2) Send a command to all online devices (e.g., toggle power)
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  send-cmd --command Power --value Toggle

# 3) List only online devices
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  list-online

# 4) Upgrade online devices if newer firmware is available (via OtaURL)
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  upgrade-online --dry-run

# 5) Trigger LWT Online for all currently offline devices (using Publish2)
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  trigger-lwt-send

# Bonus) Show how many retained messages match default topics and print a few
#        Optional: increase receive window and enable verbose output
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  list-retained-msgs

# with options:
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  list-retained-msgs --grace-s 10 --noisy

# Bonus) Load previously saved device list (if present) and show count
#        Optional: specify custom snapshot directory and timezone
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  readfromfile

# with options:
mqttcommander \
  --host broker --port 1883 --username user --password pass \
  readfromfile --tasmota-json-dir /path/to/snapshots --timezone Europe/Berlin
```

When running inside Docker, use `--entrypoint mqttcommander` as shown above, and pass the same flags.

### Via Python API

Two additional examples that build on the `MqttCommander` API:

```python
# Example A: Read retained discovery/state data and print topic summary
from mqttcommander import MqttCommander

comm = MqttCommander(host="localhost", port=1883, username="user", password="pass")
msgs = comm.get_all_retained_msgs(topics=["tasmota/discovery/#", "tele/+/STATE"], noisy=False, rettype="json")
if msgs:
  print(f"Collected {len(msgs)} retained messages")
  for m in msgs[:5]:
    print(m.topic)

# Example B: Ensure timezone settings are correct on all online devices
from mqttcommander import MqttCommander

comm = MqttCommander(host="localhost", port=1883, username="user", password="pass")
all_devs = comm.get_all_tasmota_devices_from_retained(noisy=False)
online = comm.filter_online_tasmotas_from_retained(all_devs)
comm.ensure_correct_timezone_settings_for_tasmotas(online)

# Example C: Upgrade firmware on all online devices (dry run)
comm.ensure_freshest_firmware(online, dry_run=True)
```

## Testing

Tests live under `tests/`. Run all tests with:

```bash
pytest -q
```

## License

This project is licensed under the LGPL where applicable/possible — see [LICENSE.md](LICENSE.md). Some files/parts may be governed by other licenses and/or licensors, such as [MIT](LICENSEMIT.md) | [GPL](LICENSEGPL.md) | [LGPL](LICENSELGPL.md). Please also check file headers/comments.

## Acknowledgments

See inline comments in the codebase for inspirations and references.

## ⚠️ Disclaimer

This is a development/experimental project. For production use, review security settings, customize configurations, and test thoroughly in your environment. Provided "as is" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software. Use at your own risk.