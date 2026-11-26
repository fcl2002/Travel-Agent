"""Contract every offer source implements, whatever its data format or API."""

from datetime import date
from typing import Protocol

from agent.domain.search import Leg, Money, Segment, Offer


class OutsideCoverageError(Exception):
    def __init__(self, source: str, first_day: date, last_day: date):
        super().__init__(f"{source} only publishes trips from {first_day} to {last_day}")
        self.source, self.first_day, self.last_day = source, first_day, last_day


class OfferSource(Protocol):
    name: str

    async def search(self, leg: Leg, party_size: int) -> list[Offer]:
        """Direct offers for the leg, priced for the whole party.

        Raises OutsideCoverageError when the travel date is outside the published data,
        so callers can tell "no trips" apart from "not published yet".
        """
        ...


class Pricer(Protocol):
    name: str

    def price(self, segments: tuple[Segment, ...], party_size: int) -> Money: ...


class FixturePricer:
    """Fictional, deterministic prices until a real price source is connected."""

    name = "fixture"
    base_minor = 299
    per_minute_minor = 4

    def price(self, segments: tuple[Segment, ...], party_size: int) -> Money:
        minutes = sum(int(segment.duration.total_seconds() // 60) for segment in segments)
        return Money((self.base_minor + minutes * self.per_minute_minor) * party_size, "EUR")
