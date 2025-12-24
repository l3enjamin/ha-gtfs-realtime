
![GTFS Realtime](resources/logo.svg)
# GTFS Realtime for Home Assistant

[![Coverage Status](https://coveralls.io/repos/github/bcpearce/homeassistant-gtfs-realtime/badge.svg?branch=main)](https://coveralls.io/github/bcpearce/homeassistant-gtfs-realtime?branch=main)

[![Check GTFS Feed Compatibility](https://github.com/bcpearce/homeassistant-gtfs-realtime/actions/workflows/feed_compatibility.yaml/badge.svg)](https://github.com/bcpearce/homeassistant-gtfs-realtime/actions/workflows/feed_compatibility.yaml)

## Installation

This integration can be installed manually or through [HACS](https://hacs.xyz/).

#### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bcpearce&repository=homeassistant-gtfs-realtime&category=Integration)

This repository is now included in HACS's defaults.

#### Manual

Copy files in [custom_components/gtfs_realtime](custom_components/gtfs_realtime/) to [/path/to/homeassistant/config/custom_components/gtfs_realtime](#).

## Configuration

Once the integration is installed, the configure the integration through Settings >> Devices and Services, and use "Add Integration".  Select GTFS Realtime and follow the instructions in the user interface.

You can select a supported provider or configure it manually. A number of GTFS providers are included for convenience in this repository.  

There is no guarantee that these providers will continue to work with this integration.  A [GitHub Action Workflow](https://github.com/bcpearce/homeassistant-gtfs-realtime/actions/workflows/feed_compatibility.yaml) runs to check the status of each feed. 

### Realtime Feed URLs

These are the URLs that will be queried for realtime updates. Using a preconfigured provider may include feeds you do not need, these can be deleted here to improve performance. Note that static feeds are *also* required alongside realtime feeds for full schedule information such as destination headsigns and route IDs. 

### Static Feed URLs

Less frequently updated data will be provided as one or more .zip files. Include the URL your provider supplies these files at. It is updated less frequently, and can be customized to match the release rate of your provider. 

### API Key

If your provider requires an API Key, it can be included as a header field for HTTP requests. It should be given in the format expected by your provider. Hints with placeholders are provided for preconfigured feeds that require authentication. 

In some cases, the API key might be provided as a URL parameter, in this case you should update the feed URL for the feed to include it. 

### Route Icons

Optionally route icons can be included.  The integration will default to using MDI icons otherwise. For NYC Subway integrations, and other supported integrations, the resources folder may contain valid route icons to use.  

For custom use, a URL must be provided that includes up to three Python format braces for `{route_id}`, `{route_color}` and `{route_text_color}`. At minimum, `{route_id}` must be provided.  These braces should be placed in the input string and conform to the requirements in Python'a [str.format()](https://docs.python.org/3/library/stdtypes.html#str.format) method. 

#### Resources

The [resources/NYCT_Bullets](resources/NYCT_Bullets/) folder contains ready-to-use SVG files for customizing arrival icons for the New York City Subway, provided by Wikimedia Commons.

### Other Transit Systems

This software may work for other GTFS realtime providers, but has not been tested. There is no guarantee that providers--even if included in this repository--will work--or that changes in provider APIs will not cause breakages. 

## Frontend

Example frontend card configs can be found in [example/frontend.yaml](example/frontend.yaml).

Simply displaying all entities for a "stop" device provides a train arrival board.

![sample dashboard](resources/sample.png)

## Map Integration

Stop sensors now include geographic coordinates (latitude/longitude) from GTFS static data, making them compatible with Home Assistant's map card and custom map cards like [`custom:map-card`](https://github.com/nathan-gs/ha-map-card).

### Stop Sensor Structure

Each stop creates a single sensor entity with:
- **State**: Time in seconds until next arrival (displayed as minutes)
- **Attributes**:
  - `latitude`: Stop latitude from GTFS stops.txt
  - `longitude`: Stop longitude from GTFS stops.txt
  - `stop_name`: Human-readable stop name
  - `next_arrivals`: Array of upcoming arrivals (up to configured limit)

### Next Arrivals Format

Each arrival in the `next_arrivals` attribute contains:
```yaml
- route_id: "99"          # Route identifier
  headsign: "UBC"         # Trip destination
  trip_id: "trip_123"     # Unique trip ID
  eta_seconds: 180        # Seconds until arrival
  route_color: "#0039A6"  # Route color (hex)
  route_text_color: "#FFFFFF"
  route_type: "BUS"       # TRAM, SUBWAY, RAIL, FERRY, BUS
  vehicle_id: "1234"      # Vehicle ID (if available)
```

### Example: Map Card Configuration

Using [`custom:map-card`](https://github.com/nathan-gs/ha-map-card) to display stops:

```yaml
type: custom:map-card
focus_entity: sensor.stop_broadway_station
zoom: 14
entities:
  - entity: sensor.stop_broadway_station
    display: marker
    size: 60
    color: blue
  - entity: sensor.stop_41st_avenue
    display: marker
    size: 60
    color: blue
```

### Template Sensor for Next Arrival Display

Create a template sensor to display formatted arrival information:

```yaml
template:
  - sensor:
      - name: "Broadway Station Next Bus"
        state: >-
          {% set arrivals = state_attr('sensor.stop_broadway_station', 'next_arrivals') %}
          {% if arrivals and arrivals|length > 0 %}
            {{ arrivals[0].route_id }} to {{ arrivals[0].headsign }} in {{ (arrivals[0].eta_seconds / 60)|round(0) }} min
          {% else %}
            No arrivals
          {% endif %}
```

## Sensors

### Stop Sensor

One sensor is created per configured stop. The sensor state represents the time in seconds until the next arrival at that stop.

The sensor includes geographic coordinates and a `next_arrivals` attribute containing detailed information about upcoming trips.

**Note**: This replaces the previous implementation which created multiple individual arrival sensors per stop.

### Alert Sensor

Alert sensors can be setup for a `route_id`. The [example/frontend.yaml](example/frontend.yaml) file shows how to set up conditional cards that display only if an alert is active. The alert sensor will switch to the "Problem" state if an alert is active for a given station or route. This can be used in automations, such as turning on an indicator LED when an alert becomes active. 

## Devices

Each stop will collect its sensor together as a device. For each static data collection, a device is also included for managing the schedule updates.

## Services

Services are provided for updating and clearing the static data schedule. During setup, an interval for refreshing this data can be provided.

## GTFS Station Stop

This package utilizes [GTFS Station Stop](https://pypi.org/project/gtfs-station-stop/) to provide updates to Home Assistant sensors. 

## Disclaimer

This software is not developed with or affiliated with Home Assistant or with any GTFS API provider. It is not guaranteed to work, use at your own risk. 
