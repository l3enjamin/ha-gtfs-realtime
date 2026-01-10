"""Test the GTFS Realtime device tracker."""
from unittest.mock import MagicMock, patch
import pytest

from collections import deque
from custom_components.gtfs_realtime.device_tracker import GtfsVehicleTracker
from custom_components.gtfs_realtime.coordinator import GtfsRealtimeCoordinator

async def test_vehicle_tracker_init_with_float_history_minutes(hass):
    """Test initializing vehicle tracker with float history minutes."""
    coordinator = MagicMock(spec=GtfsRealtimeCoordinator)
    coordinator.vehicle_position_history_minutes = 10.5

    tracker = GtfsVehicleTracker(coordinator, "vehicle_1")

    assert tracker._position_history.maxlen == 21
    assert isinstance(tracker._position_history, deque)

async def test_vehicle_tracker_init_with_int_history_minutes(hass):
    """Test initializing vehicle tracker with int history minutes."""
    coordinator = MagicMock(spec=GtfsRealtimeCoordinator)
    coordinator.vehicle_position_history_minutes = 10

    tracker = GtfsVehicleTracker(coordinator, "vehicle_1")

    assert tracker._position_history.maxlen == 20
    assert isinstance(tracker._position_history, deque)
