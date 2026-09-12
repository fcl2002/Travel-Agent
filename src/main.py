from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv
from tools import get_weather
import httpx

load_dotenv()

model = ChatMistralAI(model="voxtral-small-2507")

tools = [get_weather]
model_with_tools = model.bind_tools(tools)

def travel_agent(state: MessagesState):
    try: 
        response = model_with_tools.invoke(state["messages"])

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
                "content": "What's the weather in Amsterdam?"
            }
        ]
    }
)

print(result["messages"][-1])
