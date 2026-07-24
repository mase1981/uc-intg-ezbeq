"""Configuration dataclass and manager for the ezBEQ integration."""

from dataclasses import dataclass, field
from typing import Any

from ucapi_framework import BaseConfigManager

from uc_intg_ezbeq.const import DEFAULT_EZBEQ_PORT


@dataclass
class EzbeqConfig:
    """Configuration for a single ezBEQ server.

    ``devices`` is the list of DSP devices discovered from the ezBEQ server
    during setup, each ``{"name": str, "slots": int}``. Entities are built from
    this list; the runtime device keeps their live state via ws + polling.
    """

    identifier: str = ""
    name: str = ""
    host: str = ""
    port: int = DEFAULT_EZBEQ_PORT
    devices: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # UC setup returns all values as strings; keep port numeric.
        try:
            self.port = int(self.port)
        except (TypeError, ValueError):
            self.port = DEFAULT_EZBEQ_PORT


class EzbeqConfigManager(BaseConfigManager[EzbeqConfig]):
    """Config manager bound to :class:`EzbeqConfig`."""
