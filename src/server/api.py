from fastapi import FastAPI
import os
import dotenv
from medical_emergency_agent import create_agent as create_emergency_agent
from agent_framework.azure import AzureOpenAIChatClient
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from copilotkit import CopilotKitRemoteEndpoint, Action as CopilotAction

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
med_emergency_agent = create_emergency_agent(chat_client)

# Initialize FastAPI app
app = FastAPI()

# Backend Actions.
# this is a dummy action for demonstration purposes, but will work in testing.
async def fetch_name_for_user_id(userId: str):
    # Replace with your database logic
    return {"name": "User_" + userId}

# this is the medical emergency action for demonstration purposes
async def ask_medical_emergency_agent(question: str):
    print("Received question in ask_medical_emergency_agent:", question)
    response = await med_emergency_agent.run(question)
    print("Medical Emergency Agent Response in action:", response)
    return {"response": response}


medical_emergency_action = CopilotAction(
    name="askMedicalEmergencyAgent",
    description="Send a question to the medical emergency agent and get a response of either 'EMERGENCY' or 'NOT_EMERGENCY'.",
    parameters=[
        {
            "name": "question",
            "type": "string",
            "description": "The medical question to ask the emergency agent.",
            "required": True,
        }
    ],
    handler=ask_medical_emergency_agent
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
sdk = CopilotKitRemoteEndpoint(actions=[userIdAction, medical_emergency_action]) 

# Add the CopilotKit endpoint to your FastAPI app
add_fastapi_endpoint(app, sdk, "/copilotkit_remote") 
def main():
    """Run the uvicorn server."""
    import uvicorn
    uvicorn.run("api:app", host="localhost", port=8000, reload=True)
if __name__ == "__main__":
    main()