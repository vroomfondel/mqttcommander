from typing import Optional, List, cast, Union

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
) -> None:
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
            tasmotas = read_tasmotas_from_latest_file(noisy=True)
            count = len(tasmotas) if tasmotas else 0
            print(f"Loaded {count} tasmota devices from latest file")
        case "list-retained":
            msgs = comm.get_all_retained(noisy=False)
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
            vals_typed = cast(List[List[Union[str, float, dict, int]] | None] | None, [values] if values is not None else None)
            comm.send_cmds_to_online_tasmotas(online, to_be_used_commands=[command], values_to_send=vals_typed)
        case _:
            raise SystemExit(f"Unknown action: {action}")


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="mqttcommander CLI")

    # Common connection options
    parser.add_argument("--host", type=str, required=True, help="MQTT broker host")
    parser.add_argument("--port", type=int, required=True, help="MQTT broker port")
    parser.add_argument("--username", type=str, required=True, help="MQTT username")
    parser.add_argument("--password", type=str, required=True, help="MQTT password")

    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("readfromfile", help="Read latest saved tasmota devices file and show count")
    sub.add_parser("list-retained", help="List count of retained messages for default topics")
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
    )


if __name__ == "__main__":
    main()
