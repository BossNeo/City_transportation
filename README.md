# Sofia Live Transport

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for real-time public transport departures in Sofia, Bulgaria.

## Features

- Real-time departure times from nearby stops using GTFS static + GTFS-RT feeds
- Covers **buses**, **trams**, **trolleybuses**, and **subway** lines
- Configurable radius, time window, and refresh interval
- Per-stop sensors with full departure details
- Delay information (early / on time / late) with Bulgarian-language labels
- Binary sensor per stop indicating active delays
- Vehicle-type icons

## Installation

### HACS (Recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add: `https://github.com/your-username/sofia_live_transport` (type: Integration)
3. Install **Sofia Live Transport**
4. Restart Home Assistant

### Manual

1. Copy `custom_components/sofia_live_transport/` to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Sofia Live Transport**
3. Fill in the config form:

| Field | Description | Default |
|-------|-------------|---------|
| Name | Instance name | Sofia Transport |
| Latitude | Center latitude | HA home lat |
| Longitude | Center longitude | HA home lon |
| Radius (m) | Stop search radius | 150 |
| Time window (min) | How far ahead to show departures | 30 |
| Refresh interval (s) | How often to poll RT feed | 60 |
| Vehicle types | Comma-separated types | bus,tram,trolleybus,subway |

Valid vehicle types: `bus`, `tram`, `trolleybus`, `subway`

## Entities Created

For each stop found within your radius:

| Entity | Description |
|--------|-------------|
| `sensor.<name>_<stop>_departures` | Full list of upcoming departures in attributes |
| `sensor.<name>_<stop>_next` | State = next departure summary, e.g. `204 след 5 мин` |
| `binary_sensor.<name>_<stop>_has_delay` | `on` if any departure is currently delayed |

### Departure Attributes

Each departure in the list includes:

```yaml
line: "204"
vehicle_type: "bus"
minutes: 5
arrival_time: "14:32"
destination: "Младост 1"
delay_seconds: 180
delay_minutes: 3
delay_label: "+3 мин"
delay_status: "late"
is_delayed: true
```

## Data Sources

- **Static GTFS**: `https://gtfs.sofiatraffic.bg/api/v1/static` (cached 24h)
- **GTFS-RT Trip Updates**: `https://gtfs.sofiatraffic.bg/api/v1/trip-updates`

## Requirements

- Home Assistant 2024.6.0+
- `gtfs-realtime-bindings`
- `protobuf`
- `aiohttp`
- `aiofiles`

## License

MIT
