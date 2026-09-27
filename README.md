# Travel Agent

This project was created with the goal of deepening my knowledge of **AI agents** through the development of a real-world application. The idea is to address a common problem faced by many people: planning a trip can require a lot of time, knowledge, and sometimes money for specialized services.

The goal is to build an agent that helps any user create a personalized travel itinerary based on their **interests, destination, dates, budget, and preferences**. The user should be able to interact with the agent naturally, describe the kind of trip they want, and receive useful and personalized recommendations.

> **Status:** This project is currently under development. Suggestions, ideas, and contributions are very welcome. If you have any ideas for improving or expanding the project, feel free to contact me:
>
> - Email: `fcostalasmar@gmail.com`
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