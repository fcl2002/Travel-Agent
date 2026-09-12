from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import tools_condition
from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv
from tools import tools, tool_node
import httpx

load_dotenv()

model = ChatMistralAI(model="voxtral-small-2507")
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
builder.add_node("tools", tool_node)

builder.add_edge(START, "travel_agent")
builder.add_conditional_edges("travel_agent", tools_condition)
builder.add_edge("tools", "travel_agent")

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

for message in result["messages"]:
    print(type(message).__name__)
    print(message)
    print("---")
