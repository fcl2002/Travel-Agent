# Domain and scope of the ontology

## What is the domain that the ontology will cover?

Round trips in France using public transport, such as buses, trains or flights.

## For what we are going to use the ontology?

We're going to use the ontology to help us identify the cheapest way to travel by public transport (bus, train or flight) for a round-trip in France.

## For what types of questions the information in the ontology should provide answers?

* If possible, how to reach a destination in France by public transport, considering buses, trains, and flights ?
* What is the cheapest way to travel between two locations in France on a specific date ?
* Is it worth stopping off at a town along the way ?
* Is it worth combining different transportation modes of transport and transfers to reach the destination ?
* Which offers the best trade-off between time and money ?
* Are there cheaper transport alternatives if the user is flexible about departure dates or times within a specified period ?
* Is the available itinerary suitable for the user's requirements, such as budget, total travel time and luggage ?

## Who will use and maintain the ontology?

The users are students and anyone who wants to discover France and its culture without spending too much money. The ontology will be maintained by [Fernando Lasmar](https://www.linkedin.com/in/fernando-lasmar/) and [Vivian Fragoso](https://www.linkedin.com/in/vivian-fragoso/), two Computer Engineering students who love to travel.

## Use Cases 

### 1st Case
> ### Finding the cheapest round-trip option for fixed dates
> I'd like to travel to Nice for one night on 17 and 18 October 2026, and then return to Paris. I have €100 to spend on transport. What is the cheapest way to make the most of my weekend there?

### 2nd Case

> ### Finding the cheapest destination within a date range
> Vivian wants to travel between 23 and 31 October 2026. She'll depart from Paris and has the following destinations in mind: Bordeaux, Lyon, Marseille, Nice, and Toulouse. She would like to know which of these destinations is cheapest destination for these specific dates. She wants to stay for at least 3 days (2 nights) and then return to Paris.

### 3rd Case

> ### Finding the cheapest same-day round-trip itinerary
> A group of students wants to travel to Mont Saint-Michel on specific weekend in November. They don't want to spend the night there. They would like to depart from Paris in the morning and return after 5pm, to make the most of their day. They are looking for the cheapest transport option with an early departure time, what would you recommend ?

## Ontology Class Hierarchy

```text
owl:Thing
│
├── Itinerary
├── Trip Plan
│   ├── One Way Trip
│   └── Round Trip Plan
└── Trip Segment
```

## References

> Note: Our ontology is based on the open-source [Trip Planning Ontology][trip-ontology], developed by houssamallali. 
> 
> We are progressively adapting and extending its classes, properties, and relationships to meet our project's requirements, initially focusing on affordable domestic
> travel within France.

[trip-ontology]: https://github.com/houssamallali/TripPlanningOntology/blob/main/README.md
[GEOFLA]: https://earthportal.eu/ontologies/GEOFLA
