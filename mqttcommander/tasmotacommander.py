import difflib
import json
import os
import textwrap
import threading

from datetime import datetime, tzinfo
from io import StringIO
from pathlib import Path
from typing import Any, Literal, Set, Optional, List, Dict, ClassVar, Tuple, Annotated

from mqttstuff import MWMqttMessage, MosquittoClientWrapper, MQTTLastDataReader

from loguru import logger
import pytz

import Helper
from mqttcommander.Helper import get_pretty_dict_json_no_sort
from mqttcommander.models import TasmotaTimezoneConfig, TasmotaDeviceConfig, TasmotaRule, TasmotaDeviceSensors, TasmotaDevice, TasmotaTimeZoneDSTSTD

logger.debug(f"{__name__} DEBUG")
logger.info(f"{__name__} INFO")



# print(maca.model_dump())
# exit(1)


# class TasmotaDeviceList(BaseModel):
#     tasmotas: List[TasmotaDevice]

TASMOTA_DEFAULT_TOPICS: List[str] = ["tasmota/discovery/#", "tele/+/LWT"]
TASMOTA_DISCOVERY_TOPIC_BEGIN: str = "tasmota/discovery"
TASMOTA_LWT_TOPIC_BEGIN: str = "tele/"
TASMOTA_LWT_TOPIC_END: str = "LWT"


class MqttCommander:
    logger: ClassVar = logger.bind(classname=__qualname__)
    _msg_topicname_startwith_drop_filter_defaultset: ClassVar[Set[str]] = {"tele/rtl_433"}

    # TODO ADD RECEIVE_TRIGGERS

    def __init__(
        self,
        topics: list[str]|None = None,
        msg_topicname_startwith_drop_filter: Set | None = _msg_topicname_startwith_drop_filter_defaultset,  # type: ignore
        mqttclient: MosquittoClientWrapper | None = None,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None
    ):
        self.msg_topicname_startwith_drop_filter = msg_topicname_startwith_drop_filter

        if mqttclient is None and not all([host, port, username, password]):
            raise ValueError("Either mqttclient or all of host,port,username,password must be supplied")

        if msg_topicname_startwith_drop_filter is self.__class__._msg_topicname_startwith_drop_filter_defaultset:
            self.__class__.logger.debug("DEFAULT SET REPLACED!")
            self.msg_topicname_startwith_drop_filter: Set[str] = set()  # type: ignore
            self.msg_topicname_startwith_drop_filter.update(msg_topicname_startwith_drop_filter)

        # ensure we always have a concrete list of topics
        self.topics = topics or TASMOTA_DEFAULT_TOPICS

        self.mqttclient: MosquittoClientWrapper

        if mqttclient is not None:
            self.mqttclient = mqttclient
        else:
            self.mqttclient = MosquittoClientWrapper(
                host=host,
                port=port,
                username=username,
                password=password,
            )

        # Do not overwrite self.topics with possibly None; always use concrete list
        self.mqttclient.set_topics(self.topics)
        self.cmdsent: bool = False



    def apply_topic_filter(self, msgs: list[MWMqttMessage] | None) -> list[MWMqttMessage] | None:
        if self.msg_topicname_startwith_drop_filter is None or msgs is None:
            return msgs

        ret: list[MWMqttMessage] = []
        for msg in msgs:
            for sw in self.msg_topicname_startwith_drop_filter:
                if not msg.topic.startswith(sw):
                    ret.append(msg)

        if len(ret) == 0:
            return None

        return ret


    def get_all_retained(
        self,
        topics: list[str] | None = None,
        retained_msgs_receive_grace_ms: int = 2_000,
        noisy: bool = False,
        rettype: Literal["json", "str", "int", "float", "valuemsg", "str_raw"] = "str_raw",
        fallback_rettype: Literal["json", "str", "int", "float", "valuemsg", "str_raw"] = "str_raw",
    ) -> list[MWMqttMessage] | None:

        if topics is None:
            topics = self.topics

        assert self.mqttclient is not None and \
               self.mqttclient.host is not None and \
               self.mqttclient.port is not None and \
               self.mqttclient.username is not None and \
               self.mqttclient.password is not None

        # need fresh connect to server - otherwise, the retained data is not sent to a ("cleansession=true) client
        # TODO: HT20251214 check if handing down provided mqttclient could be an option...
        msgs: list[MWMqttMessage] | None = MQTTLastDataReader.get_most_recent_data_with_timeout(
            host=self.mqttclient.host,
            port=self.mqttclient.port,
            username=self.mqttclient.username,
            password=self.mqttclient.password,
            topics=topics,
            noisy=noisy,
            timeout_msgreceived_seconds=retained_msgs_receive_grace_ms / 1000.0,
            retained="only",
            max_received_msgs=-1,
            rettype=rettype,
            fallback_rettype=fallback_rettype,
        )

        msgs = self.apply_topic_filter(msgs)

        return msgs

    def start_loop_forever(
        self, rettype: Literal["json", "str", "int", "float", "valuemsg", "str_raw"] = "str_raw"
    ) -> None:
        # self.mqttclient.add_message_callback("tele/tasmota_183BAA/LWT", self.on_msg_received)
        self.mqttclient.set_on_msg_callback(self.on_msg_received, rettype=rettype)
        self.mqttclient.connect_and_start_loop_forever(topics=self.topics)

    def on_msg_received(self, msg: MWMqttMessage, userdata: Any) -> None:
        if self.msg_topicname_startwith_drop_filter is not None:
            for sw in self.msg_topicname_startwith_drop_filter:
                if msg.topic.startswith(sw):
                    return

        self.__class__.logger.debug(get_pretty_dict_json_no_sort(msg.model_dump(by_alias=True)))

    def send_cmds_to_online_tasmotas(
            self,
            tasmotas: List[TasmotaDevice],
            to_be_used_commands: List[str] | None = None,
            values_to_send: List[List[str | float | dict | int] | None] | None = None,
    ) -> List[TasmotaDevice]:
        to_be_used_commands = to_be_used_commands or [
            "RULE1",
            "RULE2",
            "RULE3",
            "TIMEZONE",
            "LATITUDE",
            "LONGITUDE",
            "TIMEDST",
            "TIMESTD",
            "TELEPERIOD",
            "POWERDELTA1",
            "SETOPTION4",
            "TIMER1",
            "TIMER2",
            "TIMER3",
            "TIMER4",
        ]

        values_to_send = values_to_send or [None for _ in tasmotas]

        assert len(values_to_send) == len(tasmotas), f"{len(values_to_send)=} =! {len(tasmotas)=}"

        tasmota_online: List[TasmotaDevice] = []
        values_to_send_online: List[List[str | float | dict | int] | None] = []

        for num, (tdo, vt) in enumerate(zip(tasmotas, values_to_send), start=1):
            assert tdo.tasmota_config is not None

            if not tdo.is_online():
                logger.debug(
                    f"[{num}]*OFFLINE* {tdo.tasmota_config.topic} -> {tdo.tasmota_config.topic} -> LWT={tdo.lwt_current_value}"
                )
            else:
                logger.debug(
                    f"[{num}]*ONLINE* {tdo.tasmota_config.device_name} -> {tdo.tasmota_config.topic} -> LWT={tdo.lwt_current_value}"
                )
                logger.debug(f"\t{vt=}")
                tasmota_online.append(tdo)
                values_to_send_online.append(vt)

                if vt:
                    assert len(vt) == len(to_be_used_commands), f"{len(vt)=} != {len(to_be_used_commands)=}"

        # TODO topics as parameters
        topics: List[str] = ["stat/+/RESULT", "stat/+/STATUS"]
        cmd_to_topic_map: Dict[str, str] = {}

        # cmnd/tasmota_0688AA/SetOption4 1 => enables mqtt result to stat/tasmota_06888F/[CMDNAME]
        for cmd in to_be_used_commands:
            if cmd[-1].isdigit():
                cmd_to_topic_map[cmd] = cmd[0:-1]
            else:
                cmd_to_topic_map[cmd] = cmd

        for v in set(cmd_to_topic_map.values()):
            topics.append(f"stat/+/{v}")

        logger.debug("cmd_to_topic_map:")
        logger.debug(cmd_to_topic_map)

        logger.debug("TOPICS:")
        logger.debug(topics)

        # logger.debug("Sleeping 10s")
        # time.sleep(10)

        assert self.mqttclient is not None and \
               self.mqttclient.host is not None and \
               self.mqttclient.port is not None and \
               self.mqttclient.username is not None and \
               self.mqttclient.password is not None

        # TODO: HT20251214 new connection really necessary here ?!
        mq: MosquittoClientWrapper = MosquittoClientWrapper(
            host=self.mqttclient.host,
            port=self.mqttclient.port,
            username=self.mqttclient.username,
            password=self.mqttclient.password,
            # topics=[f"stat/{td.tasmota_config.topic}/#"],
            topics=topics,
            timeout_connect_seconds=5,
        )

        # mq.add_message_callback("f"stat/{td.tasmota_config.topic}/")
        mq.wait_for_connect_and_start_loop()

        for num, (td, vt) in enumerate(zip(tasmota_online, values_to_send_online), start=1):
            assert td.tasmota_config is not None

            logger.debug(f"{num}: {td.tasmota_config.topic} -> {vt=}")

            tzconfig: Dict = td.tasmota_config.timezoneconfig.model_dump() if td.tasmota_config.timezoneconfig else {}

            for index, cmd in enumerate(to_be_used_commands):
                to_send_value: None | str | float | dict = None
                if vt:
                    to_send_value = vt[index]

                cmd_topic: str = f"cmnd/{td.tasmota_config.topic}/{cmd}"

                logger.debug(f"\t{cmd_topic=} -> {to_send_value=}")

                cmd_res: str = cmd_to_topic_map[cmd]

                result_topic: str = f"stat/{td.tasmota_config.topic}/RESULT"
                cmd_res_topic: str = f"stat/{td.tasmota_config.topic}/{cmd_res}"

                msg_received_cond: threading.Condition = threading.Condition()
                # msg_received_bool: bool = False
                resp_data: Dict[str, MWMqttMessage] = {}

                def msg_received(msg: MWMqttMessage, userdata: Any) -> None:
                    logger.debug(f"MSG Received :: {msg=} {userdata=}")

                    with msg_received_cond:
                        msg_received_cond.notify_all()
                        # msg_received_bool = True
                        resp_data[msg.topic] = msg

                # mq.set_on_msg_callback(msg_received, rettype="str")  # rettype="str" macht ein auto-try auf json-decode...
                mq.add_message_callback(sub=result_topic, callback=msg_received, rettype="str")
                mq.add_message_callback(sub=cmd_res_topic, callback=msg_received, rettype="str")

                # td.tasmota_config.tp[0] -> cmnd
                # td.tasmota_config.tp[1] ->stat
                # td.tasmota_config.tp[1] ->tele

                published_success: bool = mq.publish_one(topic=cmd_topic, value=to_send_value, timeout=5)
                logger.debug(
                    f"{cmd_topic} [{td.tasmota_config.device_name}] -> published {to_send_value=} -> {published_success=}"
                )

                if not published_success:
                    logger.debug("SKIPPING since not properly published...")
                    continue

                with msg_received_cond:
                    wait_success: bool = msg_received_cond.wait(timeout=10)
                    logger.debug(f"MSG[{result_topic}] -> WaitingSuccess {wait_success=}")
                    if not wait_success:
                        logger.debug("SKIPPING since no msg received properly...")
                        continue

                    wait2: bool = msg_received_cond.wait_for(
                        lambda: result_topic in resp_data or cmd_res_topic in resp_data, timeout=10
                    )
                    logger.debug(
                        f"Waiting for {result_topic}|{cmd_res_topic} [{td.tasmota_config.device_name}] to be in resp_data: {wait2=}"
                    )
                    if not wait2:
                        logger.debug("SKIPPING since response not received properly...")
                        continue

                msg_me: MWMqttMessage | None = resp_data.get(result_topic, resp_data.get(cmd_res_topic, None))
                logger.debug(f"{msg_me=}")

                assert msg_me is not None and msg_me.value is not None and isinstance(msg_me.value, dict)

                # {"Command":"Unknown"
                if "Command" in msg_me.value and msg_me.value["Command"] == "Unknown":
                    logger.debug("SKIPPING since command is not known to this DEVICE...")

                    if result_topic in resp_data:
                        del resp_data[result_topic]
                    if cmd_res_topic in resp_data:
                        del resp_data[cmd_res_topic]

                    continue

                match cmd:
                    case "RULE1":
                        td.tasmota_rule1 = TasmotaRule(**msg_me.value["Rule1"])
                    case "RULE2":
                        td.tasmota_rule2 = TasmotaRule(**msg_me.value["Rule2"])
                    case "RULE3":
                        td.tasmota_rule3 = TasmotaRule(**msg_me.value["Rule3"])
                    case "TIMEZONE" | "LATITUDE" | "LATITUDE" | "LONGITUDE" | "TIMEDST" | "TIMESTD":
                        tzconfig.update(**msg_me.value)
                    case "TELEPERIOD":
                        td.tasmota_config.teleperiod = msg_me.value["TelePeriod"]
                    case "POWERDELTA1":
                        td.tasmota_config.powerdelta1 = msg_me.value["PowerDelta1"]
                    case "SETOPTION4":
                        td.tasmota_config.setoption4 = msg_me.value["SetOption4"]
                    case "TIMER1":
                        td.tasmota_config.timer1 = msg_me.value["Timer1"]
                    case "TIMER2":
                        td.tasmota_config.timer2 = msg_me.value["Timer2"]
                    case "TIMER3":
                        td.tasmota_config.timer3 = msg_me.value["Timer3"]
                    case "TIMER4":
                        td.tasmota_config.timer4 = msg_me.value["Timer4"]

                    # 17:04:45.530 CMD: setoption4 1
                    # 17:04:45.535 MQT: stat/tasmota_AB65AA/SETOPTION = {"SetOption4":"ON"}
                    # 17:04:46.840 CMD: powerdelta
                    # 17:04:46.846 MQT: stat/tasmota_AB65AA/POWERDELTA = {"PowerDelta1":103}

                if result_topic in resp_data:
                    del resp_data[result_topic]
                if cmd_res_topic in resp_data:
                    del resp_data[cmd_res_topic]

                mq.remove_message_callback(sub=result_topic)
                mq.remove_message_callback(sub=cmd_res_topic)

            # logger.debug(f"tzconfig:{get_pretty_dict_json(tzconfig)}")
            if len(tzconfig) > 0:
                logger.debug("OLD TZ CONFIG:")
                if td.tasmota_config.timezoneconfig:
                    logger.debug(td.tasmota_config.timezoneconfig.model_dump())
                else:
                    logger.debug("NONE")

                td.tasmota_config.timezoneconfig = TasmotaTimezoneConfig(**tzconfig)
                logger.debug("NEW TZ CONFIG:")
                logger.debug(td.tasmota_config.timezoneconfig.model_dump())

            # logger.debug(get_pretty_dict_jsonnosort(td.model_dump(mode="python", exclude_none=False, exclude_defaults=False, by_alias=False)))

        mq.disconnect()

        return tasmotas

    def ensure_correct_timezone_settings_for_tasmotas(self, online_tasmotas: List[TasmotaDevice], timezoneconfig: Optional[TasmotaTimezoneConfig] = None) -> List[TasmotaDevice]:
        timezoneconfig = timezoneconfig or TasmotaTimezoneConfig(
            latitude=53.6437753,
            longitude=9.8940783,
            timedst=TasmotaTimeZoneDSTSTD.from_tasmota_command_string("0,0,3,1,1,120"),
            timestd=TasmotaTimeZoneDSTSTD.from_tasmota_command_string("0,0,10,1,1,60"),
            timezone=99
        )

        assert timezoneconfig is not None

        to_be_updated_tasmotas: List[TasmotaDevice] = []

        to_be_sent_commands: List[str] = ["Latitude", "Longitude", "TimeDST", "TimeSTD", "TimeZone"]
        values_to_send: list[list[str | float | dict | int] | None] = []

        for tdo in online_tasmotas:
            assert tdo.tasmota_config is not None and tdo.tasmota_config.timezoneconfig is not None

            if tdo.is_online() and tdo.tasmota_config.timezoneconfig.timezone != 99:
                logger.debug(
                    f"TIMEZONE is off for {tdo.tasmota_config.device_name} -> {tdo.tasmota_config.topic} -> TIMEZONE={tdo.tasmota_config.timezoneconfig.timezone}"
                )
                to_be_updated_tasmotas.append(tdo)
                values_to_send.append(timezoneconfig.as_tasmota_command_list())
                # WAS:
                # values_to_send.append(
                #                 [
                #                     53.6437753,
                #                     9.8940783,
                #                     "0,0,3,1,1,120",
                #                     "0,0,10,1,1,60",
                #                     99
                #                 ]
                #             )

        return self.send_cmds_to_online_tasmotas(
            tasmotas=online_tasmotas,
            to_be_used_commands=to_be_sent_commands,
            values_to_send=values_to_send
        )


    def update_online_tasmotas(self, tasmotas: List[TasmotaDevice]) -> List[TasmotaDevice]:
        tasmota_online: List[TasmotaDevice] = []

        for tdo in tasmotas:
            if not tdo.is_online():
                continue

        for num, tdo in enumerate(tasmotas, start=1):
            assert tdo.tasmota_config is not None

            if not tdo.is_online():
                logger.debug(
                    f"[{num}]*OFFLINE* {tdo.tasmota_config.topic} -> {tdo.tasmota_config.topic} -> LWT={tdo.lwt_current_value}"
                )
            else:
                logger.debug(
                    f"[{num}]*ONLINE* {tdo.tasmota_config.device_name} -> {tdo.tasmota_config.topic} -> LWT={tdo.lwt_current_value}"
                )
                tasmota_online.append(tdo)

        tasmota_online = self.send_cmds_to_online_tasmotas(
            tasmotas=tasmota_online,
            to_be_used_commands=None,  # nimmt dann die default status-commands...
            values_to_send=None,  # sendet dann empty command -> returned nur den status
        )

        return tasmota_online

    def read_tasmotas_from_file_update_save_to_file(self) -> None:
        tds: List[TasmotaDevice] | None = read_tasmotas_from_latest_file()

        if not tds:
            return

        tds_dumps: List[str] = [
            get_pretty_dict_json_no_sort(
                td.model_dump(mode="python", exclude_none=False, exclude_defaults=False, by_alias=False)
            )
            for td in tds
        ]

        online_tasmotas: List[TasmotaDevice] = self.filter_online_tasmotas_from_retained(
            all_tasmotas=tds,
            update_lwt_current_value=True
        )

        updated_tasmotas: List[TasmotaDevice] = self.update_online_tasmotas(
            tasmotas=online_tasmotas
        )  # das update_online_tasmots macht AUCH ein inline update -> tds[X] wird aktualisiert...

        for index, td in enumerate(tds):
            mydump: str = get_pretty_dict_json_no_sort(
                td.model_dump(mode="python", exclude_none=False, exclude_defaults=False, by_alias=False)
            )
            previous_data: str = tds_dumps[index]

            diff_str: StringIO = StringIO()
            changecount: int = 0
            for l in difflib.unified_diff(previous_data, mydump, fromfile=f"PREVIOUS", tofile=f"UPDATED"):
                diff_str.write(l)
                changecount += 1

            assert td.tasmota_config is not None
            if changecount > 0:
                logger.debug(
                    f"{td.tasmota_config.topic} -> [{changecount=}]\n{textwrap.indent(diff_str.getvalue(), "\t")}")
            else:
                logger.debug(f"{td.tasmota_config.topic} -> NOTHING CHANGED.")

        write_tasmota_devices_file(tasmotas=tds)



    def get_all_tasmota_devices_from_retained(self,
            topics: List[str] | None = None, noisy: bool = False, noisy_lowerlevel: bool = False
    ) -> list[TasmotaDevice]:
        topics = topics or TASMOTA_DEFAULT_TOPICS
        ret: list[TasmotaDevice] = []


        msgs: list[MWMqttMessage] | None = self.get_all_retained(
            topics=topics,
            retained_msgs_receive_grace_ms=2_000,
            rettype="json",
            noisy=noisy_lowerlevel,
            fallback_rettype="str_raw",
        )

        tdlookup: dict[str, TasmotaDevice] = {}
        td: TasmotaDevice | None

        if msgs:
            # first run for discovery...
            for num, msg in enumerate(msgs, start=1):
                if noisy:
                    logger.debug(f"DIS [{num:03}] {msg.topic}\t[{type(msg.value)=}] {msg.value}")

                if msg.topic.startswith(TASMOTA_DISCOVERY_TOPIC_BEGIN):
                    maclookupkey: str = msg.topic[0: msg.topic.rfind("/")]
                    maclookupkey = maclookupkey[maclookupkey.rfind("/") + 1:]

                    td = tdlookup.get(maclookupkey)
                    if noisy:
                        logger.debug(f"LOOKUP [{msg.topic}] for {maclookupkey} GOT: {td=}")
                    if td is None:
                        td = TasmotaDevice()
                        tdlookup[maclookupkey] = td
                        ret.append(td)

                    if msg.topic.endswith("config"):
                        assert isinstance(msg.value, dict)
                        td.tasmota_config = TasmotaDeviceConfig(**msg.value)
                        if noisy:
                            logger.debug(
                                get_pretty_dict_json_no_sort(
                                    td.model_dump(mode="python", exclude_none=False, exclude_defaults=False,
                                                  by_alias=False)
                                )
                            )

                        assert td.tasmota_config.topic
                        tdlookup[td.tasmota_config.topic] = td
                    elif msg.topic.endswith("sensors"):
                        assert isinstance(msg.value, dict)
                        td.tasmota_sensors = TasmotaDeviceSensors(**msg.value)
                        if noisy:
                            logger.debug(
                                get_pretty_dict_json_no_sort(
                                    td.model_dump(mode="python", exclude_none=False, exclude_defaults=False,
                                                  by_alias=False)
                                )
                            )

            # second run for LWT status
            for num, msg in enumerate(msgs, start=1):
                if noisy:
                    logger.debug(f"LWT [{num:03}] {msg.topic}\t[{type(msg.value)=}] {msg.value}")

                if msg.topic.startswith(TASMOTA_LWT_TOPIC_BEGIN) and msg.topic.endswith(TASMOTA_LWT_TOPIC_END):
                    mytopic: str = msg.topic.split("/")[1]

                    td = tdlookup.get(mytopic)
                    if noisy:
                        logger.debug(f"LOOKUP [{msg.topic}] for {mytopic} GOT: {td=}")

                    if td is None:
                        td = TasmotaDevice()
                        td.tasmota_config = TasmotaDeviceConfig()  # type: ignore
                        td.tasmota_config.topic = mytopic

                        tdlookup[mytopic] = td
                        ret.append(td)

                    td.lwt_current_value = msg.value  # type: ignore

        return ret

    def filter_online_tasmotas_from_retained(self,
            all_tasmotas: List[TasmotaDevice], update_lwt_current_value: bool = True
    ) -> List[TasmotaDevice]:
        all_online_tasmotas: List[TasmotaDevice] = self.get_all_tasmota_devices_from_retained()

        online_topics: Dict[str, Literal["Online", "Offline"] | None] = {}

        ret: List[TasmotaDevice] = []
        for tdo in all_online_tasmotas:
            assert tdo.tasmota_config is not None

            if tdo.is_online():
                online_topics[tdo.tasmota_config.topic] = tdo.lwt_current_value  # type: ignore
                logger.debug(f"ONLINE: {tdo.tasmota_config.topic}")
            else:
                logger.debug(f"OFFLINE: {tdo.tasmota_config.topic}")

        for tdo in all_tasmotas:
            assert tdo.tasmota_config is not None

            if tdo.tasmota_config.topic in online_topics:
                if update_lwt_current_value:
                    tdo.lwt_current_value = online_topics[tdo.tasmota_config.topic]
                ret.append(tdo)

        # online_tasmotas: List[TasmotaDevice] = update_online_tasmotas(tasmotas=all_tasmotas)  # also does updates INLINE !!!

        return ret


def write_tasmota_devices_file(tasmotas: List[TasmotaDevice], fp: Path | None = None, noisy: bool = False, timezone: tzinfo=pytz.timezone("Europe/Berlin")) -> Path:
    if fp is None:
        fp = Path(__file__)
        fp = Path(fp.parent.resolve(), "tasmotas")
        if not fp.exists():
            fp.mkdir()

        now: datetime = datetime.now(tz=timezone)
        fp = Path(fp, f"tasmota_devices_{now:%d-%m-%Y_%H%M%S}.json")

    with open(fp, "w") as fout:
        fout.write("[\n")

        for num, tasmota in enumerate(tasmotas, start=1):
            if num > 1:
                fout.write(",\n")

            outs: str = get_pretty_dict_json_no_sort(
                tasmota.model_dump(mode="python", exclude_none=False, exclude_defaults=False, by_alias=False)
            )

            if noisy:
                logger.debug(f"[{num}]\n{outs}")

            fout.write(outs)

        fout.write("\n]\n")
        fout.flush()

    logger.info(f"TASMOTA DEVICES WRITTEN TO: {fp.resolve()}")

    return fp


def read_tasmotas_from_latest_file(
    tasmota_json_dir: Path | None = None, noisy: bool = False, timezone: tzinfo=pytz.timezone("Europe/Berlin")
) -> Optional[List[TasmotaDevice]]:
    if tasmota_json_dir is None:
        tasmota_json_dir = Path(__file__)
        tasmota_json_dir = Path(tasmota_json_dir.parent.resolve(), "tasmotas")
        if not tasmota_json_dir.exists():
            tasmota_json_dir.mkdir()

    jsonfiles: List[Path] = [fm for fm in tasmota_json_dir.glob("tasmota_devices_*json")]
    jsonfiles = sorted(jsonfiles, key=lambda p: os.stat(p).st_mtime, reverse=True)

    for f in jsonfiles:
        dateme: datetime = datetime.fromtimestamp(os.stat(f).st_mtime, tz=timezone)
        logger.debug(f"{f.absolute()} -> {dateme}")

        json_data: List[Dict] | Dict | None = None
        with open(f) as fin:
            json_data = json.load(fin)

        if json_data and type(json_data) is list:
            ret: List[TasmotaDevice] = []
            for td_dict in json_data:
                tdm: TasmotaDevice = TasmotaDevice(**td_dict)
                ret.append(tdm)
            return ret
    return None