from agent_framework import AgentExecutor, ChatAgent
from agent_framework.azure import AzureOpenAIChatClient

from tools.file_search import file_search_tool

_AGENT_INSTRUCTIONS = """
You are a Joint Surgery Information Agent. Answer questions strictly about total joint surgery.

Use the joint_surgery_guide_search tool to retrieve supporting excerpts from the local "Your Guide to Total Joint Replacement" manual before responding. Base every answer only on the tool output and clearly synthesize the retrieved guidance. Always decline questions that fall outside joint surgery topics, and if the tool returns no relevant passages say that the information is not available in the guide. Do not offer personal medical advice beyond the content you retrieve.
""".strip()


def create_agent_executor(client: AzureOpenAIChatClient) -> AgentExecutor:
    guide_tool = file_search_tool()
    agent = AgentExecutor(
        client.create_agent(
            instructions=_AGENT_INSTRUCTIONS,
            tools=[guide_tool],
        ),
        id="joint_surgery_info_agent_executor",
    )
    return agent


def create_agent(client: AzureOpenAIChatClient):
    guide_tool = file_search_tool()
    agent = ChatAgent(
        chat_client=client,
        tools=[guide_tool],
        instructions=_AGENT_INSTRUCTIONS,
        name="JointSurgeryInfoAgent",
    )

    return agent
