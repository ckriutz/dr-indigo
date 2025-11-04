import os
from typing import Any, Never

from agent_framework import AgentExecutorRequest, AgentExecutorResponse, ChatMessage, Role, WorkflowBuilder, WorkflowContext, executor
import dotenv
from fastapi import FastAPI

from agent_framework.azure import AzureOpenAIChatClient
from copilotkit import CopilotKitRemoteEndpoint, Action as CopilotAction
from copilotkit.integrations.fastapi import add_fastapi_endpoint

from medical_triage_agent import create_agent as create_triage_agent, MedicalTriageResult
from medical_triage_agent import create_executor_agent as create_triage_executor_agent
from joint_surgery_info_agent import create_agent as create_joint_surgery_agent
from joint_surgery_info_agent import create_executor_agent as create_joint_surgery_executor_agent



# Load environment variables
dotenv.load_dotenv()

# Setup Langfuse observability
try:
    from agent_framework.observability import setup_observability
    from langfuse import Langfuse
    import httpx

    os.environ["REQUESTS_CA_BUNDLE"] = "novant_ssl.cer"

    # Create httpx client with custom SSL certificate for Langfuse
    httpx_client = httpx.Client(verify="novant_ssl.cer")

    # Initialize Langfuse with custom SSL configuration
    langfuse = Langfuse(
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        host=os.environ.get("LANGFUSE_HOST"),
        httpx_client=httpx_client
    )
    
    # Setup observability
    setup_observability(enable_sensitive_data=True)
    print("✅ Observability setup completed!")
    
    # Verify Langfuse connection
    try:
        if langfuse.auth_check():
            print("✅ Langfuse client authenticated and ready!")
        else:
            print("⚠️  Langfuse authentication failed")
    except Exception as e:
        print(f"⚠️  Langfuse auth check error: {e}")
    
except ImportError as e:
    print(f"⚠️  setup_observability not available. Error: {e}")
    print("⚠️  Continuing without observability setup.")
    langfuse = None

api_key = os.environ.get("AZURE_OPENAI_API_KEY")
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")

# Initialize Azure OpenAI Chat Client
chat_client = AzureOpenAIChatClient(
    api_key=api_key,
    endpoint=endpoint,
    deployment_name=deployment,
)

# Create agents
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
    
# So this is just a simple handler that replies with emergency instructions.
# No LLM needed, and whatever we put in here is what the workflow will output.
@executor(id="reply_emergency")
async def handle_emergency(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    print("Handling emergency response:", response)
    await ctx.yield_output(f"Yo, you should call 911 or go to the emergency room!")

# So this is just a simple handler that replies with medical guidance instructions.
# No LLM needed, and whatever we put in here is what the workflow will output.
@executor(id="reply_medical_guidance")
async def handle_medical_guidance(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    print("Handling medical guidance response:", response)
    await ctx.yield_output(f"Sadly, I can't help with giving medical advice. Please consult a healthcare professional for guidance.")

# Here is our workflow definition.
workflow = (
    WorkflowBuilder()
    .set_start_executor(med_triage_agent_executor)
    # Start by short circuiting medical emergencies and medical advice.
    .add_edge(med_triage_agent_executor, handle_emergency, condition=lambda msg: condition_medical_emergency(msg))
    .add_edge(med_triage_agent_executor, handle_medical_guidance, condition=lambda msg: not condition_medical_emergency(msg) and condition_medical_guidance(msg))
    # So for this edge, it's not a medical emergency, or medical guidance, and we can move it to the joint surgery agent.
    .add_edge(med_triage_agent_executor, joint_surgery_agent_executor_agent, condition=lambda msg: not condition_medical_guidance(msg) and not condition_medical_emergency(msg))
    .build()
)

# Initialize FastAPI app
app = FastAPI()

# Backend Actions.
# this is a dummy action for demonstration purposes, but will work in testing.
async def reply_greeting(greeting: str):
    # Replace with your database logic
    print("Received greeting in reply_greeting action:", greeting)
    return {"greeting": greeting}

# this is the medical emergency action for demonstration purposes
async def ask_medical_question_workflow_agent(question: str):
    print("Received question in ask_medical_question_workflow_agent:", question)
    request = AgentExecutorRequest(messages=[ChatMessage(Role.USER, text=question)], should_respond=True)
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
    handler=ask_medical_question_workflow_agent
)

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
    handler=reply_greeting
)

# Initialize the CopilotKit SDK
sdk = CopilotKitRemoteEndpoint(actions=[greetingAction, medical_question_action]) 

# Add the CopilotKit endpoint to your FastAPI app
add_fastapi_endpoint(app, sdk, "/copilotkit_remote")

# Add a simple REST endpoint for testing/evaluation purposes
@app.post("/ask")
async def ask_question(request: dict):
    """
    Simple REST endpoint for directly querying the joint surgery info agent.
    Bypasses the triage workflow and goes straight to the joint surgery agent.
    
    Example:
        POST /ask
        {"question": "I'm in pain, what should I do?"}
    """
    question = request.get("question", "")
    if not question:
        return {"error": "No question provided"}
    
    try:
        # Create the joint surgery agent
        joint_surgery_agent = create_joint_surgery_agent(chat_client)
        # Use the ChatAgent directly with a simple run
        response = await joint_surgery_agent.run(question)
        
        # Extract the response text
        if response and hasattr(response, 'text'):
            return {"response": response.text}
        elif isinstance(response, str):
            return {"response": response}
        else:
            return {"response": str(response)}
            
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