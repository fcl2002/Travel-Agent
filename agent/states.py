from typing import TypeDict, List

class TravelState(TypeDict):
    origin: str
    destination: str
    budget: float
    days: int
    itinerary: str
    interests: List[str]