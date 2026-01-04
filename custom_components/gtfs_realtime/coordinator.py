"""GTFS Realtime Coordinator."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import os
from typing import Any

from google.transit import gtfs_realtime_pb2
from gtfs_station_stop.feed_subject import FeedSubject
from gtfs_station_stop.route_status import RouteStatus
from gtfs_station_stop.schedule import GtfsSchedule
from gtfs_station_stop.schedule import async_build_schedule  # noqa: F401
from gtfs_station_stop.station_stop import StationStop
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_STATIC_SOURCES_UPDATE_FREQUENCY_DEFAULT,
    CONF_VEHICLE_POSITION_HISTORY_MINUTES_DEFAULT,
    DOMAIN,
)

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


@dataclass
class GtfsUpdateData:
    """Collection of GTFS Data For Sensors to Lookup."""

    station_stops: dict[str, StationStop] = field(
        default_factory=lambda: defaultdict(dict)
    )
    routes_statuses: dict[str, RouteStatus] = field(
        default_factory=lambda: defaultdict(dict)
    )
    schedule: GtfsSchedule = field(default_factory=GtfsSchedule)
    vehicle_positions: dict[str, Any] = field(default_factory=dict)
    tracked_routes: set[str] = field(default_factory=set)


class GtfsRealtimeCoordinator(DataUpdateCoordinator):
    """GTFS Realtime Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        feed_subject: FeedSubject,
        gtfs_static_zip: Iterable[os.PathLike] | os.PathLike = list[os.PathLike],
        *,
        gtfs_provider: str | None = None,
        static_timedelta: dict[os.PathLike, timedelta] | None = None,
        route_icons: str | None = None,
        vehicle_position_url: str | None = None,
        vehicle_position_history_minutes: int = CONF_VEHICLE_POSITION_HISTORY_MINUTES_DEFAULT,
        tracked_routes: set[str] | None = None,
        **kwargs,
    ) -> None:
        """Initialize the GTFS Update Coordinator to notify all entities upon poll."""
        if static_timedelta is None:
            static_timedelta = {}
        self.realtime_timedelta: timedelta = kwargs.get(
            "realtime_timedelta", timedelta(seconds=60)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self.realtime_timedelta,
        )
        self.static_timedelta = static_timedelta
        self.kwargs = kwargs
        self.gtfs_provider = gtfs_provider
        self.hub: FeedSubject = feed_subject
        self.hub.max_api_calls_per_second = 1  # rate limit
        self.gtfs_update_data = GtfsUpdateData()
        self.gtfs_static_zip: Iterable[os.PathLike] | os.PathLike = gtfs_static_zip
        self.route_icons = route_icons
        self.static_update_targets: set[os.PathLike] = set(gtfs_static_zip)
        self.last_static_update: dict[os.PathLike, datetime] = {}
        
        # Vehicle position configuration
        self.vehicle_position_url = vehicle_position_url
        self.vehicle_position_history_minutes = vehicle_position_history_minutes
        self.gtfs_update_data.tracked_routes = tracked_routes or set()
        
        _LOGGER.debug("Setup GTFS Realtime Update Coordinator")
        _LOGGER.debug("Realtime GTFS update interval %s", self.realtime_timedelta)
        if self.vehicle_position_url:
            _LOGGER.info(
                "Vehicle position tracking enabled with %d minute history",
                self.vehicle_position_history_minutes
            )
            if self.gtfs_update_data.tracked_routes:
                _LOGGER.info(
                    "Tracking vehicles for routes: %s",
                    ", ".join(self.gtfs_update_data.tracked_routes)
                )
        for uri, delta in self.static_timedelta.items():
            _LOGGER.info("Static GTFS update interval for %s is %s", uri, delta)

    async def _async_update_data(self) -> GtfsUpdateData:
        """Fetch data from API endpoint."""
        self.static_update_targets |= {
            uri
            for uri, last_update in self.last_static_update.items()
            if datetime.now() - last_update
            > self.static_timedelta.get(
                uri, timedelta(hours=CONF_STATIC_SOURCES_UPDATE_FREQUENCY_DEFAULT)
            )
        }
        await self.async_update_static_data()
        await self.hub.async_update(async_get_clientsession(self.hass))
        
        # Fetch vehicle positions if configured
        if self.vehicle_position_url:
            await self._async_update_vehicle_positions()
        
        return self.gtfs_update_data

    async def _async_update_vehicle_positions(self) -> None:
        """Fetch and parse vehicle position feed."""
        try:
            session = async_get_clientsession(self.hass)
            headers = self.kwargs.get('headers', {})
            
            async with session.get(
                self.vehicle_position_url,
                headers=headers,
                timeout=30
            ) as response:
                if response.status != 200:
                    _LOGGER.warning(
                        "Failed to fetch vehicle positions: HTTP %d",
                        response.status
                    )
                    return
                
                data = await response.read()
                feed = gtfs_realtime_pb2.FeedMessage()
                feed.ParseFromString(data)
                
                # Clear old positions
                self.gtfs_update_data.vehicle_positions.clear()
                
                # Parse vehicle positions
                for entity in feed.entity:
                    if entity.HasField('vehicle'):
                        vehicle = entity.vehicle
                        
                        # Use vehicle ID from entity or vehicle descriptor
                        vehicle_id = entity.id
                        if vehicle.HasField('vehicle') and vehicle.vehicle.id:
                            vehicle_id = vehicle.vehicle.id
                        
                        self.gtfs_update_data.vehicle_positions[vehicle_id] = vehicle
                
                _LOGGER.debug(
                    "Fetched %d vehicle positions",
                    len(self.gtfs_update_data.vehicle_positions)
                )
                
                # Check coverage for tracked routes
                if self.gtfs_update_data.tracked_routes:
                    self._log_route_coverage()
                
        except Exception as err:
            _LOGGER.warning(
                "Error fetching vehicle positions from %s: %s",
                self.vehicle_position_url,
                err,
                exc_info=True
            )
            # Don't clear positions on error - keep stale data until it times out

    def _log_route_coverage(self) -> None:
        """Log which tracked routes have vehicle position data."""
        routes_with_vehicles = set()
        
        for vehicle_pos in self.gtfs_update_data.vehicle_positions.values():
            try:
                if vehicle_pos.HasField('trip') and vehicle_pos.trip.route_id:
                    routes_with_vehicles.add(vehicle_pos.trip.route_id)
            except AttributeError:
                continue
        
        for route_id in self.gtfs_update_data.tracked_routes:
            if route_id not in routes_with_vehicles:
                _LOGGER.info(
                    "Route %s is tracked but has no vehicle position data. "
                    "This may be normal for routes that don't provide real-time "
                    "vehicle locations (e.g., SkyTrain, SeaBus).",
                    route_id
                )

    def get_vehicles_for_route(self, route_id: str) -> list[str]:
        """Get list of vehicle IDs currently serving a route."""
        vehicles = []
        for vehicle_id, position in self.gtfs_update_data.vehicle_positions.items():
            try:
                if position.HasField('trip') and position.trip.route_id == route_id:
                    vehicles.append(vehicle_id)
            except AttributeError:
                continue
        
        return vehicles

    async def async_update_static_data(self, clear_old_data=False):
        """Update or clear static feeds and merge with existing datasets."""
        # Check for clear old data to reset the datasets
        if clear_old_data:
            self.gtfs_update_data.schedule = GtfsSchedule()
            _LOGGER.debug("GTFS Static data cleared")

        for target in self.static_update_targets:
            await self.gtfs_update_data.schedule.async_build_schedule(
                target,
                session=async_get_clientsession(self.hass),
                **self.kwargs,
            )
            await self.gtfs_update_data.schedule.async_load_stop_times(
                set(self.gtfs_update_data.station_stops.keys())
            )

            _LOGGER.debug("GTFS Static Feed %s updated", target)
            self.last_static_update[target] = datetime.now()
        self.static_update_targets.clear()
