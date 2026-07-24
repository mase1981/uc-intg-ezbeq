"""Async REST + WebSocket client for an ezBEQ server."""

import logging
from typing import Any

import aiohttp

from uc_intg_ezbeq.const import (
    API_AUDIOTYPES,
    API_AUTHORS,
    API_CONTENTTYPES,
    API_DEVICE_PATCH,
    API_DEVICES,
    API_FILTER,
    API_META,
    API_SEARCH,
    API_WS,
    API_YEARS,
)

_LOG = logging.getLogger(__name__)


class EzbeqClient:
    """Talks to an ezBEQ server (no auth, plain HTTP on the LAN)."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = int(port)
        self._base = f"http://{host}:{self._port}"
        self._session: aiohttp.ClientSession | None = None

    @property
    def ws_url(self) -> str:
        return f"ws://{self._host}:{self._port}{API_WS}"

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    # -- low level -----------------------------------------------------
    async def _get(self, path: str, params: Any = None) -> Any:
        session = await self.session()
        async with session.get(f"{self._base}{path}", params=params) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _patch(self, path: str, payload: dict) -> Any:
        session = await self.session()
        async with session.patch(f"{self._base}{path}", json=payload) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _put(self, path: str, payload: dict) -> Any:
        session = await self.session()
        async with session.put(f"{self._base}{path}", json=payload) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _delete(self, path: str) -> Any:
        session = await self.session()
        async with session.delete(f"{self._base}{path}") as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    # -- devices / status ----------------------------------------------
    async def get_devices(self) -> dict[str, dict]:
        """Return {device_name: device_state} for all configured DSP devices."""
        data = await self._get(API_DEVICES)
        return data if isinstance(data, dict) else {}

    async def test_connection(self) -> bool:
        try:
            await self._get(API_META)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.debug("ezBEQ connection test failed: %s", err)
            return False

    # -- catalogue -----------------------------------------------------
    async def get_meta(self) -> dict:
        data = await self._get(API_META)
        return data if isinstance(data, dict) else {}

    async def get_authors(self) -> list[str]:
        return await self._get(API_AUTHORS) or []

    async def get_years(self) -> list:
        return await self._get(API_YEARS) or []

    async def get_audiotypes(self) -> list[str]:
        return await self._get(API_AUDIOTYPES) or []

    async def get_contenttypes(self) -> list[str]:
        return await self._get(API_CONTENTTYPES) or []

    async def search(
        self,
        text: str | None = None,
        authors: list[str] | None = None,
        years: list | None = None,
        audiotypes: list[str] | None = None,
        contenttypes: list[str] | None = None,
        limit: int | str | None = None,
    ) -> list[dict]:
        """Server-side catalogue search. Repeatable facets are AND across
        facets, OR within a facet."""
        params: list[tuple[str, str]] = []
        if text:
            params.append(("text", text))
        for author in authors or []:
            params.append(("authors", str(author)))
        for year in years or []:
            params.append(("years", str(year)))
        for atype in audiotypes or []:
            params.append(("audiotypes", str(atype)))
        for ctype in contenttypes or []:
            params.append(("contenttypes", str(ctype)))
        if limit is not None:
            params.append(("limit", str(limit)))
        data = await self._get(API_SEARCH, params=params or None)
        return data if isinstance(data, list) else []

    # -- load / clear / gain / mute ------------------------------------
    async def load(self, device_name: str, slot: str, entry: str) -> dict:
        """Load a catalogue entry (id or digest) into device+slot and activate it."""
        payload = {"slots": [{"id": str(slot), "active": True, "entry": entry}]}
        return await self._patch(API_DEVICE_PATCH.format(name=device_name), payload)

    async def clear(self, device_name: str, slot: str) -> dict:
        return await self._delete(
            API_FILTER.format(name=device_name, slot=str(slot))
        )

    async def set_master_volume(self, device_name: str, gain: float) -> dict:
        return await self._put(
            f"/api/1/devices/{device_name}/gain", {"gain": float(gain)}
        )

    async def set_mute(self, device_name: str, mute: bool) -> dict:
        payload = {"slots": [], "mute": bool(mute)}
        return await self._patch(API_DEVICE_PATCH.format(name=device_name), payload)
