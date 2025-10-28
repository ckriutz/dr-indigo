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
joint_surgery_agent_executor = create_joint_surgery_executor_agent(chat_client)
joint_surgery_agent = create_joint_surgery_agent(chat_client)

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

# Wrapper executor for joint surgery agent that yields output
@executor(id="joint_surgery_agent_with_output")
async def joint_surgery_with_output(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    print("Joint surgery agent response:", response)
    # Extract the actual response text and yield it as output
    await ctx.yield_output(response.agent_run_response.text)

# Here is our workflow definition.
workflow = (
    WorkflowBuilder()
    .set_start_executor(med_triage_agent_executor)
    # Start by short circuiting medical emergencies and medical advice.
    .add_edge(med_triage_agent_executor, handle_emergency, condition=lambda msg: condition_medical_emergency(msg))
    .add_edge(med_triage_agent_executor, handle_medical_guidance, condition=lambda msg: not condition_medical_emergency(msg) and condition_medical_guidance(msg))
    # So for this edge, it's not a medical emergency, or medical guidance, and we can move it to the joint surgery agent.
    .add_edge(med_triage_agent_executor, joint_surgery_agent, condition=lambda msg: not condition_medical_guidance(msg) and not condition_medical_emergency(msg))
    # Joint surgery agent needs to yield output
    .add_edge(joint_surgery_agent, joint_surgery_with_output)
    .build()
)

# Initialize FastAPI app
app = FastAPI()

# In-memory conversation history storage
# In production, replace with a database (Redis, PostgreSQL, etc.)
conversation_threads = {}

# Backend Actions.
# this is a dummy action for demonstration purposes, but will work in testing.
async def getUserAction(name: str, birthday: str):
    # Replace with your database logic
    print("Received user information in getUserAction:", name, birthday)
    return {"Thanks for the information! {name} how can I assist you further?"}

# this is the medical emergency action for demonstration purposes
async def ask_medical_question_workflow_agent(question: str, thread_id: str = None):
    print("Received question in ask_medical_question_workflow_agent:", question)
    print("Thread ID:", thread_id)
    
    # Retrieve conversation history if thread_id provided
    messages = []
    if thread_id and thread_id in conversation_threads:
        messages = conversation_threads[thread_id].copy()
        print(f"Continuing conversation with {len(messages)} previous messages")
    
    # Add the new user message
    messages.append(ChatMessage(Role.USER, text=question))
    
    # Create request with full conversation history
    request = AgentExecutorRequest(
        messages=messages, 
        should_respond=True
    )
    events = await workflow.run(request)
    outputs = events.get_outputs()
    response = outputs[-1]
    
    # Generate thread_id if this is a new conversation
    if not thread_id:
        import uuid
        thread_id = str(uuid.uuid4())
        print(f"Created new thread: {thread_id}")
    
    # Store the conversation history (user message + assistant response)
    messages.append(ChatMessage(Role.ASSISTANT, text=str(response)))
    conversation_threads[thread_id] = messages
    
    print("Medical Question Agent Response in action:", response)
    print("Thread ID for next request:", thread_id)
    print(f"Conversation now has {len(messages)} messages")
    
    return response


medical_question_action = CopilotAction(
    name="askMedicalQuestionAgent",
    description="Send a question to the medical question agent and get a response.",
    parameters=[
        {
            "name": "question",
            "type": "string",
            "description": "The medical question to ask the question agent.",
            "required": True,
        },
        {
            "name": "thread_id",
            "type": "string",
            "description": "Optional thread ID to continue an existing conversation. If not provided, a new thread will be created.",
            "required": False,
        }
    ],
    handler=ask_medical_question_workflow_agent
)

# Greeting Action
getUserAction = CopilotAction(
    name="getUser",
    description="When the user provides their name and birthday, extract this information for further use. Do not reply to any other types of messages.",
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
        }
    ],
    handler=getUserAction
)


# Initialize the CopilotKit SDK
sdk = CopilotKitRemoteEndpoint(actions=[getUserAction, medical_question_action])

# Add the CopilotKit endpoint to your FastAPI app
add_fastapi_endpoint(app, sdk, "/copilotkit_remote") 
def main():
    """Run the uvicorn server."""
    import uvicorn
    uvicorn.run("api:app", host="localhost", port=8000, reload=True)
if __name__ == "__main__":
    main()