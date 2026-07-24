"""Setup flow for the ezBEQ integration: enter IP + port, auto-discover DSPs."""

import logging
from typing import Any

from ucapi import RequestUserInput
from ucapi_framework import BaseSetupFlow

from uc_intg_ezbeq.client import EzbeqClient
from uc_intg_ezbeq.config import EzbeqConfig
from uc_intg_ezbeq.const import DEFAULT_EZBEQ_PORT

_LOG = logging.getLogger(__name__)


class EzbeqSetupFlow(BaseSetupFlow[EzbeqConfig]):
    """Single screen: ezBEQ server IP + port. DSP devices are discovered."""

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "ezBEQ Server Setup"},
            [
                {
                    "id": "info",
                    "label": {"en": "ezBEQ Server"},
                    "field": {"label": {"value": {"en": "Enter the IP address and port of your ezBEQ server. Your DSP devices and the BEQ catalogue are discovered automatically."}}},
                },
                {"id": "name", "label": {"en": "Name"}, "field": {"text": {"value": "ezBEQ"}}},
                {"id": "host", "label": {"en": "ezBEQ IP address"}, "field": {"text": {"value": ""}}},
                {"id": "port", "label": {"en": "ezBEQ port"}, "field": {"number": {"value": DEFAULT_EZBEQ_PORT, "min": 1, "max": 65535}}},
            ],
        )

    async def query_device(self, input_values: dict[str, Any]) -> EzbeqConfig | RequestUserInput:
        host = input_values.get("host", "").strip()
        if not host:
            raise ValueError("ezBEQ server IP address is required")
        try:
            port = int(input_values.get("port", DEFAULT_EZBEQ_PORT))
        except (TypeError, ValueError):
            port = DEFAULT_EZBEQ_PORT
        name = input_values.get("name", "").strip() or "ezBEQ"

        client = EzbeqClient(host, port)
        try:
            if not await client.test_connection():
                raise ValueError(f"Cannot reach an ezBEQ server at {host}:{port}")
            devices_state = await client.get_devices()
        finally:
            await client.close()

        devices = [
            {"name": dsp_name, "slots": len(state.get("slots", [])) or 1}
            for dsp_name, state in devices_state.items()
            if isinstance(state, dict)
        ]
        if not devices:
            raise ValueError(
                "ezBEQ is reachable but has no DSP devices configured. "
                "Add a device (miniDSP, HTP-1, JRiver, …) in ezBEQ first."
            )

        _LOG.info("ezBEQ %s:%d — discovered %d DSP device(s): %s", host, port, len(devices),
                  ", ".join(f"{d['name']}({d['slots']})" for d in devices))
        return EzbeqConfig(
            identifier=f"ezbeq_{host.replace('.', '_')}_{port}",
            name=name, host=host, port=port, devices=devices,
        )
