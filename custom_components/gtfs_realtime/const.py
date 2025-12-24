"""Constants for the GTFS Realtime integration."""

DOMAIN = "gtfs_realtime"

CONF_GTFS_PROVIDER = "gtfs_provider"
CONF_GTFS_PROVIDER_ID = "gtfs_provider_id"
CONF_USE_LOCAL_FEEDS = "use_local_feeds"
CONF_AUTH_HEADER = "auth_header"
CONF_GTFS_STATIC_DATA = "gtfs_static_data"
CONF_STATIC_SOURCES_UPDATE_FREQUENCY = "static_sources_update_frequency"
CONF_STATIC_SOURCES_UPDATE_FREQUENCY_DEFAULT = 2  # hours
CONF_URL_ENDPOINTS = "url_endpoints"
CONF_ROUTE_ICONS = "route_icons"
CONF_ROUTE_IDS = "route_ids"
CONF_STOP_IDS = "stop_ids"
CONF_ARRIVAL_LIMIT = "arrival_limit"
CONF_VERSION = 2
CONF_MINOR_VERSION = 0

# Vehicle tracking configuration
CONF_VEHICLE_POSITION_URL = "vehicle_position_url"
CONF_VEHICLE_POSITION_HISTORY_MINUTES = "vehicle_position_history_minutes"
CONF_VEHICLE_POSITION_HISTORY_MINUTES_DEFAULT = 10
CONF_TRACKED_ROUTES = "tracked_routes"

# ERRORS
CONF_SELECT_AT_LEAST_ONE_STOP_OR_ROUTE = "select_at_least_one_stop_or_route"

FEEDS_URL = "https://raw.githubusercontent.com/bcpearce/homeassistant-gtfs-realtime/refs/heads/main/custom_components/gtfs_realtime/feeds.json"

STOP_ID = "stop_id"
ROUTE_ID = "route_id"
TRIP_ID = "trip_id"
ROUTE_COLOR = "route_color"
ROUTE_TEXT_COLOR = "route_text_color"
HEADSIGN = "headsign"
ROUTE_TYPE = "route_type"

# Geographic and arrival attributes
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"
ATTR_STOP_NAME = "stop_name"
ATTR_NEXT_ARRIVALS = "next_arrivals"
ATTR_ETA_SECONDS = "eta_seconds"
ATTR_VEHICLE_ID = "vehicle_id"

SSI_DB = "station_stop_info_db"
TI_DB = "trip_info_db"
CAL_DB = "calendar_db"
RTI_DB = "route_info_db"

COORDINATOR_REALTIME = "coordinator_realtime"

PLATFORM = "platform"
