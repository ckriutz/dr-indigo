import logging

from fastapi import FastAPI, Request


# from telemetry import initiate_telemetry
from workflow import build_workflow

from ag_ui_agent_framework import (
    AgentFrameworkRunner,
    AgentFrameworkRunnerConfig,
    add_agent_framework_fastapi_endpoint,
    workflow_agent,
)

# initiate_telemetry()

logger = logging.getLogger("uvicorn.error").getChild("agent")
logger.setLevel(logging.INFO)


# Initialize FastAPI app
app = FastAPI()


@app.middleware("http")
async def log_agent_requests(request: Request, call_next):
    """Emit structured logs whenever the AG-UI endpoint is hit."""

    if request.url.path.startswith("/agent"):
        logger.info(
            "incoming agent request",
            extra={
                "path": request.url.path,
                "client": request.client.host if request.client else None,
                "query": str(request.url.query or ""),
            },
        )

    response = await call_next(request)

    if request.url.path.startswith("/agent"):
        logger.info(
            "agent request completed",
            extra={
                "status_code": response.status_code,
                "path": request.url.path,
            },
        )

    return response


def _build_runner() -> AgentFrameworkRunner:
    workflow = build_workflow()
    agent = workflow_agent(
        workflow,
        name="care-navigation-workflow",
        description="Routes medical questions through a triage and care navigation workflow.",
    )
    config = AgentFrameworkRunnerConfig(emit_initial_state_snapshot=False)
    return AgentFrameworkRunner(agent, config=config)


# this is the medical emergency action for demonstration purposes
# async def ask_medical_question_workflow_agent(question: str):
#     print("Received question in ask_medical_question_workflow_agent:", question)

#     request_workflow = build_workflow()

#     request = AgentExecutorRequest(
#         messages=[ChatMessage(Role.USER, text=question)], should_respond=True
#     )
#     events = await request_workflow.run(request)
#     outputs = events.get_outputs()
#     response = outputs[-1]
#     print("Medical Question Agent Response in action:", response)
#     return {"response": response}

# medical_question_action = CopilotAction(
#     name="askMedicalQuestionAgent",
#     description="Send a question to the medical question agent and get a response.",
#     parameters=[
#         {
#             "name": "question",
#             "type": "string",
#             "description": "The medical question to ask the question agent.",
#             "required": True,
#         }
#     ],
#     handler=ask_medical_question_workflow_agent,
# )


# async def reply_greeting(greeting: str):
#     # Replace with your database logic
#     print("Received greeting in reply_greeting action:", greeting)
#     return {"greeting": greeting}


# Greeting Action
# greetingAction = CopilotAction(
#     name="replyGreeting",
#     description="When the user says hello, or gives their name, or any other general greeting, reply with a greeting message.",
#     parameters=[
#         {
#             "name": "greeting",
#             "type": "string",
#             "description": "The greeting message to reply with.",
#             "required": True,
#         }
#     ],
#     handler=reply_greeting,
# )

# Initialize the CopilotKit SDK
# sdk = CopilotKitRemoteEndpoint(actions=[greetingAction, medical_question_action])

# Add the CopilotKit endpoint to your FastAPI app
# add_fastapi_endpoint(app, sdk, "/copilotkit_remote")


# Add a simple REST endpoint for testing/evaluation purposes
# @app.post("/ask")
# async def ask_question(request: dict):
#     """
#     Simple REST endpoint for directly querying the joint surgery info agent.
#     Bypasses the triage workflow and goes straight to the joint surgery agent.

#     Example:
#         POST /ask
#         {"question": "I'm in pain, what should I do?"}
#     """
#     question = request.get("question", "")
#     if not question:
#         return {"error": "No question provided"}

#     try:
#         # Create the care navigator agent
#         care_navigator_agent = create_care_navigator_agent(get_chat_client(
#             AUBREY_SETTINGS.azure_openai_api_key,
#             AUBREY_SETTINGS.azure_openai_endpoint,
#             AUBREY_SETTINGS.azure_openai_care_nav_model,
#         ))
#         # Use the ChatAgent directly with a simple run
#         response = await care_navigator_agent.run(question)

#         # Extract the response text
#         if response and hasattr(response, 'text'):
#             return {"response": response.text}
#         elif isinstance(response, str):
#             return {"response": response}
#         else:
#             return {"response": str(response)}

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"error": str(e)}

# @app.post("/ask_workflow")
# async def ask_question_workflow(request: dict):
#     """
#     REST endpoint that uses the full workflow including triage agent.
#     Routes through medical emergency detection and medical advice filtering.

#     Example:
#         POST /ask_workflow
#         {"question": "I'm in pain, what should I do?"}
#     """
#     question = request.get("question", "")
#     if not question:
#         return {"error": "No question provided"}

#     try:

#         request_workflow = build_workflow()

#         # Create a request for the workflow
#         workflow_request = AgentExecutorRequest(
#             messages=[ChatMessage(Role.USER, text=question)],
#             should_respond=True
#         )

#         # Run through the full workflow
#         events = await request_workflow.run(workflow_request)
#         outputs = events.get_outputs()

#         # Extract the final response
#         if outputs and len(outputs) > 0:
#             output = outputs[-1]

#             # Handle different output types
#             if isinstance(output, str):
#                 response_text = output
#             elif hasattr(output, 'text'):
#                 response_text = output.text
#             elif hasattr(output, 'agent_run_response') and output.agent_run_response:
#                 response_text = output.agent_run_response.text
#             else:
#                 # Fallback to string representation
#                 response_text = str(output)

#             return {"response": response_text}
#         else:
#             return {"response": "No response from workflow"}

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"error": str(e)}

runner = _build_runner()
add_agent_framework_fastapi_endpoint(app, runner, path="/agent")


def main():
    """Run the uvicorn server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
