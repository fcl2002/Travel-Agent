from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from tools import tools, tool_node
import httpx

load_dotenv()

model = ChatGroq(model="openai/gpt-oss-20b")
model_with_tools = model.bind_tools(tools)

memory = MemorySaver()

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

graph = builder.compile(checkpointer=memory)

config = {
    "configurable": {
        "thread_id": "user-1"
    }
}

while True:
    user_input = input("\nYou: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    result = graph.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": user_input
                }
            ]
        },
        config=config
    )

    response = result["messages"][-1]

    print("\nAgent: ")
    print(response.content)
