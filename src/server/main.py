import asyncio
import json
import os
import textwrap
from typing import Any, Never
import dotenv
from pydantic import BaseModel
from agent_framework.azure import AzureOpenAIChatClient
from medical_triage_agent import create_agent as create_triage_agent, MedicalTriageResult
from medical_triage_agent import create_executor_agent as create_triage_executor_agent
from joint_surgery_info_agent import create_agent as create_joint_surgery_agent
from joint_surgery_info_agent import create_executor_agent as create_joint_surgery_executor_agent
from patient_authentication_agent import (
    PatientAuthenticationResult,
    create_executor_agent as create_authentication_executor_agent,
)

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    ChatMessage,
    Role,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    # Event types used for debugging output
    AgentRunEvent,
    AgentRunUpdateEvent,
    WorkflowOutputEvent,
    RequestInfoEvent,
    WorkflowStatusEvent,
    WorkflowFailedEvent,
    WorkflowStartedEvent,
    ExecutorInvokedEvent,
    ExecutorCompletedEvent,
)

# Configuration
dotenv.load_dotenv()
api_key =  os.environ.get("AZURE_OPENAI_API_KEY")
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")

chat_client = AzureOpenAIChatClient(
    api_key=api_key,
    endpoint=endpoint,
    deployment_name=deployment,
)

# Create agents
auth_agent_executor = create_authentication_executor_agent(chat_client)
med_triage_agent_executor = create_triage_executor_agent(chat_client)
med_triage_agent = create_triage_agent(chat_client)
joint_surgery_agent_executor_agent = create_joint_surgery_executor_agent(chat_client)

# Lets make sure the json returned is valid, and route based on the boolean value.
def condition_medical_emergency(message: Any) -> bool:
    # Defensive guard. If a non AgentExecutorResponse appears, let the edge pass to avoid dead ends.
    if not isinstance(message, AgentExecutorResponse):
        return True
    try:
        # Using model_validate_json ensures type safety and raises if the shape is wrong.
        detection = MedicalTriageResult.model_validate_json(message.agent_run_response.text)
        return detection.is_medical_emergency
    except Exception:
        # Fail closed on parse errors so we do not accidentally route to the wrong path.
        # Returning False prevents this edge from activating.
        return False


# Lets make sure the json returned is valid, and route based on the boolean value.
def condition_medical_guidance(message: Any) -> bool:
    # Defensive guard. If a non AgentExecutorResponse appears, let the edge pass to avoid dead ends.
    if not isinstance(message, AgentExecutorResponse):
        return True
    try:
        # Using model_validate_json ensures type safety and raises if the shape is wrong.
        detection = MedicalTriageResult.model_validate_json(message.agent_run_response.text)
        return detection.is_medical_advice
    except Exception:
        # Fail closed on parse errors so we do not accidentally route to the wrong path.
        # Returning False prevents this edge from activating.
        return False

def extract_authentication_result(message: Any) -> PatientAuthenticationResult | None:
    if not isinstance(message, AgentExecutorResponse):
        return None

    agent_response = message.agent_run_response
    value = getattr(agent_response, "value", None)

    try:
        if isinstance(value, PatientAuthenticationResult):
            return value
        if isinstance(value, dict):
            return PatientAuthenticationResult.model_validate(value)
        text = agent_response.text
        if text:
            return PatientAuthenticationResult.model_validate_json(text)
    except Exception:
        return None
    return None


@executor(id="handle_authentication_state")
async def handle_authentication_state(
    response: AgentExecutorResponse,
    ctx: WorkflowContext[AgentExecutorResponse, str],
) -> None:
    result = extract_authentication_result(response)

    if result is None:
        await ctx.yield_output(
            "I'm sorry, I couldn't process your information. Could you please share your details again so I can verify your identity?"
        )
        return

    await ctx.set_shared_state("patient_authentication", result.model_dump())

    if result.message_to_patient:
        await ctx.yield_output(result.message_to_patient)

    if result.triage_ready:
        await ctx.send_message(response)

# So this is just a simple handler that replies with emergency instructions.
# No LLM needed.
@executor(id="reply_emergency")
async def handle_emergency(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    # Downstream of the email assistant. Parse a validated EmailResponse and yield the workflow output.
    await ctx.yield_output(f"Yo, you should call 911 or go to the emergency room!")

# So this is just a simple handler that replies with emergency instructions.
# No LLM needed.
@executor(id="reply_medical_guidance")
async def handle_medical_guidance(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    # Downstream of the email assistant. Parse a validated EmailResponse and yield the workflow output.
    await ctx.yield_output(f"Sadly, I can't help with giving medical advice. Please consult a healthcare professional for guidance.")

# workflow = (
#     WorkflowBuilder()
#     .set_start_executor(med_triage_agent_executor)
#     # Start by short circuiting medical emergencies and medical advice.
#     .add_edge(med_triage_agent_executor, handle_emergency, condition=lambda msg: condition_medical_emergency(msg))
#     .add_edge(med_triage_agent_executor, handle_medical_guidance, condition=lambda msg: not condition_medical_emergency(msg) and condition_medical_guidance(msg))
#     # So for this edge, it's not a medical emergency, or medical guidance, and we can move it to the joint surgery agent.
#     .add_edge(med_triage_agent_executor, joint_surgery_agent_executor_agent, condition=lambda msg: not condition_medical_guidance(msg) and not condition_medical_emergency(msg))
#     .build()
# )

workflow = (
    WorkflowBuilder()
    .set_start_executor(auth_agent_executor)
    .add_edge(auth_agent_executor, handle_authentication_state)
    .add_edge(handle_authentication_state, med_triage_agent_executor)
    # Start by short circuiting medical emergencies and medical advice.
    .add_edge(med_triage_agent_executor, handle_emergency, condition=lambda msg: condition_medical_emergency(msg))
    .add_edge(
        med_triage_agent_executor,
        handle_medical_guidance,
        condition=lambda msg: not condition_medical_emergency(msg) and condition_medical_guidance(msg),
    )
    # So for this edge, it's not a medical emergency, or medical guidance, and we can move it to the joint surgery agent.
    .add_edge(
        med_triage_agent_executor,
        joint_surgery_agent_executor_agent,
        condition=lambda msg: not condition_medical_guidance(msg) and not condition_medical_emergency(msg),
    )
    .build()
)


def pretty_print_event(index: int, event: object) -> None:
    """Print a structured, emoji-annotated representation of workflow events for debugging."""
    def _wrap(text: str, indent: int = 6) -> None:
        for line in textwrap.wrap(text, width=120):
            print(" " * indent + line)

    prefix = f"[{index}]"
    # Agent run (completed)
    if isinstance(event, AgentRunEvent):
        resp = event.data
        text = getattr(resp, "text", str(resp))
        print(f"{prefix} 🤖 {getattr(event, 'executor_id', '')}:")
        _wrap(text)
        if getattr(resp, "value", None) is not None:
            print("      parsed:")
            v = resp.value
            if isinstance(v, BaseModel):
                print(textwrap.indent(v.model_dump_json(), "      "))
            else:
                try:
                    print(textwrap.indent(json.dumps(v, indent=2), "      "))
                except Exception:
                    print("      " + str(v))
        return

    # Agent streaming update
    if isinstance(event, AgentRunUpdateEvent):
        update = event.data
        text = getattr(update, "text", str(update))
        print(f"{prefix} 🤖 {getattr(event, 'executor_id', '')} (stream):")
        _wrap(text)
        return

    # Workflow output event
    if isinstance(event, WorkflowOutputEvent):
        print(f"{prefix} 📤 Output from 🤖 {getattr(event, 'source_executor_id', '')}:")
        data = getattr(event, "data", "")
        _wrap(str(data))
        return

    # Request for external info
    if isinstance(event, RequestInfoEvent):
        print(f"{prefix} 🔔 RequestInfo (id={event.request_id}, source={event.source_executor_id}):")
        _wrap(str(event.data))
        return

    # Lifecycle/status events
    if isinstance(event, WorkflowStatusEvent):
        print(f"{prefix} 🔁 Status: {event.state}")
        return

    if isinstance(event, WorkflowFailedEvent):
        print(f"{prefix} ❌ Workflow failed: {event.details.message}")
        return

    if isinstance(event, WorkflowStartedEvent):
        print(f"{prefix} ▶️ Workflow started")
        return

    # Generic executor events (invoked/completed)
    if isinstance(event, ExecutorInvokedEvent):
        print(f"{prefix} ⌛ Invoked: {getattr(event, 'executor_id', '')}")
        return

    if isinstance(event, ExecutorCompletedEvent):
        print(f"{prefix} ✅ Completed: {getattr(event, 'executor_id', '')}")
        return

    # Fallback
    print(f"{prefix} {event}")

async def main():
    question = "I'm currently on fire and having a hard time breathing."
    print("Asking question:", question)

    request = AgentExecutorRequest(messages=[ChatMessage(Role.USER, text=question)], should_respond=True)
    events = await workflow.run(request)

    # Print all events for debugging so we can see agent run events even if they are not
    # produced as WorkflowOutputEvent instances. This uses emojis for agent events.

    print("Workflow events:")
    for i, ev in enumerate(events):
        pretty_print_event(i, ev)

    outputs = events.get_outputs()
    if outputs:
        #print("Workflow outputs:")
        #for idx, out in enumerate(outputs):
            #print(f"  Output {idx}: {out}")
        print(f"Final output: {outputs[-1]}")

if __name__ == "__main__":
    asyncio.run(main())