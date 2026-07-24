"""ezBEQ per-slot Sensor entities (show what BEQ is loaded in each slot)."""

import logging

from ucapi import sensor
from ucapi_framework import SensorEntity

from uc_intg_ezbeq.config import EzbeqConfig
from uc_intg_ezbeq.device import EzbeqDevice

_LOG = logging.getLogger(__name__)


class EzbeqSlotSensor(SensorEntity):
    """Shows the BEQ currently loaded in one slot of a DSP device."""

    def __init__(
        self, device_config: EzbeqConfig, device: EzbeqDevice, dsp: dict, dsp_index: int, slot_id: int
    ) -> None:
        self._device = device
        self._dsp_name = dsp["name"]
        self._slot_id = str(slot_id)
        entity_id = f"sensor.{device_config.identifier}.d{dsp_index}s{slot_id}"
        super().__init__(
            entity_id,
            f"{self._dsp_name} Slot {slot_id}",
            [],
            {
                sensor.Attributes.STATE: sensor.States.UNKNOWN,
                sensor.Attributes.VALUE: "",
            },
            device_class=sensor.DeviceClasses.CUSTOM,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({sensor.Attributes.STATE: sensor.States.UNAVAILABLE})
            return
        slot = self._device.slot(self._dsp_name, self._slot_id)
        self.update({
            sensor.Attributes.STATE: sensor.States.ON,
            sensor.Attributes.VALUE: self._device.slot_loaded_text(slot),
        })


def create_sensors(device_config: EzbeqConfig, device: EzbeqDevice) -> list[EzbeqSlotSensor]:
    sensors: list[EzbeqSlotSensor] = []
    for dsp_index, dsp in enumerate(device_config.devices):
        for slot_id in range(1, int(dsp.get("slots", 1) or 1) + 1):
            sensors.append(EzbeqSlotSensor(device_config, device, dsp, dsp_index, slot_id))
    return sensors
