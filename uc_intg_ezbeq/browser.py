"""BEQ catalogue media browser, backed by the ezBEQ server's search API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ucapi import StatusCodes
from ucapi.api_definitions import Pagination
from ucapi.media_player import (
    BrowseMediaItem,
    BrowseOptions,
    BrowseResults,
    MediaClass,
    SearchMediaItem,
    SearchOptions,
    SearchResults,
)

if TYPE_CHECKING:
    from uc_intg_ezbeq.device import EzbeqDevice

_LOG = logging.getLogger(__name__)

ITEMS_PER_PAGE = 50


def _entry_fields(entry: dict) -> dict:
    title = entry.get("formattedTitle") or entry.get("title", "Unknown")
    author = entry.get("author", "")
    year = entry.get("year", "")
    audio = ", ".join(entry.get("audioTypes", []) or [])
    digest = entry.get("digest") or entry.get("id") or ""
    subtitle = " | ".join(str(p) for p in (year, audio, author) if p)
    return dict(
        title=str(title)[:255],
        media_class=MediaClass.TRACK,
        media_type="beq_entry",
        media_id=f"beq:load:{digest}",
        can_play=True,
        can_browse=False,
        subtitle=subtitle[:255] or None,
    )


def _entry_item(entry: dict) -> BrowseMediaItem:
    return BrowseMediaItem(**_entry_fields(entry))


def _dir(title: str, media_type: str, media_id: str, subtitle: str | None = None) -> BrowseMediaItem:
    return BrowseMediaItem(
        title=title,
        media_class=MediaClass.DIRECTORY,
        media_type=media_type,
        media_id=media_id,
        can_browse=True,
        can_play=False,
        subtitle=subtitle,
    )


async def browse(device: "EzbeqDevice", dsp_name: str, options: BrowseOptions) -> BrowseResults | StatusCodes:
    media_type = options.media_type or "root"
    media_id = options.media_id or ""
    paging = options.paging
    page = int((paging.page if paging and paging.page else None) or 1)

    if media_type == "root" or (options.media_id is None and options.media_type is None):
        return _root(device, dsp_name)
    if media_type == "beq_menu":
        return _menu()
    if media_type.startswith("beq_facet:"):
        return await _facet_values(device, media_type.split(":", 1)[1])
    if media_type == "beq_search":
        return await _facet_results(device, media_id, page)
    return StatusCodes.NOT_FOUND


async def search(device: "EzbeqDevice", options: SearchOptions) -> SearchResults | StatusCodes:
    query = (options.query or "").strip()
    if not query:
        return SearchResults(media=[], pagination=Pagination(page=1, limit=0, count=0))
    paging = options.paging
    page = int((paging.page if paging and paging.page else None) or 1)
    try:
        entries = await device.client.search(text=query, limit=500)
    except Exception as err:  # pylint: disable=broad-exception-caught
        _LOG.error("BEQ search failed: %s", err)
        return StatusCodes.SERVER_ERROR
    start = (page - 1) * ITEMS_PER_PAGE
    items = [SearchMediaItem(**_entry_fields(e)) for e in entries[start:start + ITEMS_PER_PAGE]]
    return SearchResults(
        media=items,
        pagination=Pagination(page=page, limit=ITEMS_PER_PAGE, count=len(entries)),
    )


def _root(device: "EzbeqDevice", dsp_name: str) -> BrowseResults:
    items = [_dir("BEQ Catalogue", "beq_menu", "beq_menu", "Browse or search Bass EQ filters")]
    slot_id = device.selected_slot(dsp_name)
    slot = device.slot(dsp_name, slot_id)
    loaded = device.slot_loaded_text(slot)
    if slot and slot.get("last") and slot.get("last") != "Empty":
        items.append(
            BrowseMediaItem(
                title=f"Clear slot {slot_id}: {loaded}",
                media_class=MediaClass.TRACK,
                media_type="beq_clear",
                media_id="beq:clear",
                can_play=True,
                can_browse=False,
                subtitle="Remove the loaded BEQ from the selected slot",
            )
        )
    return BrowseResults(
        media=BrowseMediaItem(
            title=dsp_name, media_class=MediaClass.DIRECTORY, media_type="root",
            media_id="root", can_browse=True, can_search=True, items=items,
        ),
        pagination=Pagination(page=1, limit=len(items), count=len(items)),
    )


def _menu() -> BrowseResults:
    items = [
        _dir("By Audio Type", "beq_facet:audiotypes", "audiotypes"),
        _dir("By Author", "beq_facet:authors", "authors"),
        _dir("By Year", "beq_facet:years", "years"),
    ]
    return BrowseResults(
        media=BrowseMediaItem(
            title="BEQ Catalogue", media_class=MediaClass.DIRECTORY,
            media_type="beq_menu", media_id="beq_menu",
            can_browse=True, can_search=True, items=items,
        ),
        pagination=Pagination(page=1, limit=len(items), count=len(items)),
    )


async def _facet_values(device: "EzbeqDevice", facet: str) -> BrowseResults:
    try:
        if facet == "authors":
            values = await device.client.get_authors()
        elif facet == "years":
            values = await device.client.get_years()
        elif facet == "audiotypes":
            values = await device.client.get_audiotypes()
        else:
            return BrowseResults(media=BrowseMediaItem(title="", media_class=MediaClass.DIRECTORY, media_type="beq_menu", media_id="beq_menu", items=[]), pagination=Pagination(page=1, limit=0, count=0))
    except Exception as err:  # pylint: disable=broad-exception-caught
        _LOG.error("Facet %s failed: %s", facet, err)
        values = []
    items = [_dir(str(v), "beq_search", f"{facet}={v}") for v in values]
    return BrowseResults(
        media=BrowseMediaItem(
            title=facet.title(), media_class=MediaClass.DIRECTORY,
            media_type=f"beq_facet:{facet}", media_id=facet,
            can_browse=True, items=items,
        ),
        pagination=Pagination(page=1, limit=len(items), count=len(items)),
    )


async def _facet_results(device: "EzbeqDevice", media_id: str, page: int) -> BrowseResults:
    facet, _, value = media_id.partition("=")
    kwargs = {}
    if facet == "authors":
        kwargs["authors"] = [value]
    elif facet == "years":
        kwargs["years"] = [value]
    elif facet == "audiotypes":
        kwargs["audiotypes"] = [value]
    try:
        entries = await device.client.search(limit=1000, **kwargs)
    except Exception as err:  # pylint: disable=broad-exception-caught
        _LOG.error("BEQ facet search failed: %s", err)
        entries = []
    entries.sort(key=lambda e: e.get("sortTitle") or e.get("title", ""))
    start = (page - 1) * ITEMS_PER_PAGE
    items = [_entry_item(e) for e in entries[start:start + ITEMS_PER_PAGE]]
    return BrowseResults(
        media=BrowseMediaItem(
            title=value, media_class=MediaClass.DIRECTORY,
            media_type="beq_search", media_id=media_id,
            can_browse=True, can_search=True, items=items,
        ),
        pagination=Pagination(page=page, limit=ITEMS_PER_PAGE, count=len(entries)),
    )
