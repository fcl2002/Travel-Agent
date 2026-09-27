# Travel Agent Roadmap


## Goal
Build and deploy a real travel-planning assistant that can understand a trip request, use live data, create an itinerary, check constraints such as budget, remember the conversation, and let the user refine the plan.

## Roadmap

1. Conversation Protype

- [ ] CLI chat interface; 
- [ ] LangGraph tool calling and conditional routing;
- [ ] Add conversatin memory with the checkpointer.

*Acceptance criteria:* The user can have a multi-turn conversation and the agent remember previous messages.

2. Real Traver Data

- [ ] Add a real weather tooal (get_weather(city, date)); 
- [ ] Add a places/attractions tool (get_events(city, date, interests[]));
- [ ] Handle API errors and unavailable data.

*Acceptance criteria*: The agent can answer travel questions using at least two external data sources.

3. Structured Trip State, tracking fields such as:

- [ ] Origin; 
- [ ] Destination; 
- [ ] Dates; 
- [ ] Budget; 
- [ ] Number of travelers; 
- [ ] Interests.

*Acceptance criteria*: The graph can reliably extract and reuse the main trip requirements.

4. Itinerary Planning:

- [ ] Select relevant activities; 
- [ ] Organize them by day; 
- [ ] Consider opening hours, weather and travel time; 
- [ ] Allow the user to request changes.

*Acceptance criteria*: The CLI can produce produce and revise a complete itinerary.

5. Budget Validation:

- [ ] Estimate transport, accomodation, food, and activites; 
- [ ] Compare estimated cost with the user's budget; 
- [ ] Revise the plan when it exceeds the budget.

*Acceptance criteria*: The graph can follow a plan -> validate -> revise loop.

6. Persistent Storage:

- [ ] Add PostreSQL; 
- [ ] Store trips, messages, preferences, and itineraries; 
- [ ] Allow aprevious trip to be resumed.

*Acceptance criteria*: Restarting the application does not erase saved trips.

7. Backend API:

- [ ] Add FastAPI; 
- [ ] Expose endpoints for trips, messages, and itineraries; 
- [ ] Connect FastAPI to LangGraph and the database.

*Acceptance criteria*: The agent can be used through HTTP requests instead of only the CLI.

8. Web Interface:

- [ ] Create a trip form; 
- [ ] Add chat; 
- [ ] Display the itinerary;
- [ ] Display estimated costs and budget remaining.

9. Deployment:

- [ ] Frontend: Vercel; 
- [ ] Backend: Render, Railway, or Fly.io.

*Acceptance criteria*: The application is publicly accessible and can plan a real trip end-to-end.