"""Command-line interface for mqttcommander.

Provides a small set of subcommands to inspect retained messages, list
discovered Tasmota devices, and send commands to online devices.
"""
import textwrap
from pathlib import Path
from typing import Optional, List, cast, Union

import pytz
from loguru import logger

import mqttcommander
from mqttcommander import (
    MqttCommander,
    TASMOTA_DEFAULT_TOPICS,
    read_tasmotas_from_latest_file,
    TasmotaDevice, Helper,
)


def _run(
    host: str,
    port: int,
    username: str,
    password: str,
    action: str,
    command: Optional[str] = None,
    value: Optional[str] = None,
    tasmota_json_dir: Optional[Path] = None,
    timezone_name: Optional[str] = None,
    retained_msgs_receive_grace_s: Optional[int] = None,
    noisy: Optional[bool] = None,
    noisy_lowerlevel: Optional[bool] = None,
    dry_run: Optional[bool] = None,
) -> None:
    """Execute the requested CLI action.

    Args:
        host: MQTT broker hostname.
        port: MQTT broker port.
        username: MQTT username.
        password: MQTT password.
        action: Subcommand to execute. One of:
            - ``readfromfile``: Load latest saved Tasmota device snapshot and print count.
            - ``list-retained-msgs``: Receive and count retained MQTT messages for default topics.
            - ``list-tasmotas``: Build device list from retained discovery messages and print them.
            - ``list-online``: Filter online devices from retained data and print them.
            - ``send-cmd``: Send a command to all online devices.
            - ``trigger-lwt-send``: Trigger LWT Online for all offline devices using Publish2 command.
        command: Command name for ``send-cmd`` (e.g. ``Power``). Required when ``action`` is ``send-cmd``.
        value: Value to send for ``send-cmd``
        tasmota_json_dir: Directory to read Tasmota device snapshots from when ``action`` is
            ``readfromfile``. Defaults to the package ``tasmotas`` directory when ``None``.
        timezone_name: Timezone name (e.g. ``Europe/Berlin``) used when ``action`` is ``readfromfile``
            for timestamp handling. Defaults to ``Europe/Berlin`` when ``None``.
        retained_msgs_receive_grace_s: Grace period in seconds to receive retained messages when
            ``action`` is ``list-retained-msgs``. If ``None``, a default of 5 seconds is used.
        noisy: If ``True``, print/log additional information while receiving retained messages.
        noisy_lowerlevel: If ``True``, print/log lower-level debug info.
        dry_run: If ``True``, perform a dry run for actions that modify state.
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
            logger.info(f"Loaded {count} tasmota devices from latest file")
        case "list-retained-msgs":
            retained_msgs_receive_grace_s = retained_msgs_receive_grace_s or 5
            noisy = False if not noisy else True
            msgs = comm.get_all_retained_msgs(
                retained_msgs_receive_grace_ms=retained_msgs_receive_grace_s * 1000, noisy=noisy
            )
            cnt = 0 if msgs is None else len(msgs)
            logger.info(f"Retained messages matching topics {comm.topics}: {cnt}")
            if msgs:
                for m in msgs:
                    logger.info(f"- {m.topic}")
        case "list-tasmotas":
            retained_msgs_receive_grace_s = retained_msgs_receive_grace_s or 5
            noisy = False if not noisy else True
            noisy_lowerlevel = False if not noisy_lowerlevel else True

            all_devs = comm.get_all_tasmota_devices_from_retained(noisy=noisy, noisy_lowerlevel=noisy_lowerlevel, retained_msgs_receive_grace_ms=retained_msgs_receive_grace_s*1000)
            logger.info(f"Found {len(all_devs)} tasmota devices from retained data")
            for d in all_devs:
                tc = d.tasmota_config
                name = None
                if tc is not None:
                    name = tc.device_name or tc.friendly_name or tc.topic

                tw = textwrap.indent(Helper.get_pretty_dict_json_no_sort(d.model_dump()), "\t")
                logger.info(f"- {name}\n{tw}")
        case "list-online":
            retained_msgs_receive_grace_s = retained_msgs_receive_grace_s or 5
            noisy_lowerlevel = False if not noisy_lowerlevel else True
            noisy = False if not noisy else True
            all_devs = comm.get_all_tasmota_devices_from_retained(noisy=noisy, noisy_lowerlevel=noisy_lowerlevel, retained_msgs_receive_grace_ms=retained_msgs_receive_grace_s*1000)

            online = comm.filter_online_tasmotas_from_retained(all_tasmotas=all_devs, update_lwt_current_value=True)
            logger.info(f"Online devices: {len(online)} / {len(all_devs)}")
            for d in online:
                tc = d.tasmota_config
                name = None
                if tc is not None:
                    name = tc.device_name or tc.friendly_name or tc.topic

                tw = textwrap.indent(Helper.get_pretty_dict_json_no_sort(d.model_dump()), "\t")
                logger.info(f"- {name} online={d.lwt_current_value}\n{tw}")
        case "send-cmd":
            if not command:
                raise SystemExit("--command is required for action send-cmd")
            noisy = False if not noisy else True
            noisy_lowerlevel = False if not noisy_lowerlevel else True
            retained_msgs_receive_grace_s = retained_msgs_receive_grace_s or 5
            all_devs = comm.get_all_tasmota_devices_from_retained(noisy=noisy, noisy_lowerlevel=noisy_lowerlevel, retained_msgs_receive_grace_ms=retained_msgs_receive_grace_s*1000)
            online = comm.filter_online_tasmotas_from_retained(all_devs)
            # vals_typed = cast(
            #     List[List[Union[str, float, dict, int]] | None] | None, [values] if values is not None else None
            # )
            val_typed = cast(
                List[Union[str, float, dict, int]] | None, value if value is not None else None
            )
            comm.send_cmds_to_online_tasmotas(online, to_be_used_commands=[command], values_to_send=[val_typed for _ in online])
        case "upgrade-online":
            dry_run = False if not dry_run else True
            noisy = False if not noisy else True
            noisy_lowerlevel = False if not noisy_lowerlevel else True
            retained_msgs_receive_grace_s = retained_msgs_receive_grace_s or 5
            all_devs = comm.get_all_tasmota_devices_from_retained(
                noisy=noisy,
                noisy_lowerlevel=noisy_lowerlevel,
                retained_msgs_receive_grace_ms=retained_msgs_receive_grace_s * 1000,
            )
            online = comm.filter_online_tasmotas_from_retained(all_devs)

            comm.ensure_freshest_firmware(online_tasmotas=online, dry_run=dry_run)

        case "trigger-lwt-send":
            noisy = False if not noisy else True
            noisy_lowerlevel = False if not noisy_lowerlevel else True
            retained_msgs_receive_grace_s = retained_msgs_receive_grace_s or 5
            all_devs = comm.get_all_tasmota_devices_from_retained(noisy=noisy, noisy_lowerlevel=noisy_lowerlevel,
                                                                  retained_msgs_receive_grace_ms=retained_msgs_receive_grace_s * 1000)
            offline = [d for d in all_devs if not d.is_online()]
            logger.info(f"Triggering LWT Online for {len(offline)} offline devices")

            if offline:
                # this is direct mqtt command-sending mode...
                comm.mqttclient.wait_for_connect_and_start_loop()
                for d in offline:
                    if d.tasmota_config and d.tasmota_config.topic:
                        topic = d.tasmota_config.topic
                        cmd_topic = f"cmnd/{topic}/Publish2"
                        cmd_payload = f"tele/{topic}/LWT Online"
                        logger.info(f"Sending to {cmd_topic}: {cmd_payload}")
                        comm.mqttclient.publish_one(topic=cmd_topic, value=cmd_payload)
        case _:
            raise SystemExit(f"Unknown action: {action}")


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the mqttcommander CLI.

    Parses command-line arguments and invokes :func:`_run`.

    Args:
        argv: Command-line arguments. Defaults to ``sys.argv[1:]``.
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
    p_ret = sub.add_parser("list-retained-msgs", help="List count of retained messages for default topics")
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

    p_lt = sub.add_parser("list-tasmotas", help="Build device list from retained discovery and print devices")
    p_lt.add_argument(
        "--grace-s",
        dest="retained_msgs_receive_grace_s",
        type=int,
        default=None,
        help="Time window in seconds to receive retained messages (default: 5)",
    )
    p_lt.add_argument(
        "--noisy",
        action="store_true",
        default=False,
        help="Enable verbose output while processing received retained messages",
    )
    p_lt.add_argument(
        "--noisy_lowerlevel",
        action="store_true",
        default=False,
        help="Enable verbose output while receiving retained messages",
    )


    p_lo = sub.add_parser("list-online", help="Filter online devices and print them")
    p_lo.add_argument(
        "--grace-s",
        dest="retained_msgs_receive_grace_s",
        type=int,
        default=None,
        help="Time window in seconds to receive retained messages (default: 5)",
    )
    p_lo.add_argument(
        "--noisy",
        action="store_true",
        default=False,
        help="Enable verbose output while processing received retained messages",
    )
    p_lo.add_argument(
        "--noisy_lowerlevel",
        action="store_true",
        default=False,
        help="Enable verbose output while receiving retained messages",
    )

    p_send = sub.add_parser("send-cmd", help="Send a command to all online devices")
    p_send.add_argument("--command", required=True, help="Command, e.g. Power")
    p_send.add_argument("--value", help="Value to send, e.g. Toggle or 1 0 ...")

    p_lwt = sub.add_parser("trigger-lwt-send", help="Send command for all OFFLINE devices 'Publish2 tele/{topic}/LWT Online'")
    p_lwt.add_argument(
        "--grace-s",
        dest="retained_msgs_receive_grace_s",
        type=int,
        default=None,
        help="Time window in seconds to receive retained messages (default: 5)",
    )
    p_lwt.add_argument(
        "--noisy",
        action="store_true",
        default=False,
        help="Enable verbose output while processing received retained messages",
    )
    p_lwt.add_argument(
        "--noisy_lowerlevel",
        action="store_true",
        default=False,
        help="Enable verbose output while receiving retained messages",
    )

    upg = sub.add_parser("upgrade-online", help="Upgrade online tasmotas from set OtaURL if there is a newer firmware available.")
    upg.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Disable actual sending upgrade - enable \"dry run\"",
    )

    args = parser.parse_args(argv)  # argv wird hier verwendet

    _run(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        action=args.action,
        command=getattr(args, "command", None),
        value=getattr(args, "value", None),
        tasmota_json_dir=getattr(args, "tasmota_json_dir", None),
        timezone_name=getattr(args, "timezone_name", None),
        retained_msgs_receive_grace_s=getattr(args, "retained_msgs_receive_grace_s", None),
        noisy=getattr(args, "noisy", None),
        noisy_lowerlevel=getattr(args, "noisy_lowerlevel", None),
        dry_run=getattr(args, "dry_run", None),
    )


if __name__ == "__main__":
    main()
