# Travel Agent

This project was created with the goal of deepening my knowledge of **AI agents** through the development of a real-world application. The idea is to address a common problem faced by many people: planning a trip can require a lot of time, knowledge, and sometimes money for specialized services.

The goal is to build an agent that helps any user create a personalized travel itinerary based on their **interests, destination, dates, budget, and preferences**. The user should be able to interact with the agent naturally, describe the kind of trip they want, and receive useful and personalized recommendations.

> **Status:** This project is currently under development. Suggestions, ideas, and contributions are very welcome. If you have any ideas for improving or expanding the project, feel free to contact me:
>
> - Email: `fcostalasmar@gmail.com`
> - LinkedIn: `https://www.linkedin.com/in/fernando-lasmar`

## First Prototype

The first prototype focuses on validating the core architecture of the agent and its ability to use external data to support travel planning.

The current version already supports:

- Interaction through a command-line interface (CLI).
- Multi-turn conversations with conversation memory.
- **LangGraph** for agent workflow, state management, and conditional routing.
- **Groq API** as the LLM provider.
- Tool calling through LangGraph's `ToolNode`.
- A weather tool using the **Open-Meteo API**.
- City geocoding to convert location names into coordinates before requesting weather data.
- Weather forecast validation for dates outside the supported forecast range.
- System-level instructions to help the model interpret dates consistently and avoid invalid tool calls.

The next steps are to add more real travel data sources, especially points of interest, structure trip information such as destination, dates, interests, and budget, and generate a complete personalized itinerary.