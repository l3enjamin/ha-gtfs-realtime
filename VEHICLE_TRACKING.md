# Vehicle Tracking with GTFS Realtime

## Overview

This integration now supports real-time vehicle position tracking for transit systems that provide GTFS Realtime VehiclePosition feeds. Vehicles are tracked as `device_tracker` entities with GPS coordinates, making them visible on Home Assistant maps.

## Features

- **Real-time vehicle locations** with GPS coordinates
- **Position history tracking** (configurable time window, default 10 minutes)
- **Dynamic entity creation** - vehicles appear/disappear as they enter/leave service
- **Route filtering** - choose which routes to track
- **Partial coverage support** - gracefully handles routes without vehicle positions

## Configuration

### Required Settings

1. **Vehicle Position URL**: The GTFS Realtime VehiclePosition feed URL
   - Example (TransLink): `https://gtfs.translink.ca/v2/gtfsposition?apikey=YOUR_KEY`

### Optional Settings

2. **Vehicle Position History** (default: 10 minutes)
   - How many minutes of position history to maintain for path rendering
   - Stored in memory, so consider RAM usage for large fleets

3. **Tracked Routes** (default: all routes)
   - Filter which routes' vehicles to track
   - Reduces entity count and memory usage
   - Example: Track only buses 430 and 49

## TransLink (Metro Vancouver) Example

TransLink provides vehicle positions for **buses only** - SkyTrain and SeaBus do not report vehicle locations.

### What Works
✅ Bus routes (e.g., 430, 49, 99 B-Line)  
✅ Stop sensors with arrival times for ALL routes  
✅ Map display of stops and bus positions  
✅ Vehicle path history  

### What Doesn't
❌ SkyTrain vehicle positions (Expo, Millennium, Canada Lines)  
❌ SeaBus vehicle positions  
❌ West Coast Express positions  

**This is expected behavior** - the integration will log informational messages for routes without vehicle data.

### Configuration Example

```yaml
# In YAML mode (not recommended, use UI)
gtfs_realtime:
  gtfs_provider: "TransLink"
  vehicle_position_url: "https://gtfs.translink.ca/v2/gtfsposition?apikey=YOUR_KEY"
  vehicle_position_history_minutes: 10
  tracked_routes:
    - "430"  # Bus 430 (Metrotown/UBC)
    - "049"  # Bus 49 (Metrotown/UBC)
    - "099"  # 99 B-Line (Commercial/UBC)
  stop_ids:
    - "50001"  # Broadway-City Hall Station
```

## Map Card Integration

Use the [custom:map-card](https://github.com/nathan-gs/ha-map-card) to display stops and vehicles with position history.

### Basic Example

```yaml
type: custom:map-card
title: TransLink Live Map
focus_entity: sensor.stop_broadway_city_hall
zoom: 14
history_start: 10 minutes ago
entities:
  # Stop sensor
  - entity: sensor.stop_broadway_city_hall
    display: marker
    color: blue
    size: 60
  
  # Vehicle trackers with path history
  - entity: device_tracker.bus_430_12345
    display: icon
    icon: mdi:bus
    color: '#E31937'  # TransLink red
    history_show_lines: true
    history_line_color: 'rgba(227, 25, 55, 0.6)'
    history_show_dots: true
```

### Advanced Example - All Vehicles on Route 430

```yaml
type: custom:map-card
title: Route 430 Live Tracking
zoom: 13
x: -123.116
y: 49.263
history_start: 15 minutes ago
entities:
  # Dynamically add all vehicles (use template sensor or automation)
  # Example assumes you have a helper that lists vehicle IDs
  {% for vehicle in states.device_tracker 
     | selectattr('attributes.route_id', 'eq', '430') %}
  - entity: {{ vehicle.entity_id }}
    display: icon
    icon: mdi:bus
    color: '#E31937'
    history_show_lines: true
    history_line_color: 'rgba(227, 25, 55, 0.5)'
    history_show_dots: true
  {% endfor %}
  
  # Add stops along route 430
  - entity: sensor.stop_joyce_station
    display: marker
  - entity: sensor.stop_ubc_exchange
    display: marker
```

## Entity Structure

### Stop Sensors

```yaml
sensor.stop_broadway_city_hall:
  state: 180  # Seconds to next arrival
  attributes:
    latitude: 49.2631
    longitude: -123.1161
    stop_name: "Broadway-City Hall Station"
    next_arrivals:
      - route_id: "099"
        headsign: "UBC"
        eta_seconds: 180
        vehicle_id: "18345"
        trip_id: "trip_123"
      - route_id: "009"
        headsign: "Boundary"
        eta_seconds: 420
        vehicle_id: null  # SkyTrain - no vehicle ID
```

### Vehicle Device Trackers

```yaml
device_tracker.bus_430_12345:
  state: not_home
  attributes:
    latitude: 49.2640
    longitude: -123.1150
    source_type: gps
    vehicle_id: "12345"
    route_id: "430"
    trip_id: "trip_430_123"
    bearing: 45  # Degrees
    speed: 35  # km/h
    last_update: "2025-12-24T10:00:00Z"
    position_history:
      - latitude: 49.2640
        longitude: -123.1150
        timestamp: "2025-12-24T10:00:00Z"
      - latitude: 49.2635
        longitude: -123.1145
        timestamp: "2025-12-24T09:59:30Z"
      # ... up to 10 minutes of positions
```

## Troubleshooting

### "Route X is tracked but has no vehicle position data"

**This is expected** for routes that don't provide vehicle positions (e.g., SkyTrain). The integration will still provide:
- Stop sensors with arrival times
- Stop coordinates for map display

You can safely ignore these log messages or remove the route from `tracked_routes`.

### High Memory Usage

If tracking many vehicles with long history windows:
1. Reduce `vehicle_position_history_minutes` (e.g., from 10 to 5)
2. Use `tracked_routes` to filter which routes to track
3. Consider using HA's recorder `exclude` to prevent storing device tracker history in the database:

```yaml
recorder:
  exclude:
    entity_globs:
      - device_tracker.bus_*
```

### Vehicles Not Appearing

1. **Check vehicle position URL** - Verify it returns VehiclePosition feed (not TripUpdate)
2. **Check route filtering** - If `tracked_routes` is set, vehicles on other routes won't appear
3. **Check logs** - Look for warnings about failed vehicle position fetches
4. **Verify API key** - Ensure your GTFS provider API key is valid

### Stale Positions

Vehicles are marked as `unavailable` if no position update received in 5 minutes. This is normal for:
- Vehicles going out of service
- End-of-line layovers
- GPS signal loss

## Performance Considerations

- **Update frequency**: Vehicle positions update every 30-60 seconds (depends on GTFS provider)
- **Entity count**: One device tracker per active vehicle (can be 50+ for busy routes)
- **Memory usage**: ~2KB per vehicle for 10 minutes of history
- **Database growth**: Use recorder `exclude` to prevent device tracker history bloat

## GTFS Compliance

This implementation follows the [GTFS Realtime VehiclePosition specification](https://gtfs.org/realtime/reference/#message-vehicleposition):

- Parses `VehiclePosition` messages from protobuf feed
- Extracts `position.latitude`, `position.longitude`, `position.bearing`, `position.speed`
- Links vehicles to routes via `trip.route_id`
- Handles optional fields gracefully

## Credits

- Original integration: [@bcpearce](https://github.com/bcpearce)
- Vehicle tracking: [@l3enjamin](https://github.com/l3enjamin)
- Map card: [@nathan-gs](https://github.com/nathan-gs/ha-map-card)
