import asyncio
import json
import os
import textwrap
from typing import Any, Never
import dotenv
from pydantic import BaseModel
from agent_framework.azure import AzureOpenAIChatClient
from medical_emergency_agent import create_agent as create_emergency_agent, IsMedicalEmergencyResult
from medical_emergency_agent import create_executor_agent as create_emergency_executor_agent
from joint_surgery_info_agent import create_agent as create_joint_surgery_agent
from joint_surgery_info_agent import create_executor_agent as create_joint_surgery_executor_agent
from medical_guidance_agent import create_agent as create_medical_guidance_executor_agent, IsMedicalGuidanceResult

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

joint_surgery_agent = create_joint_surgery_agent(chat_client)
med_emergency_agent = create_emergency_agent(chat_client)

med_emergency_agent_executor = create_emergency_executor_agent(chat_client)
medical_guidance_executor_agent = create_medical_guidance_executor_agent(chat_client)
joint_surgery_agent_executor = create_joint_surgery_executor_agent(chat_client)

def condition_medical_emergency(message: Any) -> bool:
    # Defensive guard. If a non AgentExecutorResponse appears, let the edge pass to avoid dead ends.
    if not isinstance(message, AgentExecutorResponse):
        return True
    try:
        # Prefer parsing a structured DetectionResult from the agent JSON text.
        # Using model_validate_json ensures type safety and raises if the shape is wrong.
        detection = IsMedicalEmergencyResult.model_validate_json(message.agent_run_response.text)
        # Route to the joint surgery agent only when the message is NOT a medical emergency.
        # In other words, if the detector returns False for `is_medical_emergency`, we continue
        # to the joint surgery information agent for normal informational queries.
        return not detection.is_medical_emergency
    except Exception:
        # Fail closed on parse errors so we do not accidentally route to the wrong path.
        # Returning False prevents this edge from activating.
        return False


def condition_medical_guidance(message: Any) -> bool:
    """
    Determine whether the message should be routed to the joint surgery agent.

    This expects an AgentExecutorResponse holding an IsMedicalGuidanceResult JSON.
    Returns True when the message is NOT medical guidance (safe to route to joint surgery),
    and False otherwise. On parse errors we "fail closed" and return False.
    """
    # Defensive guard. If a non AgentExecutorResponse appears, let the edge pass to avoid dead ends.
    if not isinstance(message, AgentExecutorResponse):
        return True
    try:
        detection = IsMedicalGuidanceResult.model_validate_json(message.agent_run_response.text)
        return not detection.is_medical_guidance
    except Exception:
        return False

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

workflow = (
    WorkflowBuilder()
    .set_start_executor(med_emergency_agent_executor)
    # Start by short circuiting medical emergencies.
    .add_edge(med_emergency_agent_executor, handle_emergency, condition=lambda msg: not condition_medical_emergency(msg))
    # At this point, we know it's NOT a medical emergency. Lets make sure it's not a medical question.
    .add_edge(med_emergency_agent_executor, medical_guidance_executor_agent, condition=condition_medical_emergency)
    .add_edge(medical_guidance_executor_agent, handle_medical_guidance, condition=lambda msg: not condition_medical_guidance(msg))
    # So for this edge, it's not a medical emergency, or medical guidance, and we can move it to the joint surgery agent.
    .add_edge(medical_guidance_executor_agent, joint_surgery_agent_executor, condition=condition_medical_guidance)
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
    question = "I'm currently on fire."
    print("Asking question:", question)

    request = AgentExecutorRequest(messages=[ChatMessage(Role.USER, text=question)], should_respond=True)
    events = await workflow.run(request)

    # Print all events for debugging so we can see agent run events even if they are not
    # produced as WorkflowOutputEvent instances. This uses emojis for agent events.

    #print("Workflow events:")
    #for i, ev in enumerate(events):
    #    pretty_print_event(i, ev)

    outputs = events.get_outputs()
    if outputs:
        #print("Workflow outputs:")
        #for idx, out in enumerate(outputs):
            #print(f"  Output {idx}: {out}")
        print(f"Final output: {outputs[-1]}")

if __name__ == "__main__":
    asyncio.run(main())