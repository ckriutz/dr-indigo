import os
from typing import Any, Never
import dotenv
from agent_framework.azure import AzureOpenAIChatClient
from agents.medical_triage_agent import MedicalTriageResult
from agents.medical_triage_agent import (
    create_executor_agent as create_triage_executor_agent,
)
from agents.joint_surgery_info_agent import (
    create_agent_executor as create_joint_surgery_executor_agent,
)

from agent_framework import (
    AgentExecutorResponse,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    executor,
)


# So this is just a simple handler that replies with emergency instructions.
# No LLM needed.
@executor(id="reply_emergency")
async def _handle_emergency(
    response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]
) -> None:
    # Downstream of the email assistant. Parse a validated EmailResponse and yield the workflow output.
    await ctx.yield_output("Yo, you should call 911 or go to the emergency room!")


# Lets make sure the json returned is valid, and route based on the boolean value.
def _condition_medical_emergency(message: Any) -> bool:
    # Defensive guard. If a non AgentExecutorResponse appears, let the edge pass to avoid dead ends.
    if not isinstance(message, AgentExecutorResponse):
        return True
    try:
        # Using model_validate_json ensures type safety and raises if the shape is wrong.
        detection = MedicalTriageResult.model_validate_json(
            message.agent_run_response.text
        )
        return detection.is_medical_emergency
    except Exception:
        # Fail closed on parse errors so we do not accidentally route to the wrong path.
        # Returning False prevents this edge from activating.
        return False


def create_workflow() -> Workflow:
    # Configuration
    dotenv.load_dotenv()
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")

    # Create agents
    med_triage_agent_executor = create_triage_executor_agent(AzureOpenAIChatClient(
        api_key=api_key,
        endpoint=endpoint,
        deployment_name="gpt-5-nano",
    ))
    # med_triage_agent = create_triage_agent(chat_client)
    joint_surgery_agent_executor_agent = create_joint_surgery_executor_agent(
        AzureOpenAIChatClient(
        api_key=api_key,
        endpoint=endpoint,
        deployment_name=deployment,
    )
    )

    return (
        WorkflowBuilder()
        .set_start_executor(med_triage_agent_executor)
        # Start by short circuiting medical emergencies.
        .add_edge(
            med_triage_agent_executor,
            _handle_emergency,
            condition=_condition_medical_emergency,
        )
        # For non-emergencies, forward to the joint surgery agent.
        .add_edge(
            med_triage_agent_executor,
            joint_surgery_agent_executor_agent,
            condition=lambda msg: not _condition_medical_emergency(msg),
        )
        .build()
    )
