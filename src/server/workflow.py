import functools
import logging
import types
from typing import Any, Never


from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Role,
    TextContent,
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


logger = logging.getLogger("uvicorn.error").getChild("workflow")
logger.setLevel(logging.INFO)


_CLIENT_CACHE: dict[
    tuple[str | None, str | None, str | None], AzureOpenAIChatClient
] = {}


_TRIAGE_EXECUTOR_ID = "medical_triage_agent_executor"
_CARE_NAV_EXECUTOR_ID = "care_navigator_agent_executor"


def get_chat_client(
    api_key: str | None,
    endpoint: str | None,
    deployment: str | None,
) -> AzureOpenAIChatClient:
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

    logger.info("final_response_router invoked")
    triage_response: AgentExecutorResponse | None = None
    care_nav_response: AgentExecutorResponse | None = None

    for response in responses:
        if response.executor_id == _TRIAGE_EXECUTOR_ID:
            triage_response = response
        elif response.executor_id == _CARE_NAV_EXECUTOR_ID:
            care_nav_response = response

    if triage_response is None or care_nav_response is None:
        logger.warning("final_response_router missing triage or care navigator response")
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

    logger.info(
        "triage result", extra={"triage_result": triage_result.model_dump() if triage_result else None}
    )
    if triage_result and triage_result.is_medical_emergency:
        # Emergency messaging already emitted via the dedicated handler.
        logger.info("triage flagged emergency; skipping care navigator output")
        return

    response_text = (care_nav_response.agent_run_response.text or "").strip()
    logger.info(
        "care navigator response envelope",
        extra={
            "text_field": response_text,
            "message_count": len(care_nav_response.agent_run_response.messages or []),
        },
    )

    if not response_text:
        # Fallback: extract assistant text from the agent run response messages.
        parts: list[str] = []
        for message in care_nav_response.agent_run_response.messages or []:
            if getattr(message, "role", None) != Role.ASSISTANT:
                continue
            for content in message.contents or []:
                if isinstance(content, TextContent) and content.text:
                    parts.append(content.text.strip())
        response_text = "\n\n".join(filter(None, parts)).strip()

    logger.info("fallback message text", extra={"fallback_text": response_text})
    if not response_text and care_nav_response.full_conversation:
        # Final attempt: check merged conversation history for the last assistant reply.
        for message in reversed(care_nav_response.full_conversation or []):
            if getattr(message, "role", None) != Role.ASSISTANT:
                continue
            chunk_parts: list[str] = []
            for content in message.contents or []:
                if isinstance(content, TextContent) and content.text:
                    chunk_parts.append(content.text.strip())
            candidate = "\n\n".join(filter(None, chunk_parts)).strip()
            if candidate:
                response_text = candidate
                break

    if response_text:
        logger.info("final care navigator response", extra={"response_text": response_text})
        await ctx.yield_output(response_text)
    else:
        logger.warning("no care navigator response produced")


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

def _attach_additional_chat_options_shim(workflow: Workflow) -> Workflow:
    """Drop forward-compat chat kwargs unsupported by our agent-framework version."""

    original_run = workflow.run

    target_run = getattr(original_run, "__func__", original_run)

    @functools.wraps(target_run)
    async def run_with_shim(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        kwargs.pop("additional_chat_options", None)
        return await original_run(*args, **kwargs)

    original_run_stream = workflow.run_stream
    target_stream = getattr(original_run_stream, "__func__", original_run_stream)

    @functools.wraps(target_stream)
    async def run_stream_with_shim(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        kwargs.pop("additional_chat_options", None)
        async for event in original_run_stream(*args, **kwargs):
            yield event

    workflow.run = types.MethodType(run_with_shim, workflow)
    workflow.run_stream = types.MethodType(run_stream_with_shim, workflow)
    return workflow


def build_workflow() -> Workflow:
    med_triage_agent_executor = create_triage_executor_agent(
        get_chat_client(
            AUBREY_SETTINGS.azure_openai_api_key,
            AUBREY_SETTINGS.azure_openai_endpoint,
            AUBREY_SETTINGS.azure_openai_triage_model,
        )
    )

    care_navigator_executor = create_care_navigator_executor(
        get_chat_client(
            AUBREY_SETTINGS.azure_openai_api_key,
            AUBREY_SETTINGS.azure_openai_endpoint,
            AUBREY_SETTINGS.azure_openai_care_nav_model,
        )
    )

    workflow = (
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

    return _attach_additional_chat_options_shim(workflow)
