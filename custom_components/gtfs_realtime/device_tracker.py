"""Platform for device tracker integration (vehicle positions)."""

from __future__ import annotations
from collections import deque
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.gtfs_realtime import GtfsRealtimeConfigEntry

from .const import (
    ATTR_VEHICLE_ID,
    DOMAIN,
    ROUTE_ID,
    TRIP_ID,
)
from .coordinator import GtfsRealtimeCoordinator

_LOGGER = logging.getLogger(__name__)

MAX_POSITION_AGE_MINUTES = 5  # Consider vehicle unavailable if no update in 5 minutes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GtfsRealtimeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device trackers, dynamically adding vehicles as they appear."""
    coordinator: GtfsRealtimeCoordinator = entry.runtime_data
    
    # Only proceed if vehicle position URL is configured
    if not coordinator.vehicle_position_url:
        _LOGGER.info(
            "Vehicle position URL not configured for %s. "
            "Vehicle tracking will not be available.",
            coordinator.gtfs_provider or "GTFS provider"
        )
        return
    
    tracked_vehicles: dict[str, GtfsVehicleTracker] = {}
    
    @callback
    def async_add_vehicle_trackers():
        """Add trackers for newly discovered vehicles."""
        new_trackers = []
        
        # Get all vehicles currently in position feed
        for vehicle_id, position in coordinator.data.vehicle_positions.items():
            # Skip if already tracking
            if vehicle_id in tracked_vehicles:
                continue
            
            # Extract route ID from vehicle position
            route_id = None
            if hasattr(position, 'trip') and hasattr(position.trip, 'route_id'):
                route_id = position.trip.route_id
            
            # Only track vehicles on routes we're monitoring (if configured)
            if coordinator.data.tracked_routes and route_id not in coordinator.data.tracked_routes:
                continue
            
            tracker = GtfsVehicleTracker(coordinator, vehicle_id, route_id)
            tracked_vehicles[vehicle_id] = tracker
            new_trackers.append(tracker)
            _LOGGER.debug(
                "Adding tracker for vehicle %s on route %s",
                vehicle_id,
                route_id or "unknown"
            )
        
        if new_trackers:
            async_add_entities(new_trackers)
    
    # Initial setup
    async_add_vehicle_trackers()
    
    # Listen for coordinator updates to add new vehicles
    entry.async_on_unload(
        coordinator.async_add_listener(async_add_vehicle_trackers)
    )


class GtfsVehicleTracker(TrackerEntity, CoordinatorEntity):
    """Device tracker for GTFS realtime vehicle positions."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GtfsRealtimeCoordinator,
        vehicle_id: str,
        route_id: str | None = None,
    ) -> None:
        """Initialize the vehicle tracker."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._route_id = route_id
        self._attr_unique_id = f"vehicle_{vehicle_id}"
        self._attr_name = f"Vehicle {vehicle_id}"
        
        # Position history for path drawing (configurable time window)
        history_minutes = coordinator.vehicle_position_history_minutes
        self._position_history: deque[tuple[float, float, datetime]] = deque(
            maxlen=history_minutes * 2  # Assuming ~30s updates = 2 per minute
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type (GPS)."""
        return SourceType.GPS

    @property
    def available(self) -> bool:
        """Return if vehicle is currently reporting position."""
        vehicle_pos = self._get_vehicle_position()
        if not vehicle_pos:
            return False
        
        # Check if position is stale
        if hasattr(vehicle_pos, 'timestamp') and vehicle_pos.timestamp:
            age = datetime.now() - datetime.fromtimestamp(vehicle_pos.timestamp)
            return age < timedelta(minutes=MAX_POSITION_AGE_MINUTES)
        
        return True

    @property
    def latitude(self) -> float | None:
        """Return latitude from VehiclePosition feed."""
        try:
            vehicle_pos = self._get_vehicle_position()
            if vehicle_pos and hasattr(vehicle_pos, 'position'):
                lat = vehicle_pos.position.latitude
                # Update position history
                if lat is not None:
                    self._update_position_history(lat, self.longitude)
                return lat
        except (AttributeError, KeyError) as err:
            _LOGGER.debug(
                "No latitude data for vehicle %s: %s",
                self._vehicle_id,
                err
            )
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude from VehiclePosition feed."""
        try:
            vehicle_pos = self._get_vehicle_position()
            if vehicle_pos and hasattr(vehicle_pos, 'position'):
                return vehicle_pos.position.longitude
        except (AttributeError, KeyError) as err:
            _LOGGER.debug(
                "No longitude data for vehicle %s: %s",
                self._vehicle_id,
                err
            )
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes about the vehicle."""
        vehicle_pos = self._get_vehicle_position()
        attributes = {
            ATTR_VEHICLE_ID: self._vehicle_id,
        }
        
        if vehicle_pos:
            try:
                if hasattr(vehicle_pos, 'trip'):
                    if hasattr(vehicle_pos.trip, 'route_id'):
                        attributes[ROUTE_ID] = vehicle_pos.trip.route_id
                        self._route_id = vehicle_pos.trip.route_id  # Update cached route
                    if hasattr(vehicle_pos.trip, 'trip_id'):
                        attributes[TRIP_ID] = vehicle_pos.trip.trip_id
                
                if hasattr(vehicle_pos, 'position'):
                    if hasattr(vehicle_pos.position, 'bearing'):
                        attributes['bearing'] = vehicle_pos.position.bearing
                    if hasattr(vehicle_pos.position, 'speed'):
                        attributes['speed'] = vehicle_pos.position.speed
                
                if hasattr(vehicle_pos, 'timestamp'):
                    attributes['last_update'] = datetime.fromtimestamp(
                        vehicle_pos.timestamp
                    ).isoformat()
            except (AttributeError, KeyError) as err:
                _LOGGER.debug(
                    "Error extracting vehicle attributes for %s: %s",
                    self._vehicle_id,
                    err
                )
        
        # Add position history for path rendering
        if self._position_history:
            attributes['position_history'] = [
                {
                    'latitude': lat,
                    'longitude': lon,
                    'timestamp': ts.isoformat()
                }
                for lat, lon, ts in self._position_history
            ]
        
        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the vehicle."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"vehicle_{self._vehicle_id}")},
            name=f"Vehicle {self._vehicle_id}",
            manufacturer=self.coordinator.gtfs_provider,
            model=f"Route {self._route_id}" if self._route_id else "Transit Vehicle",
        )

    def _get_vehicle_position(self) -> Any | None:
        """Get vehicle position from coordinator data."""
        return self.coordinator.data.vehicle_positions.get(self._vehicle_id)

    def _update_position_history(self, lat: float | None, lon: float | None) -> None:
        """Update the position history deque."""
        if lat is not None and lon is not None:
            now = datetime.now()
            # Only add if different from last position
            if not self._position_history or (
                self._position_history[-1][0] != lat
                or self._position_history[-1][1] != lon
            ):
                self._position_history.append((lat, lon, now))
                self._prune_old_positions()

    def _prune_old_positions(self) -> None:
        """Remove positions older than the configured time window."""
        if not self._position_history:
            return
        
        cutoff = datetime.now() - timedelta(
            minutes=self.coordinator.vehicle_position_history_minutes
        )
        
        while self._position_history and self._position_history[0][2] < cutoff:
            self._position_history.popleft()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            super()._handle_coordinator_update()
        except Exception as err:
            _LOGGER.error(
                "Exception occurred updating vehicle tracker %s: %s",
                self._vehicle_id,
                err,
                exc_info=True,
            )
            raise
