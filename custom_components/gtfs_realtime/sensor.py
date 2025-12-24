"""Platform for sensor integration."""

from __future__ import annotations
import logging

from gtfs_station_stop.arrival import Arrival
from gtfs_station_stop.route_info import RouteType
from gtfs_station_stop.station_stop import StationStop
from gtfs_station_stop.station_stop_info import StationStopInfo
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import voluptuous as vol

from custom_components.gtfs_realtime import GtfsRealtimeConfigEntry

from .const import (
    ATTR_ETA_SECONDS,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NEXT_ARRIVALS,
    ATTR_STOP_NAME,
    ATTR_VEHICLE_ID,
    CONF_ARRIVAL_LIMIT,
    CONF_STOP_IDS,
    DOMAIN,
    HEADSIGN,
    ROUTE_COLOR,
    ROUTE_ID,
    ROUTE_TEXT_COLOR,
    ROUTE_TYPE,
    STOP_ID,
    TRIP_ID,
)
from .coordinator import GtfsRealtimeCoordinator

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(STOP_ID): cv.string, vol.Optional(CONF_ARRIVAL_LIMIT, default=4): int}
)

_LOGGER = logging.getLogger(__name__)

MIN_NEGATIVE_ARRIVAL_TIME_SECONDS = -120  # 2 minutes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GtfsRealtimeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: GtfsRealtimeCoordinator = entry.runtime_data
    if CONF_STOP_IDS in entry.data:
        arrival_limit: int = int(round(entry.data[CONF_ARRIVAL_LIMIT]))
        stop_sensors = []
        for stop_id in entry.data[CONF_STOP_IDS]:
            stop_sensors.append(
                StopSensor(
                    coordinator=coordinator,
                    stop_id=stop_id,
                    arrival_limit=arrival_limit,
                )
            )
        async_add_entities(stop_sensors, update_before_add=True)


class StopSensor(SensorEntity, CoordinatorEntity):
    """Representation of a Station GTFS Realtime Stop Sensor with geographic coordinates."""

    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_picture: str | None = None

    ICON_DICT = {
        RouteType.TRAM: "mdi:tram",
        RouteType.SUBWAY: "mdi:subway-variant",
        RouteType.RAIL: "mdi:train",
        RouteType.FERRY: "mdi:ferry",
    }

    def __init__(
        self, coordinator: GtfsRealtimeCoordinator, stop_id: str, arrival_limit: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self.station_stop = coordinator.gtfs_update_data.station_stops.setdefault(
            stop_id, StationStop(stop_id, coordinator.hub)
        )
        self._arrival_limit = arrival_limit
        self.coordinator = coordinator
        self.route_type = RouteType.UNKNOWN

        self._name = self._get_stop_ref()
        self._attr_unique_id = f"stop_{self.station_stop.id}"
        self._attr_suggested_display_precision = 0
        self._attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
        self._next_arrivals: list[dict[str, any]] = []

    def _get_stop_info(self) -> StationStopInfo | None:
        """Get stop information from GTFS static data."""
        return self.coordinator.gtfs_update_data.schedule.get_stop_info(
            self.station_stop.id
        )

    def _get_stop_ref(self) -> str:
        """Get stop name from static data or fall back to stop ID."""
        station_stop_info = self._get_stop_info()
        if station_stop_info is not None:
            return station_stop_info.name
        return self.station_stop.id

    @property
    def name(self) -> str:
        """Name of the station from static data or else the Stop ID."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return stop coordinates and nested arrival information."""
        stop_info = self._get_stop_info()
        
        attributes = {
            ATTR_STOP_NAME: stop_info.name if stop_info else self.station_stop.id,
            ATTR_NEXT_ARRIVALS: self._next_arrivals,
        }
        
        # Add coordinates if available from GTFS static data
        if stop_info:
            if hasattr(stop_info, 'lat') and stop_info.lat is not None:
                attributes[ATTR_LATITUDE] = float(stop_info.lat)
            if hasattr(stop_info, 'lon') and stop_info.lon is not None:
                attributes[ATTR_LONGITUDE] = float(stop_info.lon)
        
        # Log warning if coordinates are missing
        if ATTR_LATITUDE not in attributes or ATTR_LONGITUDE not in attributes:
            _LOGGER.debug(
                "Stop %s (%s) is missing geographic coordinates in GTFS static data",
                self.station_stop.id,
                self._name
            )
        
        return attributes

    @property
    def entity_picture(self) -> str | None:
        """Provide the entity picture from a URL for the next arrival."""
        if (
            self.coordinator.route_icons
            and self._next_arrivals
            and self._next_arrivals[0].get(ROUTE_ID) is not None
        ):
            first_arrival = self._next_arrivals[0]
            return str(self.coordinator.route_icons).format(
                first_arrival[ROUTE_ID],
                first_arrival.get(ROUTE_COLOR, "%230039A6"),
                first_arrival.get(ROUTE_TEXT_COLOR, "%23FFFFFF"),
            )
        return None

    @property
    def icon(self) -> str:
        """Provide the icon based on route type of next arrival."""
        return self.__class__.ICON_DICT.get(self.route_type, "mdi:bus-clock")

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.station_stop.id)},
            name=f"{self._get_stop_ref()} ({self.station_stop.id})",
            manufacturer=self.coordinator.gtfs_provider,
            model=self.station_stop.id,
        )

    def update(self) -> None:
        """Update state from coordinator data."""
        stop_times_ds = self.coordinator.gtfs_update_data.schedule.stop_times_ds
        time_to_arrivals = list(
            filter(
                lambda tta: tta.time is None
                or tta.time > MIN_NEGATIVE_ARRIVAL_TIME_SECONDS,
                sorted(
                    self.station_stop.get_time_to_arrivals(
                        stop_times_dataset=stop_times_ds
                    )
                ),
            )
        )
        
        # Clear previous arrivals
        self._next_arrivals = []
        
        # Get schedule reference
        schedule = self.coordinator.data.schedule
        
        # Build list of next arrivals up to the limit
        for idx in range(min(self._arrival_limit, len(time_to_arrivals))):
            time_to_arrival: Arrival = time_to_arrivals[idx]
            
            # Get route ID from trip if not present
            route_id = time_to_arrival.route
            if not route_id:
                trip_info = schedule.trip_info_ds.get_close_match(time_to_arrival.trip)
                if trip_info is not None:
                    route_id = trip_info.route_id
            
            # Build arrival dictionary
            arrival_dict = {
                ROUTE_ID: route_id,
                HEADSIGN: schedule.get_trip_headsign(time_to_arrival.trip),
                TRIP_ID: time_to_arrival.trip,
                ATTR_ETA_SECONDS: max(time_to_arrival.time, 0) if time_to_arrival.time else None,
                ROUTE_COLOR: schedule.get_route_color(route_id),
                ROUTE_TEXT_COLOR: schedule.get_route_text_color(route_id),
                ROUTE_TYPE: schedule.get_route_type(route_id),
            }
            
            # Add vehicle ID if available
            if hasattr(time_to_arrival, 'vehicle_id'):
                arrival_dict[ATTR_VEHICLE_ID] = time_to_arrival.vehicle_id
            
            self._next_arrivals.append(arrival_dict)
        
        # Set sensor state to the ETA of the next arrival (first in list)
        if self._next_arrivals:
            self._attr_native_value = self._next_arrivals[0].get(ATTR_ETA_SECONDS)
            # Update route type for icon display
            route_type_str = self._next_arrivals[0].get(ROUTE_TYPE)
            if route_type_str:
                try:
                    self.route_type = RouteType[route_type_str.upper()]
                except (KeyError, AttributeError):
                    self.route_type = RouteType.UNKNOWN
        else:
            self._attr_native_value = None
            self.route_type = RouteType.UNKNOWN

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self.update()
            super()._handle_coordinator_update()
        except Exception as err:
            _LOGGER.error(
                "Exception occurred updating %s provided by %s: %s",
                self.name,
                self.coordinator.gtfs_provider,
                err,
                exc_info=True,
            )
            raise
