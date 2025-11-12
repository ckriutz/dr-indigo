from typing import Any, Never

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    executor,
)
from agent_framework.azure import AzureOpenAIChatClient

from agents.care_navigator_agent import create_care_navigator_executor
from agents.medical_triage_agent import (
    MedicalTriageResult,
    create_triage_executor_agent,
)
from settings import AUBREY_SETTINGS

_CLIENT_CACHE: dict[
    tuple[str | None, str | None, str | None], AzureOpenAIChatClient
] = {}


_TRIAGE_EXECUTOR_ID = "medical_triage_agent_executor"
_CARE_NAV_EXECUTOR_ID = "care_navigator_agent_executor"


def get_chat_client(api_key: str | None, endpoint: str | None, deployment: str | None) -> AzureOpenAIChatClient:
    cache_key = (api_key, endpoint, deployment)
    client = _CLIENT_CACHE.get(cache_key)
    if client is None:
        client = AzureOpenAIChatClient(
            api_key=api_key,
            endpoint=endpoint,
            deployment_name=deployment,
        )
        _CLIENT_CACHE[cache_key] = client
    return client


def create_message_store_factory(thread_id: str):
    """Factory function for creating Cosmos DB message stores with a specific thread_id.
    
    This enables both agents to share memory for the same user/conversation thread.
    
    Args:
        thread_id: Unique identifier for the user's conversation thread
        
    Returns:
        Factory function that creates CosmosDBChatMessageStore instances
    """
    from tools.cosmos_message_store import CosmosDBChatMessageStore
    
    def factory():
        return CosmosDBChatMessageStore(
            cosmos_endpoint=AUBREY_SETTINGS.cosmos_endpoint,
            cosmos_key=AUBREY_SETTINGS.cosmos_key,
            thread_id=thread_id,
            database_name=AUBREY_SETTINGS.cosmos_database_name,
            container_name=AUBREY_SETTINGS.cosmos_container_name,
            max_messages=AUBREY_SETTINGS.cosmos_max_messages,
        )
    return factory


@executor(id="entry_dispatcher")
async def _entry_dispatcher(
    request: AgentExecutorRequest, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Forward the patient request to downstream agents."""
    await ctx.send_message(request)


@executor(id="reply_emergency")
async def _handle_emergency(
    response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]
) -> None:
    """Short-circuit emergencies with an explicit safety message."""
    await ctx.yield_output("Yo, you should call 911 or go to the emergency room!")


@executor(id="final_response_router")
async def _final_response_router(
    responses: list[AgentExecutorResponse], ctx: WorkflowContext[Never, str]
) -> None:
    """Emit the care navigator reply when the triage agent clears the emergency check."""

    triage_response: AgentExecutorResponse | None = None
    care_nav_response: AgentExecutorResponse | None = None

    for response in responses:
        if response.executor_id == _TRIAGE_EXECUTOR_ID:
            triage_response = response
        elif response.executor_id == _CARE_NAV_EXECUTOR_ID:
            care_nav_response = response

    if triage_response is None or care_nav_response is None:
        # Require both responses before deciding on the final output.
        return

    triage_result: MedicalTriageResult | None = None
    if isinstance(triage_response.agent_run_response.value, MedicalTriageResult):
        triage_result = triage_response.agent_run_response.value
    else:
        try:
            triage_result = MedicalTriageResult.model_validate_json(
                triage_response.agent_run_response.text
            )
        except Exception:
            triage_result = None

    if triage_result and triage_result.is_medical_emergency:
        # Emergency messaging already emitted via the dedicated handler.
        return

    reply_text = care_nav_response.agent_run_response.text.strip()
    if reply_text:
        await ctx.yield_output(reply_text)


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


def create_workflow(thread_id: str | None = None) -> Workflow:
    """Create the workflow with optional thread_id for shared memory.
    
    Args:
        thread_id: Optional thread ID for persisting conversation memory.
                  If provided, both agents will share memory for this thread.
                  If None, agents will use default in-memory storage.
    """
    
    # Create the message store factory if thread_id is provided
    if thread_id:
        print(f"🧠 Creating workflow WITH persistent memory (thread_id: {thread_id})")
        message_store_factory = create_message_store_factory(thread_id)
    else:
        print("🧠 Creating workflow WITHOUT persistent memory (in-memory only)")
        message_store_factory = None
    
    med_triage_agent_executor = create_triage_executor_agent(
        get_chat_client(
            AUBREY_SETTINGS.azure_openai_api_key,
            AUBREY_SETTINGS.azure_openai_endpoint,
            AUBREY_SETTINGS.azure_openai_triage_model,
        ),
        chat_message_store_factory=message_store_factory,
    )

    care_navigator_executor = create_care_navigator_executor(
        get_chat_client(
            AUBREY_SETTINGS.azure_openai_api_key,
            AUBREY_SETTINGS.azure_openai_endpoint,
            AUBREY_SETTINGS.azure_openai_care_nav_model,
        ),
        chat_message_store_factory=message_store_factory,
    )

    return (
        WorkflowBuilder()
        .set_start_executor(_entry_dispatcher)
        .add_fan_out_edges(
            _entry_dispatcher,
            [med_triage_agent_executor, care_navigator_executor],
        )
        .add_edge(
            med_triage_agent_executor,
            _handle_emergency,
            condition=_condition_medical_emergency,
        )
        .add_fan_in_edges(
            [med_triage_agent_executor, care_navigator_executor],
            _final_response_router,
        )
        .build()
    )
