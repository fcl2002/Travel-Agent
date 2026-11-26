import asyncio
import zipfile
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from agent.domain.search import Destination, Leg, Money, TransportMode
from agent.sources.base import FixturePricer, OfferSource, OutsideCoverageError
from agent.sources.download_gtfs import extract_feed
from agent.sources.gtfs import GtfsFeed, GtfsSource

TINY_FEED = Path(__file__).parent / "fixtures" / "gtfs" / "tiny"
PARIS_TZ = ZoneInfo("Europe/Paris")
PARIS = Destination(name="Paris", canonical_key="paris")
LYON = Destination(name="Lyon", canonical_key="lyon")
NICE = Destination(name="Nice", canonical_key="nice")
CITY_STOPS = {"paris": ["Paris Bercy", "Paris Orly"], "lyon": ["Lyon Perrache"], "nice": ["Nice Vauban"]}
SATURDAY = date(2026, 12, 12)


def tiny_source() -> GtfsSource:
    return GtfsSource(operator="tiny", feed=GtfsFeed(TINY_FEED), pricer=FixturePricer(), city_stops=CITY_STOPS)


def search(source: OfferSource, leg: Leg, party_size: int = 1):
    return asyncio.run(source.search(leg, party_size))


def departures(offers) -> list[tuple[datetime, str]]:
    return [(offer.departure_at, offer.origin.name) for offer in offers]


CONTRACT_CASES = [pytest.param(tiny_source, Leg(PARIS, NICE, SATURDAY), date(2027, 1, 5), id="gtfs")]


@pytest.mark.parametrize(("make_source", "leg", "outside_day"), CONTRACT_CASES)
def test_source_contract(make_source, leg, outside_day):
    source = make_source()
    offers = search(source, leg, party_size=2)
    assert offers
    for offer in offers:
        assert (offer.origin.destination, offer.destination.destination) == (leg.origin, leg.destination)
        assert offer.departure_at.date() == leg.travel_date
        assert offer.departure_at.tzinfo is not None and offer.arrival_at.tzinfo is not None
        assert offer.source.startswith(source.name)
    again = search(source, leg, party_size=2)
    assert [replace(offer, retrieved_at=offers[0].retrieved_at) for offer in again] == offers
    with pytest.raises(OutsideCoverageError):
        search(source, replace(leg, travel_date=outside_day))


def test_gtfs_finds_direct_trips_departing_on_the_travel_date():
    offers = search(tiny_source(), Leg(PARIS, NICE, SATURDAY))
    assert departures(offers) == [
        (datetime(2026, 12, 12, 0, 30, tzinfo=PARIS_TZ), "Paris Bercy"),
        (datetime(2026, 12, 12, 8, 0, tzinfo=PARIS_TZ), "Paris Orly"),
        (datetime(2026, 12, 12, 22, 0, tzinfo=PARIS_TZ), "Paris Bercy"),
    ]
    overnight = offers[-1]
    assert overnight.arrival_at == datetime(2026, 12, 13, 7, 40, tzinfo=PARIS_TZ)
    assert overnight.destination.name == "Nice Vauban" and overnight.segments[0].line == "N1"


def test_gtfs_applies_calendar_exceptions():
    christmas = search(tiny_source(), Leg(PARIS, NICE, date(2026, 12, 25)))
    assert departures(christmas) == [(datetime(2026, 12, 25, 0, 30, tzinfo=PARIS_TZ), "Paris Bercy")]
    added_wednesday = search(tiny_source(), Leg(PARIS, NICE, date(2026, 12, 23)))
    assert (datetime(2026, 12, 23, 8, 0, tzinfo=PARIS_TZ), "Paris Orly") in departures(added_wednesday)


def test_gtfs_maps_route_types_to_modes():
    offers = search(tiny_source(), Leg(PARIS, LYON, SATURDAY))
    assert {offer.segments[0].mode for offer in offers} == {TransportMode.TRAIN, TransportMode.BUS}


def test_gtfs_coverage_is_the_published_service_period():
    for day in (date(2026, 11, 30), date(2027, 1, 1)):
        with pytest.raises(OutsideCoverageError) as error:
            search(tiny_source(), Leg(PARIS, NICE, day))
        assert (error.value.first_day, error.value.last_day) == (date(2026, 12, 1), date(2026, 12, 31))


def test_gtfs_rejects_city_stops_missing_from_the_feed():
    with pytest.raises(ValueError, match="Paris Gare du Nord"):
        GtfsSource(operator="tiny", feed=GtfsFeed(TINY_FEED), pricer=FixturePricer(),
                   city_stops={"paris": ["Paris Bercy", "Paris Gare du Nord"]})


def test_fixture_pricer_prices_the_whole_party():
    offer = search(tiny_source(), Leg(PARIS, NICE, SATURDAY))[1]
    assert offer.price == Money(299 + 8 * 60 * 4, "EUR")
    assert search(tiny_source(), Leg(PARIS, NICE, SATURDAY), party_size=3)[1].price == Money(3 * offer.price.amount_minor, "EUR")


def test_extract_feed_skips_shapes_and_refuses_unsafe_entries(tmp_path):
    archive = tmp_path / "feed.zip"
    with zipfile.ZipFile(archive, "w") as feed:
        feed.writestr("stops.txt", "stop_id\n")
        feed.writestr("shapes.txt", "shape_id\n")
    assert extract_feed(archive, tmp_path / "out") == ["stops.txt"]
    assert not (tmp_path / "out" / "shapes.txt").exists()
    for name in ("../evil.txt", "nested/stops.txt", "run.py"):
        with zipfile.ZipFile(tmp_path / "bad.zip", "w") as feed:
            feed.writestr(name, "x")
        with pytest.raises(ValueError):
            extract_feed(tmp_path / "bad.zip", tmp_path / "bad")
