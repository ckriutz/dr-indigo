import {
    CopilotRuntime,
    OpenAIAdapter,
    copilotRuntimeNextJSAppRouterEndpoint,
} from '@copilotkit/runtime';
import { AzureOpenAI } from 'openai';
import { NextRequest } from 'next/server';
import { HttpAgent } from '@ag-ui/client';

// const remoteEndpoint = process.env["COPILOTKIT_REMOTE_ENDPOINT"] || "http://localhost:8000/copilotkit_remote";
const remoteEndpoint = "http://server:8000/agent";

let cachedServiceAdapter: OpenAIAdapter | null = null;

const resolveServiceAdapter = () => {
    if (cachedServiceAdapter) return cachedServiceAdapter;

    const apiKey = process.env["AZURE_OPENAI_API_KEY"];
    const resource = process.env["AZURE_OPENAI_RESOURCE"];
    const endpoint = process.env["AZURE_OPENAI_ENDPOINT"];
    const deployment = process.env["AZURE_OPENAI_DEPLOYMENT"];
    const apiVersion = process.env["AZURE_OPENAI_API_VERSION"] || "2024-04-01-preview";

    if (!apiKey) throw new Error("The AZURE_OPENAI_API_KEY environment variable is missing or empty.");
    if (!resource) throw new Error("The AZURE_OPENAI_RESOURCE environment variable is missing or empty.");
    if (!deployment) throw new Error("The AZURE_OPENAI_DEPLOYMENT environment variable is missing or empty.");

    const azureOpenAI = new AzureOpenAI({
        apiKey,
        endpoint: endpoint || `https://${resource}.openai.azure.com/`,
        deployment,
        apiVersion,
    });

    cachedServiceAdapter = new OpenAIAdapter({
        openai: azureOpenAI as any,
        model: deployment,
    });

    return cachedServiceAdapter;
};

const careNavigatorAgent = new HttpAgent({
    agentId: "care-navigator",
    description: "Routes medical queries through the server-side triage workflow.",
    url: remoteEndpoint,
});

const runtime = new CopilotRuntime({
    // remoteEndpoints: [
    //     { url: remoteActionsEndpoint },
    // ],
    agents: {
        "care-navigator": careNavigatorAgent,
    },
    onError: (error) => {
        console.error("Copilot Runtime Error:", error);
    }
});

export const POST = async (req: NextRequest) => {
    const serviceAdapter = resolveServiceAdapter();
    const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
        runtime,
        serviceAdapter,
        endpoint: '/api/copilotkit',
    });
    return handleRequest(req);
};