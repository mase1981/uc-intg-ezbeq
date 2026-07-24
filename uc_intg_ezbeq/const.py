"""Constants for the ezBEQ integration."""

DEFAULT_EZBEQ_PORT = 8080

STATE_ON = "ON"
STATE_UNAVAILABLE = "UNAVAILABLE"

# ezBEQ REST API paths
API_DEVICES = "/api/2/devices"
API_DEVICE_PATCH = "/api/3/devices/{name}"
API_FILTER = "/api/1/devices/{name}/filter/{slot}"
API_SEARCH = "/api/1/search"
API_META = "/api/1/meta"
API_AUTHORS = "/api/1/authors"
API_YEARS = "/api/1/years"
API_AUDIOTYPES = "/api/1/audiotypes"
API_CONTENTTYPES = "/api/1/contenttypes"
API_WS = "/ws"

SLOT_EMPTY = "Empty"
