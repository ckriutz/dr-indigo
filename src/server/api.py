import os
import uuid
from typing import Any, Never
from datetime import datetime

from agent_framework import AgentExecutorRequest, AgentExecutorResponse, ChatMessage, Role, WorkflowBuilder, WorkflowContext, executor
import dotenv
from fastapi import FastAPI

from agent_framework.azure import AzureOpenAIChatClient
from copilotkit import CopilotKitRemoteEndpoint, Action as CopilotAction
from copilotkit.integrations.fastapi import add_fastapi_endpoint

from medical_triage_agent import create_executor_agent as create_triage_executor_agent, MedicalTriageResult
from joint_surgery_info_agent import create_executor_agent as create_joint_surgery_executor_agent
from memory_helper import MemoryHelper

# Load environment variables
dotenv.load_dotenv()

# Setup Langfuse observability - DISABLED to reduce console output
# Uncomment the following block to re-enable Langfuse telemetry

# try:
#     from agent_framework.observability import setup_observability
#     from langfuse import Langfuse
#     import httpx

#     # Check if certificate file exists, otherwise use default SSL verification
#     cert_path = os.path.join(os.path.dirname(__file__), "novant_ssl.cer")
    
#     if os.path.exists(cert_path):
#         print(f"✅ Using custom SSL certificate: {cert_path}")
#         os.environ["REQUESTS_CA_BUNDLE"] = cert_path
#         httpx_client = httpx.Client(verify=cert_path)
#     else:
#         print(f"⚠️  Certificate file {cert_path} not found.")
#         # You can choose one of these options:
#         # Option A: Use default SSL verification (recommended for production)
#         httpx_client = httpx.Client()  # Uses default CA bundle
#         # Option B: Disable SSL verification (only for development)
#         # httpx_client = httpx.Client(verify=False)
#         print("Using default SSL verification.")

#     # Initialize Langfuse with custom SSL configuration
#     langfuse = Langfuse(
#         secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
#         public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
#         host=os.environ.get("LANGFUSE_HOST"),
#         httpx_client=httpx_client

#     )
    
#     # Setup observability
#     setup_observability(enable_sensitive_data=True)
#     print("✅ Observability setup completed!")
    
#     # Verify Langfuse connection
#     try:
#         if langfuse.auth_check():
#             print("✅ Langfuse client authenticated and ready!")
#         else:
#             print("⚠️  Langfuse authentication failed")
#     except Exception as e:
#         print(f"⚠️  Langfuse auth check error: {e}")
    
# except ImportError as e:
#     print(f"⚠️  setup_observability not available. Error: {e}")
#     print("⚠️  Continuing without observability setup.")
#     langfuse = None


# Langfuse telemetry disabled - set to None
langfuse = None
print("ℹ️  Langfuse telemetry disabled to reduce console output")

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
joint_surgery_agent_executor_agent = create_joint_surgery_executor_agent(chat_client)

# Initialize the memory helper so we can store the conversation history in CosmosDB.
try:
    memory_helper = MemoryHelper()
    print("✓ MemoryHelper initialized successfully")
except Exception as e:
    print(f"✗ Failed to initialize MemoryHelper: {e}")
    print("Continuing with in-memory storage only...")
    memory_helper = None  # Set to None if initialization fails

# Now lets create a thread_id for conversation history storage. Set to None for new conversations.
# However, if the user gives us their name and birthday, we can use that to create a consistent thread id.
current_thread_id = None
conversation_threads = {}

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
    await ctx.yield_output(f"If you're experiencing a medical emergency, you should call 911 or go to the emergency room!")

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
    .add_edge(med_triage_agent_executor, joint_surgery_agent_executor_agent, condition=lambda msg: not condition_medical_guidance(msg) and not condition_medical_emergency(msg))
    .build()
)

# Initialize FastAPI app
app = FastAPI()

# Backend Actions.
# this is a dummy action for demonstration purposes, but will work in testing.
async def getUserAction(name: str, birthday: str):
    global current_thread_id
    
    # Replace with your database logic
    print("Received user information in getUserAction:", name, birthday)
    # remove any spaces from name and birthday for thread ID generation
    name = name.replace(" ", "_")
    birthday = birthday.replace(" ", "_")
    # Lets generate a threadId for this user based on that info.
    thread_id = f"user_{name}_{birthday}"
    print("Generated thread ID:", thread_id)
    
    # Store the thread ID globally for use in subsequent medical questions
    current_thread_id = thread_id
    
    # Use the memory helper if available
    if memory_helper is not None:
        conversation_threads = memory_helper.read_all_memory_for_thread(thread_id)
        print(f"Retrieved {len(conversation_threads)} messages for thread ID {thread_id}")
    else:
        conversation_threads = []

    return {"message": f"Thanks for the information! {name} how can I assist you further?"}

# this is the medical emergency action for demonstration purposes
async def ask_medical_question_workflow_agent(question: str, thread_id: str = None):
    global current_thread_id
    
    print("Received question in ask_medical_question_workflow_agent:", question)
    
    # Use the stored thread ID if no thread_id is provided
    if not thread_id and current_thread_id:
        thread_id = current_thread_id
        print(f"Using stored thread ID: {thread_id}")
    else:
        print("Thread ID:", thread_id)
    
    # Retrieve conversation history if thread_id provided
    messages = []
    if thread_id and memory_helper is not None:
        # Get conversation history from CosmosDB
        memory_data = memory_helper.read_memory(thread_id)
        if memory_data and "conversation_history" in memory_data:
            # Convert stored conversation history back to ChatMessage objects
            for msg in memory_data["conversation_history"]:
                role = Role.USER if msg["role"] == "user" else Role.ASSISTANT
                messages.append(ChatMessage(role, text=msg["content"]))
            print(f"Continuing conversation with {len(messages)} previous messages from CosmosDB")
    elif thread_id and thread_id in conversation_threads:
        # Fallback to in-memory storage
        messages = conversation_threads[thread_id].copy()
        print(f"Continuing conversation with {len(messages)} previous messages from memory")
    
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
    
    # Generate thread_id if this is a new conversation (and no stored one exists)
    if not thread_id:
        thread_id = str(uuid.uuid4())
        current_thread_id = thread_id  # Store it globally
        print(f"Created new thread: {thread_id}")
    
    # Store the conversation history
    messages.append(ChatMessage(Role.ASSISTANT, text=str(response)))
    
    # Store in CosmosDB if available
    if memory_helper is not None:
        # Convert ChatMessage objects to serializable format
        conversation_history = []
        for msg in messages:
            conversation_history.append({
                "role": "user" if msg.role == Role.USER else "assistant",
                "content": msg.text,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        memory_data = {
            "conversation_history": conversation_history,
            "thread_metadata": {
                "last_updated": datetime.utcnow().isoformat(),
                "message_count": len(conversation_history)
            }
        }
        
        success = memory_helper.write_memory(thread_id, memory_data)
        if not success:
            print(f"Failed to save conversation to CosmosDB for thread {thread_id}")
    
    # Also store in memory as fallback
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