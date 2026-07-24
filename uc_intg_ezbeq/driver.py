"""Integration driver for ezBEQ."""

from ucapi_framework import BaseIntegrationDriver

from uc_intg_ezbeq.config import EzbeqConfig
from uc_intg_ezbeq.device import EzbeqDevice
from uc_intg_ezbeq.media_player import create_media_players
from uc_intg_ezbeq.select import create_selects
from uc_intg_ezbeq.sensor import create_sensors


class EzbeqDriver(BaseIntegrationDriver[EzbeqDevice, EzbeqConfig]):
    """Connects to an ezBEQ server and builds a media_player + slot Select +
    per-slot Sensors for each DSP device it manages."""

    def __init__(self) -> None:
        super().__init__(
            device_class=EzbeqDevice,
            entity_classes=[
                create_media_players,
                create_selects,
                create_sensors,
            ],
            driver_id="uc_intg_ezbeq",
        )
