"""Search-side model: transport offers found for a trip request, before anything is booked."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum


class TransportMode(StrEnum):
    BUS = "bus"
    TRAIN = "train"
    FLIGHT = "flight"
    OTHER = "other"


@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if self.amount_minor < 0:
            raise ValueError("Money cannot be negative")
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError("Currency must be an ISO 4217 code such as EUR")

    def __add__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __le__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount_minor <= other.amount_minor

    def _require_same_currency(self, other: "Money") -> None:
        if other.currency != self.currency:
            raise ValueError(f"Cannot combine {self.currency} with {other.currency}")


@dataclass(frozen=True, kw_only=True)
class Destination:
    name: str
    canonical_key: str
    country_code: str = "FR"


@dataclass(frozen=True, kw_only=True)
class Stop:
    name: str
    destination: Destination
    code: str | None = None


@dataclass(frozen=True, kw_only=True)
class Segment:
    mode: TransportMode
    origin: Stop
    destination: Stop
    departure_at: datetime
    arrival_at: datetime
    line: str | None = None

    def __post_init__(self) -> None:
        if self.departure_at.tzinfo is None or self.arrival_at.tzinfo is None:
            raise ValueError("Segment times must be timezone-aware")
        if self.arrival_at <= self.departure_at:
            raise ValueError("A segment must arrive after it departs")
        if self.origin == self.destination:
            raise ValueError("A segment must go between two different stops")

    @property
    def duration(self) -> timedelta:
        return self.arrival_at - self.departure_at


@dataclass(frozen=True, kw_only=True)
class Offer:
    segments: tuple[Segment, ...]
    price: Money
    source: str
    retrieved_at: datetime
    remaining_seats: int | None = None

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("An offer needs at least one segment")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if self.remaining_seats is not None and self.remaining_seats < 0:
            raise ValueError("remaining_seats cannot be negative")
        for previous, following in zip(self.segments, self.segments[1:]):
            if following.origin.destination != previous.destination.destination:
                raise ValueError("Each segment must start in the city where the previous one ends")
            if following.departure_at <= previous.arrival_at:
                raise ValueError("Each segment must depart after the previous one arrives")

    @property
    def origin(self) -> Stop:
        return self.segments[0].origin

    @property
    def destination(self) -> Stop:
        return self.segments[-1].destination

    @property
    def departure_at(self) -> datetime:
        return self.segments[0].departure_at

    @property
    def arrival_at(self) -> datetime:
        return self.segments[-1].arrival_at

    @property
    def duration(self) -> timedelta:
        return self.arrival_at - self.departure_at

    @property
    def transfers(self) -> int:
        return len(self.segments) - 1

    @property
    def connection_times(self) -> tuple[timedelta, ...]:
        return tuple(
            following.departure_at - previous.arrival_at
            for previous, following in zip(self.segments, self.segments[1:])
        )


@dataclass(frozen=True, kw_only=True)
class PlannedStop:
    destination: Destination
    arrival_date: date
    departure_date: date

    def __post_init__(self) -> None:
        if self.departure_date < self.arrival_date:
            raise ValueError("A stop cannot be left before it is reached")


@dataclass(frozen=True)
class Leg:
    origin: Destination
    destination: Destination
    travel_date: date


@dataclass(frozen=True, kw_only=True)
class TripRequest:
    origin: Destination
    stops: tuple[PlannedStop, ...]
    returns_to_origin: bool = True
    party_size: int = 1
    budget: Money | None = None
    max_connections: int | None = None

    def __post_init__(self) -> None:
        if not self.stops:
            raise ValueError("A trip request needs at least one stop")
        if self.party_size < 1:
            raise ValueError("party_size must be at least 1")
        if self.max_connections is not None and self.max_connections < 0:
            raise ValueError("max_connections cannot be negative")
        for previous, following in zip(self.stops, self.stops[1:]):
            if following.arrival_date < previous.departure_date:
                raise ValueError("Stops must be in chronological order")

    @property
    def legs(self) -> tuple[Leg, ...]:
        places = [self.origin, *(stop.destination for stop in self.stops)]
        legs = [
            Leg(places[index], stop.destination, stop.arrival_date)
            for index, stop in enumerate(self.stops)
        ]
        if self.returns_to_origin:
            legs.append(Leg(self.stops[-1].destination, self.origin, self.stops[-1].departure_date))
        return tuple(legs)


@dataclass(frozen=True, kw_only=True)
class TripPlan:
    request: TripRequest
    offers: tuple[Offer, ...]

    def __post_init__(self) -> None:
        legs = self.request.legs
        if len(self.offers) != len(legs):
            raise ValueError(f"Expected one offer per leg ({len(legs)}), got {len(self.offers)}")
        for leg, offer in zip(legs, self.offers):
            if (offer.origin.destination, offer.destination.destination) != (leg.origin, leg.destination):
                raise ValueError(f"Offer does not travel {leg.origin.name} -> {leg.destination.name}")
            if offer.departure_at.date() != leg.travel_date:
                raise ValueError(f"Offer for {leg.destination.name} does not depart on {leg.travel_date}")
            if self.request.max_connections is not None and offer.transfers > self.request.max_connections:
                raise ValueError("Offer exceeds the maximum number of connections")
            if offer.remaining_seats is not None and offer.remaining_seats < self.request.party_size:
                raise ValueError("Offer does not have enough seats for the party")
        for previous, following in zip(self.offers, self.offers[1:]):
            if following.departure_at <= previous.arrival_at:
                raise ValueError("Each leg must depart after the previous one arrives")

    @property
    def total_price(self) -> Money:
        total = self.offers[0].price
        for offer in self.offers[1:]:
            total = total + offer.price
        return total

    @property
    def within_budget(self) -> bool:
        return self.request.budget is None or self.total_price <= self.request.budget
