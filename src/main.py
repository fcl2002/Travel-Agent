from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import tools_condition
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from tools import tools, tool_node
from datetime import date
import httpx

load_dotenv()

model = ChatGroq(model="openai/gpt-oss-20b")
model_with_tools = model.bind_tools(tools)

memory = MemorySaver()

def travel_agent(state: MessagesState):
    try: 
        today = date.today()

        system_prompt = f"""
        You are a travel planning assistant.

        Today's date is {today.isoformat()}.

        Date interpretation rules:
        - Resolve relative dates such as "today", "tomorrow", "next Friday",
        and "next weekend" relative to today's date.
        - If the user provides a date without a year, assume {today.year}.
        - Never invent another year.
        - If the resulting date would be in the past, ask the user to clarify.
        - Always provide dates to tools in YYYY-MM-DD format.
        - If a date cannot be determined confidently, ask the user for clarification.
        """

        messages = [
            SystemMessage(content=system_prompt),
            *state["messages"]
        ]
        response = model_with_tools.invoke(messages)

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
