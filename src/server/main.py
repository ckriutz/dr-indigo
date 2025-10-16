import asyncio
import dotenv
import os
from medical_emergency_agent import create_agent as create_emergency_agent
#from joint_surgery_info_agent import create_agent as create_joint_surgery_agent
from agent_framework.azure import AzureOpenAIChatClient

# Configuration
dotenv.load_dotenv()
api_key =  os.environ.get("AZURE_OPENAI_API_KEY")
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")

chat_client = AzureOpenAIChatClient(
    api_key=api_key,
    endpoint=endpoint,
    deployment_name=deployment,
)

async def main():
    question = "What should I eat before a knee replacement surgery?"
    med_emergency_agent = create_emergency_agent(chat_client)
    response = await med_emergency_agent.run(question)
    print("Medical Emergency Agent Response:", response)

    #joint_surgery_agent = create_joint_surgery_agent(chat_client)
    #response = await joint_surgery_agent.run(question)
    #print("Joint Surgery Information Agent Response:", response)

if __name__ == "__main__":
    asyncio.run(main())