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


# Add REST endpoints for testing/evaluation purposes
@app.post("/ask")
async def ask_question(request: dict):
    """
    Simple REST endpoint for directly querying the care navigator agent.
    Bypasses the full workflow and goes straight to the care navigator.
    
    Example:
        POST /ask
        {"question": "What should I expect after knee surgery?"}
    """
    question = request.get("question", "")
    if not question:
        return {"error": "No question provided"}
    
    try:
        from agents.care_navigator_agent import create_care_navigator_agent
        from settings import AUBREY_SETTINGS
        from workflow import _get_chat_client
        
        # Create the care navigator ChatAgent directly (not the executor)
        chat_client = _get_chat_client(
            AUBREY_SETTINGS.azure_openai_api_key,
            AUBREY_SETTINGS.azure_openai_endpoint,
            AUBREY_SETTINGS.azure_openai_care_nav_model,
        )
        
        care_nav_agent = create_care_navigator_agent(chat_client)
        
        # Run the agent with just the question text
        response = await care_nav_agent.run(question)
        
        # Extract the response text
        if response and hasattr(response, 'text'):
            return {"response": response.text}
        else:
            return {"response": str(response)}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.post("/ask_workflow")
async def ask_question_workflow(request: dict):
    """
    REST endpoint that uses the full workflow including triage agent.
    Routes through medical emergency detection and care navigator.
    
    Example:
        POST /ask_workflow
        {"question": "What should I expect after knee surgery?"}
    """
    question = request.get("question", "")
    if not question:
        return {"error": "No question provided"}
    
    try:
        # Create a request for the workflow
        workflow_request = AgentExecutorRequest(
            messages=[ChatMessage(Role.USER, text=question)],
            should_respond=True
        )
        
        # Run through the full workflow
        events = await workflow.run(workflow_request)
        outputs = events.get_outputs()
        
        # Extract the final response
        if outputs and len(outputs) > 0:
            output = outputs[-1]
            
            # Handle different output types
            if isinstance(output, str):
                response_text = output
            elif hasattr(output, 'text'):
                response_text = output.text
            elif hasattr(output, 'agent_run_response') and output.agent_run_response:
                response_text = output.agent_run_response.text
            else:
                # Fallback to string representation
                response_text = str(output)
            
            return {"response": response_text}
        else:
            return {"response": "No response from workflow"}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def main():
    """Run the uvicorn server."""
    import uvicorn

    uvicorn.run("api:app", host="localhost", port=8000, reload=True)


if __name__ == "__main__":
    main()
