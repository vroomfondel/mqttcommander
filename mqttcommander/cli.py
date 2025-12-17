"""Command-line interface for mqttcommander.

Provides a small set of subcommands to inspect retained messages, list
discovered Tasmota devices, and send commands to online devices.
"""

from pathlib import Path
from typing import Optional, List, cast, Union

import pytz
from loguru import logger

import mqttcommander
from mqttcommander import (
    MqttCommander,
    TASMOTA_DEFAULT_TOPICS,
    read_tasmotas_from_latest_file,
    TasmotaDevice,
)


def _run(
    host: str,
    port: int,
    username: str,
    password: str,
    action: str,
    command: Optional[str] = None,
    values: Optional[List[str]] = None,
    tasmota_json_dir: Optional[Path] = None,
    timezone_name: Optional[str] = None,
    retained_msgs_receive_grace_s: Optional[int] = None,
    noisy: Optional[bool] = None,
) -> None:
    """Execute the requested CLI action.

    Args:
        host: MQTT broker hostname.
        port: MQTT broker port.
        username: MQTT username.
        password: MQTT password.
        action: Subcommand to execute. One of:
            - ``readfromfile``: Load latest saved Tasmota device snapshot and print count.
            - ``list-retained``: Receive and count retained MQTT messages for default topics.
            - ``list-tasmotas``: Build device list from retained discovery messages and print them.
            - ``list-online``: Filter online devices from retained data and print them.
            - ``send-cmd``: Send a command to all online devices.
        command: Command name for ``send-cmd`` (e.g. ``Power``). Required when ``action`` is ``send-cmd``.
        values: Values to send for ``send-cmd``; multiple values are supported.
        tasmota_json_dir: Directory to read Tasmota device snapshots from when ``action`` is
            ``readfromfile``. Defaults to the package ``tasmotas`` directory when ``None``.
        timezone_name: Timezone name (e.g. ``Europe/Berlin``) used when ``action`` is ``readfromfile``
            for timestamp handling. Defaults to ``Europe/Berlin`` when ``None``.
        retained_msgs_receive_grace_s: Grace period in seconds to receive retained messages when
            ``action`` is ``list-retained``. If ``None``, a default of 5 seconds is used.
        noisy: If ``True``, print/log additional information while receiving retained messages when
            ``action`` is ``list-retained``. If ``None`` or ``False``, be quiet.
    """
    mqttcommander.configure_loguru_default_with_skiplog_filter()
    logger.enable("mqttcommander")

    comm: MqttCommander = MqttCommander(
        topics=TASMOTA_DEFAULT_TOPICS,
        host=host,
        port=port,
        username=username,
        password=password,
    )

    match action:
        case "readfromfile":
            tz = pytz.timezone(timezone_name) if timezone_name else pytz.timezone("Europe/Berlin")
            tasmotas = read_tasmotas_from_latest_file(
                tasmota_json_dir=tasmota_json_dir,
                timezone=tz,
            )
            count = len(tasmotas) if tasmotas else 0
            print(f"Loaded {count} tasmota devices from latest file")
        case "list-retained":
            retained_msgs_receive_grace_s = retained_msgs_receive_grace_s or 5
            noisy = False if not noisy else True
            msgs = comm.get_all_retained(
                retained_msgs_receive_grace_ms=retained_msgs_receive_grace_s * 1000, noisy=noisy
            )
            cnt = 0 if msgs is None else len(msgs)
            print(f"Retained messages matching topics {comm.topics}: {cnt}")
            if msgs:
                for m in msgs[:10]:
                    print(f"- {m.topic}")
        case "list-tasmotas":
            all_devs = comm.get_all_tasmota_devices_from_retained(noisy=False)
            print(f"Found {len(all_devs)} tasmota devices from retained data")
            for d in all_devs:
                tc = d.tasmota_config
                name = None
                if tc is not None:
                    name = tc.device_name or tc.friendly_name or tc.topic
                print(f"- {name}")
        case "list-online":
            all_devs = comm.get_all_tasmota_devices_from_retained(noisy=False)
            online = comm.filter_online_tasmotas_from_retained(all_devs)
            print(f"Online devices: {len(online)} / {len(all_devs)}")
            for d in online:
                tc = d.tasmota_config
                name = None
                if tc is not None:
                    name = tc.device_name or tc.friendly_name or tc.topic
                print(f"- {name} online={d.lwt_current_value}")
        case "send-cmd":
            if not command:
                raise SystemExit("--command is required for action send-cmd")
            all_devs = comm.get_all_tasmota_devices_from_retained(noisy=False)
            online = comm.filter_online_tasmotas_from_retained(all_devs)
            vals_typed = cast(
                List[List[Union[str, float, dict, int]] | None] | None, [values] if values is not None else None
            )
            comm.send_cmds_to_online_tasmotas(online, to_be_used_commands=[command], values_to_send=vals_typed)
        case _:
            raise SystemExit(f"Unknown action: {action}")


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entrypoint.

    Args:
        argv: Optional argument vector for testing; defaults to ``sys.argv``.
    """
    import argparse

    parser = argparse.ArgumentParser(description="mqttcommander CLI")

    # Common connection options
    parser.add_argument("--host", type=str, required=True, help="MQTT broker host")
    parser.add_argument("--port", type=int, required=True, help="MQTT broker port")
    parser.add_argument("--username", type=str, required=True, help="MQTT username")
    parser.add_argument("--password", type=str, required=True, help="MQTT password")

    sub = parser.add_subparsers(dest="action", required=True)

    p_read = sub.add_parser(
        "readfromfile",
        help="Read latest saved tasmota devices file and show count",
        description=(
            "Reads the most recent tasmota devices JSON snapshot. You can specify "
            "a custom directory with --tasmota-json-dir and a timezone for timestamp "
            "display/selection using --timezone."
        ),
    )
    p_read.add_argument(
        "--tasmota-json-dir",
        type=Path,
        default=None,
        help="Directory containing tasmota_devices_*.json snapshots (defaults to the package tasmotas dir)",
    )
    p_read.add_argument(
        "--timezone",
        dest="timezone_name",
        type=str,
        default=None,
        help="Timezone name, e.g. Europe/Berlin (defaults to Europe/Berlin)",
    )
    p_ret = sub.add_parser("list-retained", help="List count of retained messages for default topics")
    p_ret.add_argument(
        "--grace-s",
        dest="retained_msgs_receive_grace_s",
        type=int,
        default=None,
        help="Time window in seconds to receive retained messages (default: 5)",
    )
    p_ret.add_argument(
        "--noisy",
        action="store_true",
        default=False,
        help="Enable verbose output while receiving retained messages",
    )
    sub.add_parser("list-tasmotas", help="Build device list from retained discovery and print devices")
    sub.add_parser("list-online", help="Filter online devices and print them")

    p_send = sub.add_parser("send-cmd", help="Send a command to all online devices")
    p_send.add_argument("--command", required=True, help="Command, e.g. Power")
    p_send.add_argument("--values", nargs="*", help="Values to send, e.g. Toggle or 1 0 ...")

    args = parser.parse_args(argv)  # argv wird hier verwendet

    _run(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        action=args.action,
        command=getattr(args, "command", None),
        values=getattr(args, "values", None),
        tasmota_json_dir=getattr(args, "tasmota_json_dir", None),
        timezone_name=getattr(args, "timezone_name", None),
        retained_msgs_receive_grace_s=getattr(args, "retained_msgs_receive_grace_s", None),
        noisy=getattr(args, "noisy", None),
    )


if __name__ == "__main__":
    main()
