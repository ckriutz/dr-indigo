import logging
import traceback
import uuid
from threading import Lock
from typing import Any, Dict, List, Optional

import uvicorn
from agent_framework import AgentExecutorRequest, ChatMessage, Role
from copilotkit import Action as CopilotAction
from copilotkit import CopilotKitRemoteEndpoint
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.care_navigator_agent import create_care_navigator_agent
from settings import AUBREY_SETTINGS
from workflow import create_message_store_factory, create_workflow, get_chat_client

# ------------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------------
logger = logging.getLogger("api")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

# ------------------------------------------------------------------------------------
# Thread + Workflow Caches
# ------------------------------------------------------------------------------------
_thread_id_cache: Dict[str, str] = {}
_workflow_cache: Dict[str, Any] = {}
_cache_lock = Lock()


def get_or_create_thread_id(conversation_key: str = "default") -> str:
    """Return an existing thread ID or create a new one for a conversation key."""
    with _cache_lock:
        if conversation_key not in _thread_id_cache:
            new_thread_id = str(uuid.uuid4())
            _thread_id_cache[conversation_key] = new_thread_id
            logger.info("🆕 Created thread_id=%s for key=%s", new_thread_id, conversation_key)
        return _thread_id_cache[conversation_key]


def get_or_create_workflow(thread_id: str) -> Any:
    """Return a cached workflow for a thread ID (creates if missing)."""
    with _cache_lock:
        wf = _workflow_cache.get(thread_id)
        if wf is None:
            wf = create_workflow(thread_id=thread_id)
            _workflow_cache[thread_id] = wf
            logger.info("🔄 Created workflow for thread_id=%s", thread_id)
        return wf


# Establish a default workflow/thread for CopilotKit actions
DEFAULT_THREAD_KEY = "aubrey_session_2"
DEFAULT_THREAD_ID = get_or_create_thread_id(DEFAULT_THREAD_KEY)
DEFAULT_WORKFLOW = get_or_create_workflow(DEFAULT_THREAD_ID)

# ------------------------------------------------------------------------------------
# Request / Response Models
# ------------------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None


class AskWorkflowRequest(BaseModel):
    question: str
    # Optional in case you want to scope different workflow memory later
    thread_key: Optional[str] = "copilotkit_session"


class AskResponse(BaseModel):
    response: str


# ------------------------------------------------------------------------------------
# Output Extraction Helpers
# ------------------------------------------------------------------------------------
def extract_output_text(outputs: List[Any]) -> str:
    """Extract a human-readable response from workflow/agent outputs."""
    if not outputs:
        return "No response generated."

    output = outputs[-1]

    # Common cases
    if isinstance(output, str):
        return output

    # Check common attributes
    for attr in ("text", "agent_run_response"):
        if hasattr(output, attr):
            value = getattr(output, attr)
            if isinstance(value, str):
                return value
            if hasattr(value, "text"):
                return value.text

    # Fallback
    return str(output)


async def run_workflow_question(workflow: Any, question: str, context_messages: list[ChatMessage] = None) -> str:
    """Run a workflow for a single user question and return extracted text."""
    messages = context_messages or []
    messages.append(ChatMessage(Role.USER, text=question))

    try:
        request = AgentExecutorRequest(
            messages=messages,
            should_respond=True,
        )
        events = await workflow.run(request)
        outputs = events.get_outputs()
        response_text = extract_output_text(outputs)
        logger.info("🧠 Workflow response (truncated): %s", response_text[:150])
        return response_text
    except Exception as exc:
        logger.error("Error running workflow: %s", exc, exc_info=True)
        return "I encountered an error processing your request."


# ------------------------------------------------------------------------------------
# CopilotKit Action Handlers
# ------------------------------------------------------------------------------------
async def ask_medical_question_workflow_agent(question: str) -> str:
    """
    Handler for CopilotKit action: routes a question through the default workflow.
    """
    logger.info("Received CopilotKit medical question: %s", question)
    return await run_workflow_question(DEFAULT_WORKFLOW, question)


async def get_user_info_handler(name: str, birthday: str) -> str:
    """Extract user information when provided."""
    logger.info("Received user info - name=%s birthday=%s", name, birthday)
    return f"Thanks for the information, {name}! How can I assist you further?"


medical_question_action = CopilotAction(
    name="askMedicalQuestionAgent",
    description="Send a medical question to the workflow agent and get a response.",
    parameters=[
        {
            "name": "question",
            "type": "string",
            "description": "The medical question to ask the agent.",
            "required": True,
        }
    ],
    handler=ask_medical_question_workflow_agent,
)

get_user_info_action = CopilotAction(
    name="getUser",
    description="When the user provides their name and birthday, extract this information for further use.",
    parameters=[
        {
            "name": "name",
            "type": "string",
            "description": "The user's name.",
            "required": True,
        },
        {
            "name": "birthday",
            "type": "string",
            "description": "The user's birthday.",
            "required": True,
        },
    ],
    handler=get_user_info_handler,
)

sdk = CopilotKitRemoteEndpoint(actions=[get_user_info_action, medical_question_action])

# ------------------------------------------------------------------------------------
# FastAPI App Initialization
# ------------------------------------------------------------------------------------
app = FastAPI(title="Dr Indigo API")
add_fastapi_endpoint(app, sdk, "/copilotkit_remote")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# ------------------------------------------------------------------------------------
# REST Endpoints
# ------------------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs", "health": "/health"}


@app.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest) -> AskResponse:
    """
    Directly query the care navigator agent (bypasses full triage workflow).
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # Optional memory scope via thread_id
        message_store_factory = None
        if payload.thread_id:
            message_store_factory = create_message_store_factory(payload.thread_id)

        care_navigator_agent = create_care_navigator_agent(
            get_chat_client(
                AUBREY_SETTINGS.azure_openai_api_key,
                AUBREY_SETTINGS.azure_openai_endpoint,
                AUBREY_SETTINGS.azure_openai_care_nav_model,
            ),
            chat_message_store_factory=message_store_factory,
        )

        response = await care_navigator_agent.run(question)

        # Extract text
        if hasattr(response, "text"):
            return AskResponse(response=response.text)
        if isinstance(response, str):
            return AskResponse(response=response)
        return AskResponse(response=str(response))

    except Exception:
        logger.error("Unhandled exception in /ask endpoint:\n%s", traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.post("/ask_workflow", response_model=AskResponse)
async def ask_question_workflow(payload: AskWorkflowRequest) -> AskResponse:
    """
    Routes a question through the full workflow (triage + advice filtering).
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    thread_key = payload.thread_key or "copilotkit_session"
    thread_id = get_or_create_thread_id(thread_key)
    workflow = get_or_create_workflow(thread_id)

    logger.info("Using workflow thread_id=%s for key=%s", thread_id, thread_key)

    try:
        response_text = await run_workflow_question(workflow, question)
        return AskResponse(response=response_text)
    except Exception:
        logger.error("Unhandled exception in /ask_workflow endpoint:\n%s", traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ------------------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------------------
def main() -> None:
    """Run the uvicorn server (development)."""
    uvicorn.run("api:app", host="localhost", port=8000, reload=True)


if __name__ == "__main__":
    main()
