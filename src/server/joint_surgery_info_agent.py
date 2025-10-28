from agent_framework import AgentExecutor
from agent_framework.azure import AzureOpenAIChatClient
from search_tool import create_search_tool

# This agent will answer questions about joint surgery. It will not answer any other questions.
# All the answers it gets will be answered by data only from the GuideToTotalJointSurgery_ENG_V2.pdf
# This file is included here, but will need to be changed next to be from blob storage.
# After that, even better if it came from Azure AI Search.
# If we move to Azure AI Search, we can remove the PyPDF2==3.0.1 requirement from requirements.txt

def create_executor_agent(client: AzureOpenAIChatClient) -> AgentExecutor:
    # Create the search tool (no client needed)
    search_tool = create_search_tool()
    
    agent = AgentExecutor(
        client.create_agent(
            instructions=f"""
            You are a Joint Surgery Information Agent. Your role is to answer questions about total joint surgery 
            using ONLY information found from the search tool.

            IMPORTANT RULES:
            - Answer questions ONLY about joint surgery topics.
            - Base your answers ONLY on the information from the search tool.
            - If a question is not related to joint surgery, politely decline and explain that you only answer questions about joint surgery.
            - If the answer is not found in search, say so honestly.
            - Provide clear, accurate, and helpful responses based on the results from the search tool.
            - Do not make up information or provide medical advice beyond what's in the search tool.
            """,
            tools=[search_tool]
        ),
        # Emit the agent run response as a workflow output so callers can inspect
        # the assistant's answer directly from WorkflowRunResult.get_outputs().
        output_response=True,
        id="joint_surgery_info_agent_executor",
    )
    return agent