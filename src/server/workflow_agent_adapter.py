
from typing import Any
import uuid
from agent_framework import AgentExecutorRequest, AgentExecutorResponse, AgentRunResponse, AgentRunResponseUpdate, ChatMessage, Role, TextContent, TextReasoningContent, Workflow


class WorkflowAgentAdapter:
    """Expose the workflow via the Agent Framework streaming interface."""

    def __init__(self, workflow_instance: Workflow) -> None:
        self._workflow = workflow_instance
        self._id = "medical-workflow-agent"

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return "MedicalWorkflowAgent"

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def description(self) -> str:
        return "Routes medical questions through the triage workflow and responder agents."

    async def run(
        self,
        messages: Any = None,
        *,
        thread: Any | None = None,
        **kwargs: Any,
    ) -> AgentRunResponse:
        updates = [update async for update in self.run_stream(messages=messages, thread=thread, **kwargs)]
        if not updates:
            return AgentRunResponse(messages=[], response_id=str(uuid.uuid4()))
        return AgentRunResponse.from_agent_run_response_updates(updates)

    async def run_stream(
        self,
        messages: Any = None,
        *,
        thread: Any | None = None,
        **kwargs: Any,
    ):
        chat_messages = self._normalize_messages(messages)
        if not chat_messages:
            return

        response_id = str(uuid.uuid4())
        request = AgentExecutorRequest(messages=chat_messages, should_respond=True)
        # Emit an early reasoning chunk so AG-UI can show an active run indicator.
        yield AgentRunResponseUpdate(
            response_id=response_id,
            role=Role.ASSISTANT,
            contents=[TextReasoningContent(text="Analyzing input...")],
        )
        workflow_result = await self._workflow.run(request)
        outputs = workflow_result.get_outputs()

        if not outputs:
            yield AgentRunResponseUpdate(response_id=response_id, role=Role.ASSISTANT, text="")
            return

        final_output = outputs[-1]
        for update in self._build_updates(response_id, final_output):
            yield update

    def _normalize_messages(self, messages: Any) -> list[ChatMessage]:
        if messages is None:
            return []
        if isinstance(messages, ChatMessage):
            return [messages]
        if isinstance(messages, list):
            normalized: list[ChatMessage] = []
            for message in messages:
                if isinstance(message, ChatMessage):
                    normalized.append(message)
                elif isinstance(message, str):
                    normalized.append(ChatMessage(role=Role.USER, text=message))
            return normalized
        if isinstance(messages, str):
            return [ChatMessage(role=Role.USER, text=messages)]
        return []

    def _build_updates(self, response_id: str, output: Any):
        if isinstance(output, AgentExecutorResponse):
            agent_response = output.agent_run_response
            if agent_response.messages:
                for message in agent_response.messages:
                    yield AgentRunResponseUpdate(
                        response_id=response_id,
                        role=message.role,
                        contents=message.contents,
                        author_name=message.author_name,
                        message_id=message.message_id,
                    )
                return
            if agent_response.text:
                yield AgentRunResponseUpdate(
                    response_id=response_id,
                    role=Role.ASSISTANT,
                    text=agent_response.text,
                    contents=[TextContent(text=agent_response.text)],
                )
                return

        yield AgentRunResponseUpdate(response_id=response_id, role=Role.ASSISTANT, text=str(output))