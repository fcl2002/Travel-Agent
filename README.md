# Travel Agent

This project was created with the goal of deepening my knowledge of **AI agents** through the development of a real-world application. The idea is to address a common problem faced by many people: planning a trip can require a lot of time, knowledge, and sometimes money for specialized services.

The goal is to build an agent that helps any user create a personalized travel itinerary based on their **interests, destination, dates, budget, and preferences**. The user should be able to interact with the agent naturally, describe the kind of trip they want, and receive useful and personalized recommendations.

> **Status:** This project is currently under development. Suggestions, ideas, and contributions are very welcome. If you have any ideas for improving or expanding the project, feel free to contact me:
>
> - Email: `fcostalasmar@examplgmail.com`
> - LinkedIn: `https://www.linkedin.com/in/fernando-lasmar`

## First Prototype

The first prototype will focus on validating the core architecture of the agent and its ability to use external data to support travel planning.

In this first version, the system should:

- Allow users to interact with the agent through a command-line interface (CLI).
- Maintain conversation context across multiple messages.
- Use **LangGraph** to manage the agent workflow and state.
- Use an LLM through the **Groq API**.
- Allow the model to use external tools through tool calling.
- Integrate at least two real external data sources, such as weather information and points of interest.
- Identify important trip information such as destination, dates, interests, and budget.
- Generate an initial personalized travel itinerary.

From this prototype, the project will gradually evolve to include more structured itinerary planning, budget validation, transportation and accommodation data, persistent storage, a backend API, and eventually a web interface.


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