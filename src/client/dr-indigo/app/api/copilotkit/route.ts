import {
    CopilotRuntime,
    OpenAIAdapter,
    copilotRuntimeNextJSAppRouterEndpoint,
} from '@copilotkit/runtime';
import { HttpAgent } from '@ag-ui/client';
import { AzureOpenAI } from 'openai';
import { NextRequest } from 'next/server';

const apiKey = process.env["AZURE_OPENAI_API_KEY"];
const resource = process.env["AZURE_OPENAI_RESOURCE"];
const endpoint = process.env["AZURE_OPENAI_ENDPOINT"];
const deployment = process.env["AZURE_OPENAI_DEPLOYMENT"];
const apiVersion = process.env["AZURE_OPENAI_API_VERSION"] || "2024-04-01-preview";
// const remoteActionsEndpoint = process.env["COPILOTKIT_REMOTE_ENDPOINT"] || "http://localhost:8000/copilotkit_remote";
const agentFrameworkEndpoint = process.env["AGENT_FRAMEWORK_ENDPOINT"] || "http://localhost:8000/agent-framework";

if (!apiKey) throw new Error("The AZURE_OPENAI_API_KEY environment variable is missing or empty.");
if (!resource) throw new Error("The AZURE_OPENAI_RESOURCE environment variable is missing or empty.");
if (!deployment) throw new Error("The AZURE_OPENAI_DEPLOYMENT environment variable is missing or empty.");

const azureOpenAI = new AzureOpenAI({
    apiKey,
    endpoint: endpoint || `https://${resource}.openai.azure.com/`,
    deployment: deployment,
    apiVersion,
});

const serviceAdapter = new OpenAIAdapter({
    openai: azureOpenAI as any,
    model: deployment,
});

const careNavigationWorkflowAgent = new HttpAgent({
    agentId: "care-navigation-workflow",
    description: "Routes medical queries through the server-side triage workflow.",
    url: agentFrameworkEndpoint,
});
    
const runtime = new CopilotRuntime({
    // remoteEndpoints: [
    //     { url: remoteActionsEndpoint },
    // ],
    agents: {
        "care-navigation-workflow": careNavigationWorkflowAgent,
    },
    onError: (error) => {
        console.error("Copilot Runtime Error:", error);
    }
});
export const POST = async (req: NextRequest) => {
    const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
        runtime,
        serviceAdapter,
        endpoint: '/api/copilotkit',
    });
    return handleRequest(req);
};