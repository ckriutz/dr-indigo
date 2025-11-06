from agent_framework import AgentExecutorRequest, ChatMessage, Role
from fastapi import FastAPI

from copilotkit import CopilotKitRemoteEndpoint, Action as CopilotAction
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from telemetry import initiate_telemetry
from workflow import create_workflow

initiate_telemetry()

# Initialize FastAPI app
app = FastAPI()
workflow = create_workflow()


# this is the medical emergency action for demonstration purposes
async def ask_medical_question_workflow_agent(question: str):
    print("Received question in ask_medical_question_workflow_agent:", question)
    request = AgentExecutorRequest(
        messages=[ChatMessage(Role.USER, text=question)], should_respond=True
    )
    events = await workflow.run(request)
    outputs = events.get_outputs()
    response = outputs[-1]
    print("Medical Question Agent Response in action:", response)
    return {"response": response}


medical_question_action = CopilotAction(
    name="askMedicalQuestionAgent",
    description="Send a question to the medical question agent and get a response.",
    parameters=[
        {
            "name": "question",
            "type": "string",
            "description": "The medical question to ask the question agent.",
            "required": True,
        }
    ],
    handler=ask_medical_question_workflow_agent,
)


async def reply_greeting(greeting: str):
    # Replace with your database logic
    print("Received greeting in reply_greeting action:", greeting)
    return {"greeting": greeting}


# Greeting Action
greetingAction = CopilotAction(
    name="replyGreeting",
    description="When the user says hello, or gives their name, or any other general greeting, reply with a greeting message.",
    parameters=[
        {
            "name": "greeting",
            "type": "string",
            "description": "The greeting message to reply with.",
            "required": True,
        }
    ],
    handler=reply_greeting,
)

# Initialize the CopilotKit SDK
sdk = CopilotKitRemoteEndpoint(actions=[greetingAction, medical_question_action])

# Add the CopilotKit endpoint to your FastAPI app
add_fastapi_endpoint(app, sdk, "/copilotkit_remote")


def main():
    """Run the uvicorn server."""
    import uvicorn

    uvicorn.run("api:app", host="localhost", port=8000, reload=True)


if __name__ == "__main__":
    main()