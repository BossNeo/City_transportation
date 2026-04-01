from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import io
import math
import zipfile

import requests
from google.transit import gtfs_realtime_pb2

from .const import PROVIDERS

VEHICLE_TYPE_MAP = {0: "tram", 1: "subway", 3: "bus", 11: "trolleybus"}

@dataclass
class Stop:
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float

def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

class TransitFeed:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.stops = {}
        self.routes = {}
        self.trip_route_map = {}
        self.last_loaded = None

    def ensure_static_loaded(self):
        if self.last_loaded and (datetime.now(timezone.utc) - self.last_loaded).total_seconds() < 86400 and self.stops:
            return

        urls = PROVIDERS[self.provider]
        resp = requests.get(urls["static_url"], timeout=60)
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))

        with zf.open("stops.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            self.stops = {
                row["stop_id"]: Stop(
                    stop_id=row["stop_id"],
                    stop_name=row["stop_name"],
                    stop_lat=float(row["stop_lat"]),
                    stop_lon=float(row["stop_lon"]),
                )
                for row in reader
                if row.get("location_type", "0") in ("", "0")
            }

        with zf.open("routes.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            self.routes = {}
            for row in reader:
                self.routes[row["route_id"]] = {
                    "short_name": row.get("route_short_name") or row.get("route_long_name") or row["route_id"],
                    "long_name": row.get("route_long_name", ""),
                    "vehicle_type": VEHICLE_TYPE_MAP.get(int(row.get("route_type", "3")), "other"),
                }

        with zf.open("trips.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            self.trip_route_map = {row["trip_id"]: row["route_id"] for row in reader}

        self.last_loaded = datetime.now(timezone.utc)

    def find_stops_in_radius(self, lat: float, lon: float, radius_m: int):
        self.ensure_static_loaded()
        result = []
        for stop_id, stop in self.stops.items():
            dist = haversine_m(lat, lon, stop.stop_lat, stop.stop_lon)
            if dist <= radius_m:
                result.append((stop_id, dist))
        result.sort(key=lambda x: x[1])
        return result

    def get_departures_by_stop(self, stop_ids, vehicle_types=None, time_window_min=30):
        urls = PROVIDERS[self.provider]
        resp = requests.get(urls["trip_updates_url"], timeout=30)
        resp.raise_for_status()
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(resp.content)

        now_ts = int(datetime.now(timezone.utc).timestamp())
        max_ts = now_ts + time_window_min * 60
        stop_ids = set(stop_ids)
        out = {sid: [] for sid in stop_ids}

        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            trip = entity.trip_update.trip
            route_id = self.trip_route_map.get(trip.trip_id)
            route = self.routes.get(route_id, {})
            vtype = route.get("vehicle_type", "other")
            if vehicle_types and vtype not in vehicle_types:
                continue
            for stu in entity.trip_update.stop_time_update:
                sid = stu.stop_id
                if sid not in stop_ids:
                    continue
                ts = None
                if stu.HasField("arrival") and stu.arrival.time:
                    ts = stu.arrival.time
                elif stu.HasField("departure") and stu.departure.time:
                    ts = stu.departure.time
                if not ts or ts < now_ts or ts > max_ts:
                    continue
                out[sid].append({
                    "line": str(route.get("short_name", route_id or "?")),
                    "vehicle_type": vtype,
                    "arrival_unix": ts,
                    "arrival_local": datetime.fromtimestamp(ts).strftime("%H:%M"),
                    "minutes": max(0, math.ceil((ts - now_ts) / 60)),
                    "destination": route.get("long_name", ""),
                })
        for sid in out:
            out[sid].sort(key=lambda x: (x["arrival_unix"], x["line"]))
        return out
