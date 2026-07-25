"""BEQ catalogue media browser.

The full catalogue is fetched once from the ezBEQ server (``/api/1/search`` with
``limit=all``) and cached, so we can browse By Title (A-Z), By Author, By Year and
By Audio Type, do title search, and surface each entry's poster (thumbnail) and
frequency-response graph (used as the media_player's now-playing image).
"""

from __future__ import annotations

import asyncio
import logging
import time
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
CACHE_TTL = 86400  # 24h

_entries: list[dict] | None = None
_by_title: dict[str, dict] = {}
_ts = 0
_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Catalogue cache
# ---------------------------------------------------------------------------
async def prefetch(device: "EzbeqDevice") -> None:
    try:
        await _fetch(device)
    except Exception as err:  # pylint: disable=broad-exception-caught
        _LOG.debug("Catalogue prefetch failed: %s", err)


async def _fetch(device: "EzbeqDevice") -> list[dict]:
    global _entries, _ts, _by_title
    if _entries is not None and time.time() - _ts < CACHE_TTL:
        return _entries
    if _lock.locked():
        async with _lock:
            return _entries or []
    async with _lock:
        if _entries is not None and time.time() - _ts < CACHE_TTL:
            return _entries
        _LOG.info("Fetching BEQ catalogue from ezBEQ server")
        entries = await device.client.search(limit="all")
        entries.sort(key=lambda e: (e.get("sortTitle") or e.get("title", "")).lower())
        _entries = entries
        _ts = int(time.time())
        _by_title = {(e.get("title", "") or "").lower(): e for e in entries}
        _LOG.info("BEQ catalogue loaded: %d entries", len(entries))
        return entries


def images_for_entry(entry: dict) -> tuple[str | None, str | None]:
    """Return (poster_jpg, graph_png) from an entry's images list."""
    imgs = entry.get("images") or []
    poster = next((u for u in imgs if str(u).lower().endswith((".jpg", ".jpeg"))),
                  imgs[0] if imgs else None)
    graph = next((u for u in imgs if str(u).lower().endswith(".png")),
                 imgs[-1] if len(imgs) > 1 else None)
    return poster, graph


def graph_for_title(title: str) -> str | None:
    entry = _by_title.get((title or "").lower())
    return images_for_entry(entry)[1] if entry else None


# ---------------------------------------------------------------------------
# Item builders
# ---------------------------------------------------------------------------
def _entry_fields(entry: dict) -> dict:
    title = entry.get("formattedTitle") or entry.get("title", "Unknown")
    author = entry.get("author", "")
    year = entry.get("year", "")
    audio = ", ".join(entry.get("audioTypes", []) or [])
    digest = entry.get("digest") or entry.get("id") or ""
    poster, _graph = images_for_entry(entry)
    subtitle = " | ".join(str(p) for p in (year, audio, author) if p)
    return dict(
        title=str(title)[:255],
        media_class=MediaClass.TRACK,
        media_type="beq_entry",
        media_id=f"beq:load:{digest}",
        can_play=True,
        can_browse=False,
        subtitle=subtitle[:255] or None,
        thumbnail=poster,
    )


def _entry_item(entry: dict) -> BrowseMediaItem:
    return BrowseMediaItem(**_entry_fields(entry))


def _dir(title: str, media_type: str, media_id: str, subtitle: str | None = None) -> BrowseMediaItem:
    return BrowseMediaItem(
        title=title, media_class=MediaClass.DIRECTORY, media_type=media_type,
        media_id=media_id, can_browse=True, can_play=False, subtitle=subtitle,
    )


def _page(container_title: str, media_type: str, media_id: str, items: list, page: int, total: int) -> BrowseResults:
    return BrowseResults(
        media=BrowseMediaItem(
            title=container_title, media_class=MediaClass.DIRECTORY,
            media_type=media_type, media_id=media_id,
            can_browse=True, can_search=True, items=items,
        ),
        pagination=Pagination(page=page, limit=ITEMS_PER_PAGE, count=total),
    )


def _loading(container_title: str = "BEQ Catalogue") -> BrowseResults:
    return _page(container_title, "beq_menu", "beq_menu", [
        _dir("Loading catalogue...", "beq_menu", "beq_menu", "Please wait a moment and browse again."),
    ], 1, 1)


# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------
async def browse(device: "EzbeqDevice", dsp_name: str, options: BrowseOptions) -> BrowseResults | StatusCodes:
    media_type = options.media_type or "root"
    media_id = options.media_id or ""
    paging = options.paging
    page = int((paging.page if paging and paging.page else None) or 1)

    if media_type == "root" or (options.media_id is None and options.media_type is None):
        return _root(device, dsp_name)
    if media_type == "beq_menu":
        return _menu()

    cat = await _ensure_cache(device)
    if cat is None:
        return _loading()

    if media_type == "beq_titles":
        return _letters(cat)
    if media_type == "beq_letter":
        return _by_letter(cat, media_id, page)
    if media_type == "beq_authors":
        return _facet_list(cat, "author", "beq_author", "Authors")
    if media_type == "beq_years":
        return _facet_list(cat, "year", "beq_year", "Years")
    if media_type == "beq_audiotypes":
        return _facet_list(cat, "audioTypes", "beq_audiotype", "Audio Types", is_list=True)
    if media_type == "beq_author":
        return _facet_results(cat, lambda e: e.get("author") == media_id, media_id, "beq_author", media_id, page)
    if media_type == "beq_year":
        return _facet_results(cat, lambda e: str(e.get("year")) == media_id, media_id, "beq_year", media_id, page)
    if media_type == "beq_audiotype":
        return _facet_results(cat, lambda e: media_id in (e.get("audioTypes") or []), media_id, "beq_audiotype", media_id, page)
    return StatusCodes.NOT_FOUND


async def search(device: "EzbeqDevice", options: SearchOptions) -> SearchResults | StatusCodes:
    query = (options.query or "").strip().lower()
    if not query:
        return SearchResults(media=[], pagination=Pagination(page=1, limit=0, count=0))
    cat = await _ensure_cache(device)
    if cat is None:
        return SearchResults(media=[], pagination=Pagination(page=1, limit=0, count=0))
    paging = options.paging
    page = int((paging.page if paging and paging.page else None) or 1)
    matches = [e for e in cat if query in (e.get("title", "") or "").lower()
               or query in (e.get("altTitle", "") or "").lower()]
    start = (page - 1) * ITEMS_PER_PAGE
    items = [SearchMediaItem(**_entry_fields(e)) for e in matches[start:start + ITEMS_PER_PAGE]]
    return SearchResults(media=items, pagination=Pagination(page=page, limit=ITEMS_PER_PAGE, count=len(matches)))


async def _ensure_cache(device: "EzbeqDevice") -> list[dict] | None:
    if _entries is not None:
        return _entries
    if not _lock.locked():
        asyncio.create_task(prefetch(device))
    return None


def _root(device: "EzbeqDevice", dsp_name: str) -> BrowseResults:
    items = [_dir("BEQ Catalogue", "beq_menu", "beq_menu", "Browse or search Bass EQ filters")]
    slot_id = device.selected_slot(dsp_name)
    slot = device.slot(dsp_name, slot_id)
    if slot and slot.get("last") and slot.get("last") != "Empty":
        items.append(BrowseMediaItem(
            title=f"Clear slot {slot_id}: {device.slot_loaded_text(slot)}",
            media_class=MediaClass.TRACK, media_type="beq_clear", media_id="beq:clear",
            can_play=True, can_browse=False, subtitle="Remove the loaded BEQ from the selected slot",
        ))
    return BrowseResults(
        media=BrowseMediaItem(title=dsp_name, media_class=MediaClass.DIRECTORY, media_type="root",
                              media_id="root", can_browse=True, can_search=True, items=items),
        pagination=Pagination(page=1, limit=len(items), count=len(items)),
    )


def _menu() -> BrowseResults:
    items = [
        _dir("By Title", "beq_titles", "titles"),
        _dir("By Audio Type", "beq_audiotypes", "audiotypes"),
        _dir("By Author", "beq_authors", "authors"),
        _dir("By Year", "beq_years", "years"),
    ]
    return _page("BEQ Catalogue", "beq_menu", "beq_menu", items, 1, len(items))


def _letter_of(entry: dict) -> str:
    t = (entry.get("sortTitle") or entry.get("title", "") or "").strip().upper()
    if not t:
        return "#"
    c = t[0]
    return c if c.isalpha() else "0-9"


def _letters(cat: list[dict]) -> BrowseResults:
    counts: dict[str, int] = {}
    for e in cat:
        counts[_letter_of(e)] = counts.get(_letter_of(e), 0) + 1
    order = (["0-9"] if "0-9" in counts else []) + [c for c in map(chr, range(65, 91)) if c in counts]
    items = [_dir(letter, "beq_letter", letter, f"{counts[letter]} titles") for letter in order]
    return _page("By Title", "beq_titles", "titles", items, 1, len(items))


def _by_letter(cat: list[dict], letter: str, page: int) -> BrowseResults:
    matches = [e for e in cat if _letter_of(e) == letter]
    start = (page - 1) * ITEMS_PER_PAGE
    items = [_entry_item(e) for e in matches[start:start + ITEMS_PER_PAGE]]
    return _page(letter, "beq_letter", letter, items, page, len(matches))


def _facet_list(cat: list[dict], key: str, child_type: str, title: str, is_list: bool = False) -> BrowseResults:
    values: dict[str, int] = {}
    for e in cat:
        vals = (e.get(key) or []) if is_list else [e.get(key)]
        for v in vals:
            if v not in (None, ""):
                values[str(v)] = values.get(str(v), 0) + 1
    order = sorted(values.keys(), key=lambda x: (x.isdigit() and f"{int(x):09d}") or x.lower())
    items = [_dir(v, child_type, v, f"{values[v]} titles") for v in order]
    return _page(title, f"beq_{key}s", key, items, 1, len(items))


def _facet_results(cat, predicate, value, media_type, media_id, page) -> BrowseResults:
    matches = [e for e in cat if predicate(e)]
    start = (page - 1) * ITEMS_PER_PAGE
    items = [_entry_item(e) for e in matches[start:start + ITEMS_PER_PAGE]]
    return _page(str(value), media_type, media_id, items, page, len(matches))
