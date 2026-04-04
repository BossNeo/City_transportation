"""
Transit data layer for Sofia Live Transport.

Handles:
  - GTFS static feed download, ZIP extraction and parsing (cached 24h)
  - GTFS-RT trip updates fetching and parsing
  - Haversine distance calculation
  - Stop discovery within radius
  - Departure merging (static schedule + RT delays)
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    import aiohttp

from .const import ROUTE_TYPE_MAP

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Stop:
    stop_id: str
    stop_name: str
    lat: float
    lon: float
    distance_m: float = 0.0


@dataclass
class StopTime:
    trip_id: str
    arrival_time: str   # HH:MM:SS (may exceed 24h for overnight)
    departure_time: str
    stop_id: str
    stop_sequence: int


@dataclass
class Trip:
    trip_id: str
    route_id: str
    service_id: str
    trip_headsign: str = ""
    direction_id: str = ""


@dataclass
class Route:
    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int


@dataclass
class CalendarDate:
    service_id: str
    date: str       # YYYYMMDD
    exception_type: int  # 1=added, 2=removed


@dataclass
class Departure:
    line: str
    vehicle_type: str
    minutes: int
    arrival_time: str       # HH:MM local
    destination: str
    delay_seconds: int
    delay_minutes: int
    delay_label: str
    delay_status: str       # late / early / on_time
    is_delayed: bool


@dataclass
class GTFSStaticData:
    stops: Dict[str, Stop] = field(default_factory=dict)
    stop_times: List[StopTime] = field(default_factory=list)
    trips: Dict[str, Trip] = field(default_factory=dict)
    routes: Dict[str, Route] = field(default_factory=dict)
    calendar_dates: List[CalendarDate] = field(default_factory=list)
    fetched_at: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DELAY_THRESHOLD = 60  # seconds – within this = on_time


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in metres between two WGS-84 coordinates."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _gtfs_time_to_seconds(time_str: str) -> int:
    """Convert GTFS HH:MM:SS (may be >24h) to total seconds since midnight."""
    parts = time_str.strip().split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def _seconds_to_hhmm(total_seconds: int) -> str:
    """Format seconds-since-midnight as HH:MM (wraps at 48h)."""
    total_seconds = total_seconds % 86400
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    return f"{h:02d}:{m:02d}"


def _build_delay_info(delay_s: int) -> tuple[int, str, str, bool]:
    """Return (delay_minutes, delay_label, delay_status, is_delayed)."""
    delay_min = round(delay_s / 60)
    if abs(delay_s) <= DELAY_THRESHOLD:
        return 0, "", "on_time", False
    if delay_s > 0:
        label = f"+{delay_min} мин" if delay_min != 0 else "+<1 мин"
        return delay_min, label, "late", True
    label = f"{delay_min} мин"
    return delay_min, label, "early", False


def _active_services_today(calendar_dates: List[CalendarDate]) -> set[str]:
    """Return set of service_ids active today using calendar_dates.txt.

    Returns an empty set when calendar_dates is empty, which the caller
    treats as "no filter" (all services allowed).
    """
    today_str = datetime.now().strftime("%Y%m%d")
    added: set[str] = set()
    removed: set[str] = set()
    for cd in calendar_dates:
        if cd.date == today_str:
            if cd.exception_type == 1:
                added.add(cd.service_id)
            elif cd.exception_type == 2:
                removed.add(cd.service_id)
    return added - removed


def _route_type_to_vehicle(route_type: int) -> str:
    """Map GTFS route_type integer to internal vehicle type string."""
    return ROUTE_TYPE_MAP.get(route_type, "bus")


# ---------------------------------------------------------------------------
# GTFS static loader
# ---------------------------------------------------------------------------

STATIC_CACHE_TTL = 86400  # 24h in seconds


class GTFSStaticLoader:
    """Download, cache and parse GTFS static ZIP feed."""

    def __init__(self, url: str, session: "aiohttp.ClientSession") -> None:
        self._url = url
        self._session = session
        self._cache: Optional[GTFSStaticData] = None

    async def get(self) -> GTFSStaticData:
        """Return cached data or fetch fresh."""
        now = time.monotonic()
        if self._cache and (now - self._cache.fetched_at) < STATIC_CACHE_TTL:
            return self._cache

        _LOGGER.debug("Fetching GTFS static feed from %s", self._url)
        try:
            import aiohttp  # local import – aiohttp is a HA dependency, always present
            async with self._session.get(
                self._url, timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                resp.raise_for_status()
                raw = await resp.read()
        except Exception as exc:
            _LOGGER.error("Failed to download GTFS static feed: %s", exc)
            if self._cache:
                _LOGGER.warning("Returning stale GTFS static cache")
                return self._cache
            raise

        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self._parse_zip, raw)
        data.fetched_at = time.monotonic()
        self._cache = data
        _LOGGER.info(
            "GTFS static loaded: %d stops, %d routes, %d trips, %d stop_times",
            len(data.stops),
            len(data.routes),
            len(data.trips),
            len(data.stop_times),
        )
        return data

    @staticmethod
    def _parse_zip(raw_bytes: bytes) -> GTFSStaticData:
        """Parse GTFS ZIP in a thread-pool executor."""
        data = GTFSStaticData()
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            names = zf.namelist()

            # --- stops.txt ---
            if "stops.txt" in names:
                with zf.open("stops.txt") as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                    for row in reader:
                        sid = row.get("stop_id", "").strip()
                        if not sid:
                            continue
                        try:
                            lat = float(row.get("stop_lat", 0) or 0)
                            lon = float(row.get("stop_lon", 0) or 0)
                        except ValueError:
                            continue
                        data.stops[sid] = Stop(
                            stop_id=sid,
                            stop_name=row.get("stop_name", sid).strip(),
                            lat=lat,
                            lon=lon,
                        )

            # --- routes.txt ---
            if "routes.txt" in names:
                with zf.open("routes.txt") as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                    for row in reader:
                        rid = row.get("route_id", "").strip()
                        if not rid:
                            continue
                        try:
                            rtype = int(row.get("route_type", 3) or 3)
                        except ValueError:
                            rtype = 3
                        data.routes[rid] = Route(
                            route_id=rid,
                            route_short_name=row.get("route_short_name", rid).strip(),
                            route_long_name=row.get("route_long_name", "").strip(),
                            route_type=rtype,
                        )

            # --- trips.txt ---
            if "trips.txt" in names:
                with zf.open("trips.txt") as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                    for row in reader:
                        tid = row.get("trip_id", "").strip()
                        if not tid:
                            continue
                        data.trips[tid] = Trip(
                            trip_id=tid,
                            route_id=row.get("route_id", "").strip(),
                            service_id=row.get("service_id", "").strip(),
                            trip_headsign=row.get("trip_headsign", "").strip(),
                            direction_id=row.get("direction_id", "").strip(),
                        )

            # --- stop_times.txt ---
            if "stop_times.txt" in names:
                with zf.open("stop_times.txt") as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                    for row in reader:
                        try:
                            seq = int(row.get("stop_sequence", 0) or 0)
                        except ValueError:
                            seq = 0
                        data.stop_times.append(
                            StopTime(
                                trip_id=row.get("trip_id", "").strip(),
                                arrival_time=row.get("arrival_time", "").strip(),
                                departure_time=row.get("departure_time", "").strip(),
                                stop_id=row.get("stop_id", "").strip(),
                                stop_sequence=seq,
                            )
                        )

            # --- calendar_dates.txt ---
            if "calendar_dates.txt" in names:
                with zf.open("calendar_dates.txt") as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                    for row in reader:
                        try:
                            exc_type = int(row.get("exception_type", 1) or 1)
                        except ValueError:
                            exc_type = 1
                        data.calendar_dates.append(
                            CalendarDate(
                                service_id=row.get("service_id", "").strip(),
                                date=row.get("date", "").strip(),
                                exception_type=exc_type,
                            )
                        )

        return data


# ---------------------------------------------------------------------------
# GTFS-RT loader
# ---------------------------------------------------------------------------


class GTFSRealtimeLoader:
    """Fetch and parse GTFS-RT trip updates protobuf."""

    def __init__(self, url: str, session: "aiohttp.ClientSession") -> None:
        self._url = url
        self._session = session

    async def get_delays(self) -> Dict[str, int]:
        """Return dict {trip_id: delay_seconds} from latest RT feed."""
        try:
            import aiohttp  # local import – always present as HA dependency
            async with self._session.get(
                self._url, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                resp.raise_for_status()
                raw = await resp.read()
        except Exception as exc:
            _LOGGER.warning("Failed to fetch GTFS-RT feed: %s", exc)
            return {}

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parse_pb, raw)

    @staticmethod
    def _parse_pb(raw: bytes) -> Dict[str, int]:
        """Parse protobuf bytes in a thread-pool executor.

        Returns {trip_id: delay_seconds}.
        """
        delays: Dict[str, int] = {}
        try:
            from google.transit import gtfs_realtime_pb2  # type: ignore[import]

            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(raw)
            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue
                tu = entity.trip_update
                trip_id = tu.trip.trip_id
                if not tu.stop_time_update:
                    continue
                # Extract delay from the first stop_time_update.
                # IMPORTANT: `delay` is a protobuf3 int32 scalar field.
                # HasField() raises TypeError on scalar fields – do NOT use it.
                # Unset scalars default to 0 (= on-time), which is correct.
                if not tu.stop_time_update:
                    continue
                stu = tu.stop_time_update[0]
                if stu.HasField("arrival"):
                    delays[trip_id] = stu.arrival.delay
                elif stu.HasField("departure"):
                    delays[trip_id] = stu.departure.delay
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to parse GTFS-RT protobuf: %s", exc)
        return delays


# ---------------------------------------------------------------------------
# Main coordinator data builder
# ---------------------------------------------------------------------------


async def build_stop_departures(
    static: GTFSStaticData,
    delays: Dict[str, int],
    center_lat: float,
    center_lon: float,
    radius_m: float,
    time_window_min: int,
    allowed_vehicle_types: List[str],
) -> Dict[str, dict]:
    """Return a dict keyed by stop_id with stop info and departure list.

    CPU-heavy work runs in a thread-pool executor so the event loop is
    never blocked.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        _build_stop_departures_sync,
        static,
        delays,
        center_lat,
        center_lon,
        radius_m,
        time_window_min,
        allowed_vehicle_types,
    )


def _build_stop_departures_sync(
    static: GTFSStaticData,
    delays: Dict[str, int],
    center_lat: float,
    center_lon: float,
    radius_m: float,
    time_window_min: int,
    allowed_vehicle_types: List[str],
) -> Dict[str, dict]:
    """Synchronous departure building (runs in executor)."""
    allowed_set = set(allowed_vehicle_types)

    # 1. Find stops within radius
    nearby: Dict[str, Stop] = {}
    for sid, stop in static.stops.items():
        dist = haversine_m(center_lat, center_lon, stop.lat, stop.lon)
        if dist <= radius_m:
            stop.distance_m = round(dist, 1)
            nearby[sid] = stop

    if not nearby:
        return {}

    # 2. Build route_id -> vehicle_type lookup
    route_vehicle: Dict[str, str] = {
        rid: _route_type_to_vehicle(r.route_type)
        for rid, r in static.routes.items()
    }

    # 3. Active services today (empty set = no filter applied)
    active_services = _active_services_today(static.calendar_dates)

    # 4. Current time in seconds since midnight
    now_local = datetime.now()
    now_secs = now_local.hour * 3600 + now_local.minute * 60 + now_local.second
    window_end_secs = now_secs + time_window_min * 60

    # 5. Fast lookup tables from trips
    trip_route: Dict[str, str] = {
        tid: t.route_id for tid, t in static.trips.items()
    }
    trip_headsign: Dict[str, str] = {
        tid: t.trip_headsign for tid, t in static.trips.items()
    }
    trip_service: Dict[str, str] = {
        tid: t.service_id for tid, t in static.trips.items()
    }

    # 6. Index stop_times by stop_id for O(stops) iteration instead of O(N*M)
    stop_times_by_stop: Dict[str, List[StopTime]] = {}
    for st in static.stop_times:
        if st.stop_id in nearby:
            stop_times_by_stop.setdefault(st.stop_id, []).append(st)

    # 7. Build departures per stop
    result: Dict[str, dict] = {}

    for sid, stop in nearby.items():
        departures: List[Departure] = []

        for st in stop_times_by_stop.get(sid, []):
            tid = st.trip_id

            # Filter by active service (only when calendar_dates is populated)
            if active_services:
                svc = trip_service.get(tid, "")
                if svc not in active_services:
                    continue

            # Parse scheduled departure time
            dep_str = st.departure_time or st.arrival_time
            if not dep_str:
                continue
            try:
                sched_secs = _gtfs_time_to_seconds(dep_str)
            except (ValueError, IndexError):
                continue

            # Apply RT delay
            delay_s = delays.get(tid, 0)
            actual_secs = sched_secs + delay_s

            # Within time window?
            if actual_secs < now_secs or actual_secs > window_end_secs:
                continue

            # Vehicle type filter
            rid = trip_route.get(tid, "")
            vehicle_type = route_vehicle.get(rid, "bus")
            if vehicle_type not in allowed_set:
                continue

            route = static.routes.get(rid)
            line = route.route_short_name if route else rid
            destination = trip_headsign.get(tid, "")

            minutes_until = max(0, round((actual_secs - now_secs) / 60))
            arrival_local = _seconds_to_hhmm(actual_secs)

            delay_min, delay_label, delay_status, is_delayed = _build_delay_info(delay_s)

            departures.append(
                Departure(
                    line=line,
                    vehicle_type=vehicle_type,
                    minutes=minutes_until,
                    arrival_time=arrival_local,
                    destination=destination,
                    delay_seconds=delay_s,
                    delay_minutes=delay_min,
                    delay_label=delay_label,
                    delay_status=delay_status,
                    is_delayed=is_delayed,
                )
            )

        # Sort ascending by minutes until departure
        departures.sort(key=lambda d: d.minutes)

        result[sid] = {
            "stop": stop,
            "departures": departures,
        }

    return result
