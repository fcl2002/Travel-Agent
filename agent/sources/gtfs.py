"""Offer source backed by an operator's GTFS feed: real timetables, prices from a Pricer."""

import csv
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

from agent.domain.search import Leg, Offer, Segment, Stop, TransportMode
from agent.sources.base import OutsideCoverageError, Pricer

CITY_STOPS_PATH = Path(__file__).with_name("city_stops.json")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
BUS_ROUTE_TYPES = {"3", *(str(code) for code in range(700, 717))}
RAIL_ROUTE_TYPES = {"2", *(str(code) for code in range(100, 118))}


class StopTime(NamedTuple):
    stop_id: str
    arrival_seconds: int
    departure_seconds: int
    allows_pickup: bool
    allows_drop_off: bool


class Service(NamedTuple):
    first_day: date
    last_day: date
    weekdays: tuple[bool, ...]


def _rows(folder: Path, name: str) -> Iterator[dict[str, str]]:
    path = folder / name
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as file:
            yield from csv.DictReader(file)


def _day(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def _seconds(value: str) -> int:
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def _mode(route_type: str) -> TransportMode:
    if route_type in BUS_ROUTE_TYPES:
        return TransportMode.BUS
    if route_type in RAIL_ROUTE_TYPES:
        return TransportMode.TRAIN
    return TransportMode.OTHER


class GtfsFeed:
    def __init__(self, folder: Path):
        agency_timezone = next(_rows(folder, "agency.txt"))["agency_timezone"]
        self.stops = {
            row["stop_id"]: (row["stop_name"], ZoneInfo(row.get("stop_timezone") or agency_timezone))
            for row in _rows(folder, "stops.txt")
        }
        self.routes = {
            row["route_id"]: (_mode(row["route_type"]), row.get("route_short_name") or row.get("route_long_name") or None)
            for row in _rows(folder, "routes.txt")
        }
        self.trips = {row["trip_id"]: (row["route_id"], row["service_id"]) for row in _rows(folder, "trips.txt")}
        self.services = {
            row["service_id"]: Service(_day(row["start_date"]), _day(row["end_date"]),
                                       tuple(row[weekday] == "1" for weekday in WEEKDAYS))
            for row in _rows(folder, "calendar.txt")
        }
        self.exceptions = {
            (row["service_id"], _day(row["date"])): row["exception_type"] == "1"
            for row in _rows(folder, "calendar_dates.txt")
        }
        days = [day for service in self.services.values() for day in (service.first_day, service.last_day)]
        days += [day for _, day in self.exceptions]
        self.first_day, self.last_day = min(days), max(days)

        sequenced: dict[str, list[tuple[int, StopTime]]] = {}
        for row in _rows(folder, "stop_times.txt"):
            sequenced.setdefault(row["trip_id"], []).append((int(row["stop_sequence"]), StopTime(
                row["stop_id"], _seconds(row["arrival_time"]), _seconds(row["departure_time"]),
                row.get("pickup_type", "") != "1", row.get("drop_off_type", "") != "1",
            )))
        self.stop_times = {trip_id: tuple(stop for _, stop in sorted(items)) for trip_id, items in sequenced.items()}
        self.trips_at_stop: dict[str, list[tuple[str, int]]] = {}
        for trip_id, stops in self.stop_times.items():
            for index, stop in enumerate(stops):
                self.trips_at_stop.setdefault(stop.stop_id, []).append((trip_id, index))

    def runs_on(self, service_id: str, day: date) -> bool:
        if (service_id, day) in self.exceptions:
            return self.exceptions[service_id, day]
        service = self.services.get(service_id)
        return service is not None and service.first_day <= day <= service.last_day and service.weekdays[day.weekday()]


class GtfsSource:
    def __init__(self, *, operator: str, feed: GtfsFeed, pricer: Pricer, city_stops: dict[str, list[str]]):
        self.name = f"{operator}-gtfs"
        self.feed, self.pricer = feed, pricer
        ids_by_name: dict[str, set[str]] = {}
        for stop_id, (stop_name, _) in feed.stops.items():
            ids_by_name.setdefault(stop_name, set()).add(stop_id)
        missing = sorted(name for names in city_stops.values() for name in names if name not in ids_by_name)
        if missing:
            raise ValueError(f"{operator}: stops listed in city_stops are not in the feed: {missing}")
        self.city_stop_ids = {
            city: {stop_id for name in names for stop_id in ids_by_name[name]}
            for city, names in city_stops.items()
        }

    async def search(self, leg: Leg, party_size: int) -> list[Offer]:
        if not self.feed.first_day <= leg.travel_date <= self.feed.last_day:
            raise OutsideCoverageError(self.name, self.feed.first_day, self.feed.last_day)
        destination_ids = self.city_stop_ids.get(leg.destination.canonical_key, set())
        retrieved_at = datetime.now(UTC)
        offers = []
        for origin_id in self.city_stop_ids.get(leg.origin.canonical_key, set()):
            for trip_id, index in self.feed.trips_at_stop.get(origin_id, ()):
                segment = self._segment(leg, trip_id, index, destination_ids)
                if segment is not None:
                    offers.append(Offer(
                        segments=(segment,), price=self.pricer.price((segment,), party_size),
                        source=f"{self.name}+{self.pricer.name}", retrieved_at=retrieved_at,
                    ))
        return sorted(offers, key=lambda offer: (offer.departure_at, offer.arrival_at, offer.origin.name))

    def _segment(self, leg: Leg, trip_id: str, index: int, destination_ids: set[str]) -> Segment | None:
        stops = self.feed.stop_times[trip_id]
        boarding = stops[index]
        alighting = next((stop for stop in stops[index + 1:] if stop.stop_id in destination_ids and stop.allows_drop_off), None)
        if not boarding.allows_pickup or alighting is None:
            return None
        route_id, service_id = self.feed.trips[trip_id]
        mode, line = self.feed.routes[route_id]
        origin_name, origin_zone = self.feed.stops[boarding.stop_id]
        destination_name, destination_zone = self.feed.stops[alighting.stop_id]
        for service_day in (leg.travel_date, leg.travel_date - timedelta(days=1)):
            departure_at = _at(service_day, boarding.departure_seconds, origin_zone)
            if departure_at.date() == leg.travel_date and self.feed.runs_on(service_id, service_day):
                return Segment(
                    mode=mode, line=line, departure_at=departure_at,
                    arrival_at=_at(service_day, alighting.arrival_seconds, destination_zone),
                    origin=Stop(name=origin_name, destination=leg.origin, code=boarding.stop_id),
                    destination=Stop(name=destination_name, destination=leg.destination, code=alighting.stop_id),
                )
        return None


def _at(service_day: date, seconds: int, zone: ZoneInfo) -> datetime:
    return datetime.combine(service_day, time(), zone) + timedelta(seconds=seconds)


def gtfs_sources(root: Path, pricer: Pricer) -> list[GtfsSource]:
    city_stops = json.loads(CITY_STOPS_PATH.read_text(encoding="utf-8"))
    return [
        GtfsSource(operator=operator, feed=GtfsFeed(root / operator), pricer=pricer, city_stops=cities)
        for operator, cities in city_stops.items()
        if (root / operator).is_dir()
    ]
