from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from agent.domain.search import (
    Destination, Money, Offer, PlannedStop, Segment, Stop, TransportMode, TripPlan, TripRequest,
)

PARIS_TZ = ZoneInfo("Europe/Paris")
PARIS = Destination(name="Paris", canonical_key="paris")
LYON = Destination(name="Lyon", canonical_key="lyon")
NICE = Destination(name="Nice", canonical_key="nice")
PARIS_GARE_DE_LYON = Stop(name="Paris Gare de Lyon", destination=PARIS)
LYON_PART_DIEU = Stop(name="Lyon Part-Dieu", destination=LYON)
LYON_PERRACHE = Stop(name="Lyon Perrache", destination=LYON)
NICE_VILLE = Stop(name="Nice Ville", destination=NICE)


def at(day: int, hour: int, minute: int = 0, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=PARIS_TZ)


def train(origin: Stop, destination: Stop, departure: datetime, hours: float) -> Segment:
    return Segment(mode=TransportMode.TRAIN, origin=origin, destination=destination,
                   departure_at=departure, arrival_at=departure + timedelta(hours=hours))


def offer(*segments: Segment, euros: int, seats: int | None = None) -> Offer:
    return Offer(segments=segments, price=Money(euros * 100, "EUR"), source="test",
                 retrieved_at=at(1, 9), remaining_seats=seats)


def paris_nice_weekend(**overrides) -> TripRequest:
    fields = {"origin": PARIS, "stops": (PlannedStop(destination=NICE, arrival_date=date(2026, 10, 17),
                                                     departure_date=date(2026, 10, 18)),),
              "budget": Money(10000, "EUR")}
    return TripRequest(**{**fields, **overrides})


def test_money_adds_and_compares_only_within_one_currency():
    assert Money(3900, "EUR") + Money(4500, "EUR") == Money(8400, "EUR")
    assert Money(8400, "EUR") <= Money(10000, "EUR")
    with pytest.raises(ValueError):
        Money(100, "EUR") + Money(100, "USD")
    for amount, currency in ((-1, "EUR"), (100, "eur"), (100, "EURO"), (100, "E1R")):
        with pytest.raises(ValueError):
            Money(amount, currency)


def test_segment_requires_aware_times_in_order_between_different_stops():
    assert train(PARIS_GARE_DE_LYON, NICE_VILLE, at(17, 7), 5.5).duration == timedelta(hours=5, minutes=30)
    naive = datetime(2026, 10, 17, 7)
    for departure, arrival, destination in ((naive, naive + timedelta(hours=1), NICE_VILLE),
                                            (at(17, 9), at(17, 8), NICE_VILLE),
                                            (at(17, 7), at(17, 8), PARIS_GARE_DE_LYON)):
        with pytest.raises(ValueError):
            Segment(mode=TransportMode.TRAIN, origin=PARIS_GARE_DE_LYON, destination=destination,
                    departure_at=departure, arrival_at=arrival)


def test_offer_with_a_connection_derives_its_journey():
    journey = offer(train(PARIS_GARE_DE_LYON, LYON_PART_DIEU, at(17, 7), 2),
                    train(LYON_PERRACHE, NICE_VILLE, at(17, 9, 40), 4.5), euros=39)
    assert (journey.origin, journey.destination) == (PARIS_GARE_DE_LYON, NICE_VILLE)
    assert journey.transfers == 1
    assert journey.connection_times == (timedelta(minutes=40),)
    assert journey.duration == timedelta(hours=7, minutes=10)


def test_offer_rejects_broken_journeys():
    with pytest.raises(ValueError):
        offer(euros=39)
    with pytest.raises(ValueError):
        offer(train(PARIS_GARE_DE_LYON, LYON_PART_DIEU, at(17, 7), 2),
              train(NICE_VILLE, PARIS_GARE_DE_LYON, at(17, 10), 5), euros=39)
    with pytest.raises(ValueError):
        offer(train(PARIS_GARE_DE_LYON, LYON_PART_DIEU, at(17, 7), 2),
              train(LYON_PART_DIEU, NICE_VILLE, at(17, 8, 30), 4), euros=39)


def test_request_turns_stops_into_dated_legs():
    assert [(leg.origin, leg.destination, leg.travel_date) for leg in paris_nice_weekend().legs] == [
        (PARIS, NICE, date(2026, 10, 17)), (NICE, PARIS, date(2026, 10, 18)),
    ]
    one_way = paris_nice_weekend(returns_to_origin=False)
    assert len(one_way.legs) == 1
    multi_stop = paris_nice_weekend(stops=(
        PlannedStop(destination=LYON, arrival_date=date(2026, 10, 17), departure_date=date(2026, 10, 18)),
        PlannedStop(destination=NICE, arrival_date=date(2026, 10, 18), departure_date=date(2026, 10, 20)),
    ))
    assert [(leg.origin, leg.destination) for leg in multi_stop.legs] == [(PARIS, LYON), (LYON, NICE), (NICE, PARIS)]


def test_request_rejects_impossible_plans():
    late_departure = PlannedStop(destination=LYON, arrival_date=date(2026, 10, 18),
                                 departure_date=date(2026, 10, 19))
    early_arrival = PlannedStop(destination=NICE, arrival_date=date(2026, 10, 17),
                                departure_date=date(2026, 10, 20))
    for overrides in ({"stops": ()}, {"party_size": 0}, {"max_connections": -1},
                      {"stops": (late_departure, early_arrival)}):
        with pytest.raises(ValueError):
            paris_nice_weekend(**overrides)
    with pytest.raises(ValueError):
        PlannedStop(destination=NICE, arrival_date=date(2026, 10, 18), departure_date=date(2026, 10, 17))


def test_round_trip_plan_totals_and_checks_the_budget():
    outbound = offer(train(PARIS_GARE_DE_LYON, NICE_VILLE, at(17, 7), 5.5), euros=39)
    inbound = offer(train(NICE_VILLE, PARIS_GARE_DE_LYON, at(18, 17), 5.5), euros=45)
    plan = TripPlan(request=paris_nice_weekend(), offers=(outbound, inbound))
    assert plan.total_price == Money(8400, "EUR")
    assert plan.within_budget
    expensive = offer(train(NICE_VILLE, PARIS_GARE_DE_LYON, at(18, 17), 5.5), euros=70)
    assert not TripPlan(request=paris_nice_weekend(), offers=(outbound, expensive)).within_budget
    assert TripPlan(request=paris_nice_weekend(budget=None), offers=(outbound, expensive)).within_budget
    with pytest.raises(ValueError):
        TripPlan(request=paris_nice_weekend(budget=Money(10000, "USD")), offers=(outbound, inbound)).within_budget


def test_same_day_round_trip_is_a_valid_plan():
    request = paris_nice_weekend(stops=(PlannedStop(destination=NICE, arrival_date=date(2026, 10, 17),
                                                    departure_date=date(2026, 10, 17)),))
    plan = TripPlan(request=request, offers=(
        offer(train(PARIS_GARE_DE_LYON, NICE_VILLE, at(17, 6), 5.5), euros=39),
        offer(train(NICE_VILLE, PARIS_GARE_DE_LYON, at(17, 18), 5.5), euros=45),
    ))
    assert plan.total_price == Money(8400, "EUR")


def test_plan_rejects_offers_that_do_not_fit_the_request():
    outbound = offer(train(PARIS_GARE_DE_LYON, NICE_VILLE, at(17, 7), 5.5), euros=39)
    inbound = offer(train(NICE_VILLE, PARIS_GARE_DE_LYON, at(18, 17), 5.5), euros=45)
    with_connection = offer(train(NICE_VILLE, LYON_PART_DIEU, at(18, 9), 4),
                            train(LYON_PART_DIEU, PARIS_GARE_DE_LYON, at(18, 14), 2), euros=30)
    cases = (
        (paris_nice_weekend(), (outbound,)),
        (paris_nice_weekend(), (inbound, outbound)),
        (paris_nice_weekend(), (outbound, offer(train(NICE_VILLE, PARIS_GARE_DE_LYON, at(19, 17), 5.5), euros=45))),
        (paris_nice_weekend(max_connections=0), (outbound, with_connection)),
        (paris_nice_weekend(party_size=3), (outbound, offer(train(NICE_VILLE, PARIS_GARE_DE_LYON, at(18, 17), 5.5),
                                                            euros=45, seats=2))),
    )
    for request, offers in cases:
        with pytest.raises(ValueError):
            TripPlan(request=request, offers=offers)
