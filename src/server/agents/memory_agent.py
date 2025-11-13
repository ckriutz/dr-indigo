from agent_framework import AgentExecutor, ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from pydantic import BaseModel

# Shared instructions used by both the ChatAgent and AgentExecutor
MEMORY_INSTRUCTIONS = """
Look though the user's previous messages and provide a concise summary of their key health information, concerns, and context.
Focus on relevant medical history, symptoms, and any important details that would help in future interactions. Keep the summary brief and to the point.
"""

class MemoryResult(BaseModel):
    memory_summary: str
    # Human readable rationale from the detector
    reason: str

def create_memory_agent(client: AzureOpenAIChatClient,chat_message_store_factory=None) -> ChatAgent:
    """
    Lightweight factory returning the raw ChatAgent (similar to create_care_navigator_agent).
    This allows calling `agent.run(prompt)` directly without wrapping in an AgentExecutor.
    """
    print("🏗️  Creating memory chat agent")
    return ChatAgent(
        chat_client=client,
        name="MemoryAgent",
        instructions=MEMORY_INSTRUCTIONS,
        response_format=MemoryResult
    )

def create_memory_executor_agent(client: AzureOpenAIChatClient) -> AgentExecutor:
    """
    Standard executor agent.
    """
    print("🏗️  Creating memory agent")

    agent = ChatAgent(
        chat_client=client,
        name="MemoryAgent",
        instructions=MEMORY_INSTRUCTIONS,
        response_format=MemoryResult,
    )

    return AgentExecutor(agent, id="memory_agent_executor")
