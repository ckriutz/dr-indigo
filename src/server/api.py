import os
from typing import Any, Never
from workflow_agent_adapter import WorkflowAgentAdapter

from agent_framework import (
    AgentExecutorResponse,
    WorkflowBuilder,
    WorkflowContext,
    executor,
)
import dotenv
from fastapi import FastAPI

from agent_framework.azure import AzureOpenAIChatClient
from copilotkit import CopilotKitRemoteEndpoint, Action as CopilotAction
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from ag_ui_agent_framework import AgentFrameworkRunner, add_agent_framework_fastapi_endpoint

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

# Initialize AG-UI middleware endpoint
ag_ui_runner = AgentFrameworkRunner(WorkflowAgentAdapter(workflow))

# Add the CopilotKit endpoint to your FastAPI app
# add_fastapi_endpoint(app, sdk, "/copilotkit_remote") 
add_agent_framework_fastapi_endpoint(app, ag_ui_runner, "/agent-framework")
def main():
    """Run the uvicorn server."""
    import uvicorn
    uvicorn.run("api:app", host="localhost", port=8000, reload=True)
if __name__ == "__main__":
    main()