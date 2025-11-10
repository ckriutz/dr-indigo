import asyncio
import json
import textwrap
import time

from agent_framework import (
    AgentExecutorRequest,
    ChatMessage,
    Role,
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
from openai import BaseModel

from workflow import build_workflow


async def main() -> None:
    workflow = build_workflow()
    conversation: list[ChatMessage] = []

    print("Interactive medical triage chat ready. Type 'exit' to quit.")

    while True:
        try:
            user_input = await asyncio.to_thread(input, "You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting chat.")
            break

        message = user_input.strip()
        if not message:
            continue

        if message.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        conversation.append(ChatMessage(Role.USER, text=message))

        request = AgentExecutorRequest(messages=conversation, should_respond=True)

        start_time = time.perf_counter()
        try:
            events = await workflow.run(request)
        except Exception as exc:
            print(f"Workflow error: {exc}")
            conversation.pop()
            continue

        response_duration = time.perf_counter() - start_time

        if events:
            print("Workflow events:")
            for index, event in enumerate(events):
                _pretty_print_event(index, event)

        outputs = events.get_outputs() if events else []
        response_text: str | None = None

        if outputs:
            response_text = str(outputs[-1])
        else:
            for event in reversed(events or []):
                if isinstance(event, AgentRunEvent):
                    agent_response = getattr(event, "data", None)
                    if agent_response is None:
                        continue

                    text_value = getattr(agent_response, "text", None)
                    if text_value:
                        response_text = str(text_value)
                        break

                    messages = getattr(agent_response, "messages", None)
                    if messages:
                        for msg in reversed(messages):
                            msg_text = getattr(msg, "text", None)
                            if msg_text:
                                response_text = str(msg_text)
                                break
                    if response_text:
                        break

        if response_text:
            print(f"Agent: {response_text}")
            conversation.append(ChatMessage(Role.ASSISTANT, text=response_text))
            print(f"(Response time: {response_duration:.2f}s)")
        else:
            print("Agent produced no output.")
            print(f"(Response time: {response_duration:.2f}s)")


def _pretty_print_event(index: int, event: object) -> None:
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
        print(
            f"{prefix} 🔔 RequestInfo (id={event.request_id}, source={event.source_executor_id}):"
        )
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


if __name__ == "__main__":
    asyncio.run(main())
