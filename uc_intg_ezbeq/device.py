"""ezBEQ server device (WebSocket push + polling fallback)."""

import asyncio
import json
import logging
from typing import Any

import aiohttp

from ucapi_framework import WebSocketPollingDevice

from uc_intg_ezbeq.client import EzbeqClient
from uc_intg_ezbeq.config import EzbeqConfig
from uc_intg_ezbeq.const import SLOT_EMPTY, STATE_ON, STATE_UNAVAILABLE

_LOG = logging.getLogger(__name__)


class EzbeqDevice(WebSocketPollingDevice):
    """One ezBEQ server. Maintains the live state of every DSP device it
    manages and exposes helpers used by the media_player / select / sensor
    entities."""

    def __init__(self, device_config: EzbeqConfig, **kwargs: Any) -> None:
        super().__init__(
            device_config,
            poll_interval=30,
            ping_interval=0,  # aiohttp ws heartbeat handles keepalive
            **kwargs,
        )
        self._device_config = device_config
        self._client = EzbeqClient(device_config.host, device_config.port)
        self._devices: dict[str, dict] = {}
        self._selected_slot: dict[str, str] = {}
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._state: str = STATE_UNAVAILABLE

    # -- identity ------------------------------------------------------
    @property
    def identifier(self) -> str:
        return self._device_config.identifier

    @property
    def name(self) -> str:
        return self._device_config.name

    @property
    def address(self) -> str:
        return self._device_config.host

    @property
    def log_id(self) -> str:
        return f"{self.name} ({self.address}:{self._device_config.port})"

    @property
    def state(self) -> str:
        return self._state

    @property
    def available(self) -> bool:
        return self._state == STATE_ON

    @property
    def client(self) -> EzbeqClient:
        return self._client

    # -- state accessors used by entities ------------------------------
    def dsp_state(self, dsp_name: str) -> dict | None:
        return self._devices.get(dsp_name)

    def slots(self, dsp_name: str) -> list[dict]:
        state = self._devices.get(dsp_name)
        return state.get("slots", []) if state else []

    def slot(self, dsp_name: str, slot_id: str) -> dict | None:
        for s in self.slots(dsp_name):
            if str(s.get("id")) == str(slot_id):
                return s
        return None

    def master_volume(self, dsp_name: str) -> float | None:
        state = self._devices.get(dsp_name)
        return state.get("masterVolume") if state else None

    def is_muted(self, dsp_name: str) -> bool:
        state = self._devices.get(dsp_name)
        return bool(state.get("mute")) if state else False

    def selected_slot(self, dsp_name: str) -> str:
        slots = self.slots(dsp_name)
        default = str(slots[0]["id"]) if slots else "1"
        return self._selected_slot.get(dsp_name, default)

    def set_selected_slot(self, dsp_name: str, slot_id: str) -> None:
        self._selected_slot[dsp_name] = str(slot_id)
        self.push_update()

    # -- commands ------------------------------------------------------
    async def load_entry(self, dsp_name: str, entry: str) -> bool:
        slot = self.selected_slot(dsp_name)
        try:
            state = await self._client.load(dsp_name, slot, entry)
            self._apply_state(dsp_name, state)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Load failed (%s slot %s): %s", self.log_id, dsp_name, slot, err)
            return False

    async def clear_slot(self, dsp_name: str, slot_id: str | None = None) -> bool:
        slot = str(slot_id) if slot_id is not None else self.selected_slot(dsp_name)
        try:
            state = await self._client.clear(dsp_name, slot)
            self._apply_state(dsp_name, state)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Clear failed (%s slot %s): %s", self.log_id, dsp_name, slot, err)
            return False

    async def set_volume(self, dsp_name: str, gain: float) -> bool:
        try:
            state = await self._client.set_master_volume(dsp_name, gain)
            self._apply_state(dsp_name, state)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Set volume failed: %s", self.log_id, err)
            return False

    async def set_mute(self, dsp_name: str, mute: bool) -> bool:
        try:
            state = await self._client.set_mute(dsp_name, mute)
            self._apply_state(dsp_name, state)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Set mute failed: %s", self.log_id, err)
            return False

    def _apply_state(self, dsp_name: str, state: Any) -> None:
        """Merge a device state returned by a command/broadcast."""
        if isinstance(state, dict) and state.get("name"):
            self._devices[state["name"]] = state
        elif isinstance(state, dict) and dsp_name in state:
            self._devices.update(state)
        self._state = STATE_ON
        self.push_update()

    # -- WebSocket -----------------------------------------------------
    async def create_websocket(self) -> Any:
        session = await self._client.session()
        self._ws = await session.ws_connect(self._client.ws_url, heartbeat=30)
        # Seed state via REST so entities populate immediately.
        await self._refresh_devices()
        self._loop.create_task(self._prefetch_catalogue())
        return self._ws

    async def _prefetch_catalogue(self) -> None:
        from uc_intg_ezbeq import browser
        await browser.prefetch(self)

    async def close_websocket(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    async def receive_message(self) -> Any:
        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                return json.loads(msg.data)
            except (ValueError, TypeError):
                return {}
        if msg.type in (
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.ERROR,
        ):
            return None
        return {}

    async def handle_message(self, message: Any) -> None:
        if not isinstance(message, dict):
            return
        if message.get("message") == "DeviceState":
            data = message.get("data")
            if isinstance(data, dict) and data.get("name"):
                self._devices[data["name"]] = data
                self._state = STATE_ON
                self.push_update()

    # -- Polling fallback ----------------------------------------------
    async def establish_connection(self) -> None:
        await self._refresh_devices()
        self._loop.create_task(self._prefetch_catalogue())

    async def poll_device(self) -> None:
        await self._refresh_devices()

    async def _refresh_devices(self) -> None:
        try:
            devices = await self._client.get_devices()
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.debug("[%s] Poll failed: %s", self.log_id, err)
            if self._state != STATE_UNAVAILABLE and not self.is_connected:
                self._state = STATE_UNAVAILABLE
                self.push_update()
            return
        if devices:
            self._devices = devices
            self._state = STATE_ON
            self.push_update()

    # -- lifecycle -----------------------------------------------------
    async def disconnect(self, stop_polling: bool | None = None) -> None:
        await super().disconnect(stop_polling=stop_polling)
        if stop_polling:
            await self._client.close()
            self._state = STATE_UNAVAILABLE

    @staticmethod
    def slot_loaded_text(slot: dict | None) -> str:
        if not slot:
            return SLOT_EMPTY
        title = slot.get("last") or SLOT_EMPTY
        author = slot.get("author")
        if title != SLOT_EMPTY and author:
            return f"{title} ({author})"
        return title
