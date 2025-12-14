from datetime import datetime
from io import StringIO
from typing import Optional, Annotated, List, Literal, Any, Self

from pydantic import BaseModel, Field, AliasPath, field_validator, AliasChoices
from pydantic.networks import IPv4Address
from pydantic_extra_types.mac_address import MacAddress


class TasmotaTimerConfig(BaseModel):
    # Enable	0 = disarm or disable timer
    # 1 = arm or enable timer
    enable: Optional[Annotated[int, Field(ge=0, le=1)]] = Field(None, validation_alias=AliasChoices("Enable", "enable"))

    # Mode	0 = use clock time
    # 1 = Use local sunrise time using Longitude, Latitude and Time offset
    # 2 = use local sunset time using Longitude, Latitude and Time offset
    mode: Optional[Annotated[int, Field(ge=0, le=2)]] = Field(None, validation_alias=AliasChoices("Mode", "mode"))

    # Time	When Mode 0 is active
    # > hh:mm = set time in hours 0 .. 23 and minutes 0 .. 59
    # When Mode 1 or Mode 2 is active
    # > +hh:mm or -hh:mm = set offset in hours 0 .. 11 and minutes 0 .. 59 from the time defined by sunrise/sunset.
    time: Optional[str] = Field(None, validation_alias=AliasChoices("Time", "time"))

    # Window	0..15 = add or subtract a random number of minutes to Time
    window: Optional[Annotated[int, Field(ge=0, le=15)]] = Field(
        None, validation_alias=AliasChoices("Window", "window")
    )

    # Days	SMTWTFS = set day of weeks mask where 0 or - = OFF and any different character = ON
    days: Optional[Annotated[str, Field(pattern="[1|0|-]{7}")]] = Field(
        None, validation_alias=AliasChoices("Days", "days")
    )

    # Repeat	0 = allow timer only once
    # 1 = repeat timer execution
    repeat: Optional[Annotated[int, Field(ge=0, le=1)]] = Field(None, validation_alias=AliasChoices("Repeat", "repeat"))

    # Output	1..16 = select an output to be used if no rule is enabled
    output: Optional[Annotated[int, Field(ge=1, le=16)]] = Field(
        None, validation_alias=AliasChoices("Output", "output")
    )

    # Action	0 = turn output OFF
    # 1 = turn output ON
    # 2 = TOGGLE output
    # 3 = RULE/BLINK
    # If the Tasmota Rules feature has been activated by compiling the code (activated by default in all pre-compiled Tasmota binaries), a rule with Clock#Timer=<timer> will be triggered if written and turned on by the user.
    # If Rules are not compiled, BLINK output using BlinkCount parameters.
    action: Optional[Annotated[int, Field(ge=1, le=16)]] = Field(
        None, validation_alias=AliasChoices("Action", "action")
    )

    # {"Timer1":{"Enable":1,"Mode":0,"Time":"22:00","Window":0,"Days":"1111111","Repeat":1,"Output":1,"Action":0}}


class TasmotaTimeZoneDSTSTD(BaseModel):
    hemisphere: Optional[int] = Field(None, validation_alias=AliasChoices("Hemisphere", "hemisphere"))
    week: Optional[int] = Field(None, validation_alias=AliasChoices("Week", "week"))
    month: Optional[int] = Field(None, validation_alias=AliasChoices("Month", "month"))
    day: Optional[int] = Field(None, validation_alias=AliasChoices("Day", "day"))
    hour: Optional[int] = Field(None, validation_alias=AliasChoices("Hour", "hour"))
    offset: Optional[int] = Field(None, validation_alias=AliasChoices("Offset", "offset"))

    def to_tasmota_command_string(self) -> str:
        return str([self.hemisphere,self.week,self.month,self.day,self.hour,self.offset]).replace(" ", "")

    @classmethod
    def from_tasmota_command_string(cls, values_comma_separated: str) -> TasmotaTimeZoneDSTSTD:
        data: List[str] = values_comma_separated.split(",")

        assert len(data) == 6

        return TasmotaTimeZoneDSTSTD(
            hemisphere=int(data[0]),
            week=int(data[1]),
            month=int(data[2]),
            day=int(data[3]),
            hour=int(data[4]),
            offset=int(data[5])
        )

class TasmotaTimezoneConfig(BaseModel):
    latitude: Optional[float] = Field(None, validation_alias=AliasChoices("Latitude", "latitude"))
    longitude: Optional[float] = Field(None, validation_alias=AliasChoices("Longitude", "longitude"))
    timedst: Optional[TasmotaTimeZoneDSTSTD] = Field(None, validation_alias=AliasChoices("TimeDst", "timedst"))
    timestd: Optional[TasmotaTimeZoneDSTSTD] = Field(None, validation_alias=AliasChoices("TimeStd", "timestd"))
    timezone: Optional[int | str] = Field(None, validation_alias=AliasChoices("Timezone", "timezone"))  # 99 | +01:00

    def as_tasmota_command_list(self) -> List[str | float | dict[Any, Any] | int] | None:
        assert self.latitude is not None and \
            self.longitude is not None and \
            self.timedst is not None and \
            self.timestd is not None and \
            self.timezone is not None

        return [
                self.latitude,
                self.longitude,
                self.timedst.to_tasmota_command_string(),  # that is correct!
                self.timestd.to_tasmota_command_string(),  # that is correct!
                self.timezone
            ]

    def to_tasmota_command_string(self) -> str:
        return str(self.as_tasmota_command_list()).replace(" ", "")


class TasmotaDeviceConfig(BaseModel):
    friendly_name: Optional[str] = Field(
        None, validation_alias=AliasChoices("friendly_name", AliasPath("fn", 0))
    )  # friendly name -> first element of list of strings?
    device_name: Optional[str] = Field(None, validation_alias=AliasChoices("dn", "device_name"))
    hostname: Optional[str] = Field(None, validation_alias=AliasChoices("hn", "hostname"))  # host name
    manufacturer_description: Optional[str] = Field(
        None, validation_alias=AliasChoices("md", "manufacturer_description")
    )  # manufacturer description ?!
    ip: Optional[IPv4Address] = None
    mac: Optional[MacAddress] = None
    offline_msg: Optional[str] = Field(None, validation_alias=AliasChoices("ofln", "offline_msg"))
    online_msg: Optional[str] = Field(None, validation_alias=AliasChoices("onln", "online_msg"))
    state: Optional[List[str]] = None
    # t: str = Field(alias="topic", validation_alias='t')
    topic: Optional[str] = Field(None, validation_alias=AliasChoices("t", "topic"))
    tp: Optional[List[str]] = Field(None)
    software_version: Optional[str] = Field(None, validation_alias=AliasChoices("sw", "software_version"))
    timezoneconfig: Optional[TasmotaTimezoneConfig] = None
    teleperiod: Optional[int] = Field(None, validation_alias=AliasChoices("TelePeriod", "teleperiod"))
    powerdelta1: Optional[int] = Field(None, validation_alias=AliasChoices("PowerDelta1", "powerdelta1"))
    setoption4: Optional[Literal["ON", "OFF"]] = Field(None, validation_alias=AliasChoices("SetOption4", "setoption4"))
    timer1: Optional[TasmotaTimerConfig] = Field(None, validation_alias=AliasChoices("Timer1", "timer1"))
    timer2: Optional[TasmotaTimerConfig] = Field(None, validation_alias=AliasChoices("Timer2", "timer2"))
    timer3: Optional[TasmotaTimerConfig] = Field(None, validation_alias=AliasChoices("Timer2", "timer3"))
    timer4: Optional[TasmotaTimerConfig] = Field(None, validation_alias=AliasChoices("Timer4", "timer4"))

    # SSID1
    # SSID2
    # powerdelta
    # ampres
    # voltres
    # setoption4
    # SetOption53 1; SetOption56 0; SetOption57 0;

    @field_validator("mac", mode="before")
    @classmethod
    def validate_mac(cls, v: Any) -> Optional[str]:
        # logger.debug(f"VALIDATE MAC: {v}")
        if not v:
            return None

        return cls.mac_no_colon_to_colon(v)

    @staticmethod
    def mac_no_colon_to_colon(mac: str) -> str:
        if mac.find(":") == 2:
            return mac

        ret: StringIO = StringIO()
        for ch2i in range(0, len(mac), 2):
            if ret.tell() > 0:
                ret.write(":")
            ret.write(mac[ch2i : ch2i + 2])

        return ret.getvalue()


class TasmotaRule(BaseModel):
    state: Optional[Literal["ON", "OFF"]] = Field(None, validation_alias=AliasChoices("State", "state"))
    once: Optional[Literal["ON", "OFF"]] = Field(None, validation_alias=AliasChoices("Once", "once"))
    stoponerror: Optional[Literal["ON", "OFF"]] = Field(
        None, validation_alias=AliasChoices("StopOnError", "stoponerror")
    )
    length: Optional[int] = Field(None, validation_alias=AliasChoices("Length", "length"))
    rules: Optional[str] = Field(None, validation_alias=AliasChoices("Rules", "rules"))


class TasmotaDeviceSensors(BaseModel):
    # tasmota/discovery/x/sensors
    # sn: dict
    time: datetime = Field(..., validation_alias=AliasChoices("time", "Time", AliasPath("sn", "Time")))

    # {"sn": {"Time": "2024-07-04T13:09:25", "ANALOG": {"A0": 169},
    #        "SHT3X": {"Temperature": 26.1, "Humidity": 44.5, "DewPoint": 13.1}, "TempUnit": "C"}, "ver": 1}


class TasmotaDevice(BaseModel):
    # tasmota/discovery/x/config
    tasmota_config: Optional[TasmotaDeviceConfig] = None
    tasmota_sensors: Optional[TasmotaDeviceSensors] = None
    tasmota_rule1: Optional[TasmotaRule] = None
    tasmota_rule2: Optional[TasmotaRule] = None
    tasmota_rule3: Optional[TasmotaRule] = None

    lwt_current_value: Optional[Literal["Online", "Offline"]] = None

    def is_online(self, lwt_online_default_value: str = "Online") -> bool:
        if self.tasmota_config and self.tasmota_config.online_msg:
            return self.lwt_current_value == self.tasmota_config.online_msg

        return self.lwt_current_value == lwt_online_default_value
