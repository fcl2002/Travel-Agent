from typing import TypedDict, List

class TravelState(TypedDict):
    origin: str
    destination: str
    budget: float
    days: int
    itinerary: str
    interests: List[str]