import sys

from loguru import logger

import mqttcommander
from mqttcommander import cli

mqttcommander.configure_loguru_default_with_skiplog_filter()
logger.enable("mqttcommander")

from config import settings

if __name__ == "__main__":
    # cli.main()

    # Settings in argv-Format konvertieren
    mqtt_args = [
        "--host",
        settings.mqtt.host,
        "--port",
        str(settings.mqtt.port),
        "--username",
        settings.mqtt.username,
        "--password",
        settings.mqtt.password,
        # "list-online"
        # Weitere CLI-Args hier, z.B.:
        # "list-online"
    ]

    # remaining argv are just passed in...
    cli.main(mqtt_args + sys.argv[1:])
