"""ezBEQ target-slot Select entity (one per DSP device)."""

import logging
from typing import Any

from ucapi import StatusCodes, select
from ucapi_framework import SelectEntity

from uc_intg_ezbeq.config import EzbeqConfig
from uc_intg_ezbeq.device import EzbeqDevice

_LOG = logging.getLogger(__name__)


class EzbeqSlotSelect(SelectEntity):
    """Picks the target slot that browse/load actions apply to."""

    def __init__(self, device_config: EzbeqConfig, device: EzbeqDevice, dsp: dict, index: int) -> None:
        self._device = device
        self._dsp_name = dsp["name"]
        slots = int(dsp.get("slots", 1) or 1)
        self._options = [f"Slot {i}" for i in range(1, slots + 1)]
        entity_id = f"select.{device_config.identifier}.{index}"
        super().__init__(
            entity_id,
            f"{self._dsp_name} Slot",
            {
                select.Attributes.STATE: select.States.UNKNOWN,
                select.Attributes.OPTIONS: self._options,
                select.Attributes.CURRENT_OPTION: "",
            },
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    def _current_label(self) -> str:
        slot = self._device.selected_slot(self._dsp_name)
        label = f"Slot {slot}"
        return label if label in self._options else (self._options[0] if self._options else "")

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({select.Attributes.STATE: select.States.UNAVAILABLE})
            return
        self.update({
            select.Attributes.STATE: select.States.ON,
            select.Attributes.OPTIONS: self._options,
            select.Attributes.CURRENT_OPTION: self._current_label(),
        })

    async def _handle_command(self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any) -> StatusCodes:
        try:
            if cmd_id == select.Commands.SELECT_OPTION:
                option = (params or {}).get("option", "")
            elif cmd_id in (select.Commands.SELECT_NEXT, select.Commands.SELECT_PREVIOUS,
                            select.Commands.SELECT_FIRST, select.Commands.SELECT_LAST):
                if not self._options:
                    return StatusCodes.NOT_IMPLEMENTED
                idx = self._options.index(self._current_label()) if self._current_label() in self._options else 0
                mapping = {
                    select.Commands.SELECT_NEXT: (idx + 1) % len(self._options),
                    select.Commands.SELECT_PREVIOUS: (idx - 1) % len(self._options),
                    select.Commands.SELECT_FIRST: 0,
                    select.Commands.SELECT_LAST: len(self._options) - 1,
                }
                option = self._options[mapping[cmd_id]]
            else:
                return StatusCodes.NOT_IMPLEMENTED
            if option not in self._options:
                return StatusCodes.BAD_REQUEST
            self._device.set_selected_slot(self._dsp_name, option.replace("Slot ", "").strip())
            self.update({select.Attributes.CURRENT_OPTION: option})
            return StatusCodes.OK
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Slot select error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR


def create_selects(device_config: EzbeqConfig, device: EzbeqDevice) -> list[EzbeqSlotSelect]:
    return [
        EzbeqSlotSelect(device_config, device, dsp, index)
        for index, dsp in enumerate(device_config.devices)
    ]
