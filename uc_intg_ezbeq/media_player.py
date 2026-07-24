"""ezBEQ media_player entity: browse/search the BEQ catalogue and load filters."""

import logging
from typing import Any

from ucapi import StatusCodes, media_player
from ucapi.media_player import BrowseOptions, BrowseResults, SearchOptions, SearchResults
from ucapi_framework import MediaPlayerEntity

from uc_intg_ezbeq import browser
from uc_intg_ezbeq.config import EzbeqConfig
from uc_intg_ezbeq.device import EzbeqDevice

_LOG = logging.getLogger(__name__)

FEATURES = [
    media_player.Features.MEDIA_TITLE,
    media_player.Features.MEDIA_ARTIST,
    media_player.Features.PLAY_MEDIA,
    media_player.Features.BROWSE_MEDIA,
    media_player.Features.SEARCH_MEDIA,
    media_player.Features.MUTE_TOGGLE,
]


class EzbeqMediaPlayer(MediaPlayerEntity):
    """Represents one DSP device managed by the ezBEQ server."""

    def __init__(self, device_config: EzbeqConfig, device: EzbeqDevice, dsp: dict, index: int) -> None:
        self._device = device
        self._index = index
        self._dsp_name = dsp["name"]
        entity_id = f"media_player.{device_config.identifier}.{index}"
        super().__init__(
            entity_id,
            f"{self._dsp_name} BEQ",
            FEATURES,
            {
                media_player.Attributes.STATE: media_player.States.UNKNOWN,
                media_player.Attributes.MEDIA_TITLE: "",
                media_player.Attributes.MEDIA_ARTIST: "",
                media_player.Attributes.MUTED: False,
            },
            device_class=media_player.DeviceClasses.RECEIVER,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({media_player.Attributes.STATE: media_player.States.UNAVAILABLE})
            return
        slot_id = self._device.selected_slot(self._dsp_name)
        slot = self._device.slot(self._dsp_name, slot_id)
        title = "No BEQ loaded"
        artist = ""
        if slot and slot.get("last") and slot.get("last") != "Empty":
            title = slot["last"]
            artist = slot.get("author", "")
        self.update({
            media_player.Attributes.STATE: media_player.States.PLAYING
            if artist or title != "No BEQ loaded"
            else media_player.States.ON,
            media_player.Attributes.MEDIA_TITLE: f"Slot {slot_id}: {title}",
            media_player.Attributes.MEDIA_ARTIST: artist,
            media_player.Attributes.MUTED: self._device.is_muted(self._dsp_name),
        })

    async def browse(self, options: BrowseOptions) -> BrowseResults | StatusCodes:
        return await browser.browse(self._device, self._dsp_name, options)

    async def search(self, options: SearchOptions) -> SearchResults | StatusCodes:
        return await browser.search(self._device, options)

    async def _handle_command(self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any) -> StatusCodes:
        try:
            if cmd_id == media_player.Commands.PLAY_MEDIA:
                return await self._play_media(params or {})
            if cmd_id == media_player.Commands.MUTE_TOGGLE:
                ok = await self._device.set_mute(self._dsp_name, not self._device.is_muted(self._dsp_name))
                return StatusCodes.OK if ok else StatusCodes.SERVER_ERROR
            if cmd_id == media_player.Commands.MUTE:
                return StatusCodes.OK if await self._device.set_mute(self._dsp_name, True) else StatusCodes.SERVER_ERROR
            if cmd_id == media_player.Commands.UNMUTE:
                return StatusCodes.OK if await self._device.set_mute(self._dsp_name, False) else StatusCodes.SERVER_ERROR
            return StatusCodes.NOT_IMPLEMENTED
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Command error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR

    async def _play_media(self, params: dict) -> StatusCodes:
        media_id = params.get("media_id", "")
        if media_id == "beq:clear":
            ok = await self._device.clear_slot(self._dsp_name)
            return StatusCodes.OK if ok else StatusCodes.SERVER_ERROR
        if media_id.startswith("beq:load:"):
            digest = media_id.split(":", 2)[2]
            if not digest:
                return StatusCodes.BAD_REQUEST
            ok = await self._device.load_entry(self._dsp_name, digest)
            return StatusCodes.OK if ok else StatusCodes.SERVER_ERROR
        return StatusCodes.NOT_IMPLEMENTED


def create_media_players(device_config: EzbeqConfig, device: EzbeqDevice) -> list[EzbeqMediaPlayer]:
    return [
        EzbeqMediaPlayer(device_config, device, dsp, index)
        for index, dsp in enumerate(device_config.devices)
    ]
