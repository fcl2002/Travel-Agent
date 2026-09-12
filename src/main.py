# from typing import TypeDict, List
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv
import httpx

# class TravelState(TypeDict):
#     origin: str
#     destination: str
#     budget: float
#     days: int
#     itinerary: str
#     interests: List[str]

load_dotenv()
model = ChatMistralAI(model="voxtral-small-2507")

def travel_agent(state: MessagesState):
    try: 
        response = model.invoke(state["messages"])

        return {
            "messages": [response]
        }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Mistral rate limit exceeded. Please try again shortly"
                    }
                ]
            }
        raise

builder = StateGraph(MessagesState)

builder.add_node("travel_agent", travel_agent)
builder.add_edge(START, "travel_agent")
builder.add_edge("travel_agent", END)

graph = builder.compile()

result = graph.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "I want to travel from Paris to Amsterdam for 3 days."
            }
        ]
    }
)

print(result["messages"][-1].content)
