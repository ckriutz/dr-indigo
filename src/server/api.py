import os
from typing import Any, Never

from agent_framework import AgentExecutorRequest, AgentExecutorResponse, ChatMessage, Role, WorkflowBuilder, WorkflowContext, executor
import dotenv
from fastapi import FastAPI

from agent_framework.azure import AzureOpenAIChatClient
from copilotkit import CopilotKitRemoteEndpoint, Action as CopilotAction
from copilotkit.integrations.fastapi import add_fastapi_endpoint

from medical_emergency_agent import create_agent as create_emergency_agent, IsMedicalEmergencyResult
from medical_emergency_agent import create_executor_agent as create_emergency_executor_agent
from joint_surgery_info_agent import create_agent as create_joint_surgery_agent
from joint_surgery_info_agent import create_executor_agent as create_joint_surgery_executor_agent
from medical_guidance_agent import create_agent as create_medical_guidance_executor_agent, IsMedicalGuidanceResult

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
med_emergency_agent_executor = create_emergency_executor_agent(chat_client)
medical_guidance_executor_agent = create_medical_guidance_executor_agent(chat_client)
joint_surgery_agent_executor_agent = create_joint_surgery_executor_agent(chat_client)

# Lets make sure the json returned is valid, and route based on the boolean value.
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


# Lets make sure the json returned is valid, and route based on the boolean value.
def condition_medical_guidance(message: Any) -> bool:
    # Defensive guard. If a non AgentExecutorResponse appears, let the edge pass to avoid dead ends.
    if not isinstance(message, AgentExecutorResponse):
        return True
    try:
        detection = IsMedicalGuidanceResult.model_validate_json(message.agent_run_response.text)
        return not detection.is_medical_guidance
    except Exception:
        return False
    
# So this is just a simple handler that replies with emergency instructions.
# No LLM needed, and whatever we put in here is what the workflow will output.
@executor(id="reply_emergency")
async def handle_emergency(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    await ctx.yield_output(f"Yo, you should call 911 or go to the emergency room!")

# So this is just a simple handler that replies with medical guidance instructions.
# No LLM needed, and whatever we put in here is what the workflow will output.
@executor(id="reply_medical_guidance")
async def handle_medical_guidance(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    await ctx.yield_output(f"Sadly, I can't help with giving medical advice. Please consult a healthcare professional for guidance.")

# Here is our workflow definition.
workflow = (
    WorkflowBuilder()
    .set_start_executor(med_emergency_agent_executor)
    # Start by short circuiting medical emergencies.
    .add_edge(med_emergency_agent_executor, handle_emergency, condition=lambda msg: not condition_medical_emergency(msg))
    # At this point, we know it's NOT a medical emergency. Lets make sure it's not a medical question.
    .add_edge(med_emergency_agent_executor, medical_guidance_executor_agent, condition=condition_medical_emergency)
    .add_edge(medical_guidance_executor_agent, handle_medical_guidance, condition=lambda msg: not condition_medical_guidance(msg))
    # So for this edge, it's not a medical emergency, or medical guidance, and we can move it to the joint surgery agent.
    .add_edge(medical_guidance_executor_agent, joint_surgery_agent_executor_agent, condition=condition_medical_guidance)
    .build()
)

# Initialize FastAPI app
app = FastAPI()

# Backend Actions.
# this is a dummy action for demonstration purposes, but will work in testing.
async def fetch_name_for_user_id(userId: str):
    # Replace with your database logic
    return {"name": "User_" + userId}

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

userIdAction = CopilotAction(
    name="fetchNameForUserId",
    description="Fetches user name from the database for a given ID.",
    parameters=[
        {
            "name": "userId",
            "type": "string",
            "description": "The ID of the user to fetch data for.",
            "required": True,
        }
    ],
    handler=fetch_name_for_user_id
)
# Initialize the CopilotKit SDK
sdk = CopilotKitRemoteEndpoint(actions=[userIdAction, medical_question_action]) 

# Add the CopilotKit endpoint to your FastAPI app
add_fastapi_endpoint(app, sdk, "/copilotkit_remote") 
def main():
    """Run the uvicorn server."""
    import uvicorn
    uvicorn.run("api:app", host="localhost", port=8000, reload=True)
if __name__ == "__main__":
    main()