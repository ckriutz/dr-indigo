import {
  CopilotRuntime,
  OpenAIAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from '@copilotkit/runtime';
import OpenAI from 'openai';
import { NextRequest } from 'next/server';
const apiKey = process.env["AZURE_OPENAI_API_KEY"];
const resource = process.env["AZURE_OPENAI_RESOURCE"];
const deployment = process.env["AZURE_OPENAI_DEPLOYMENT"];
const apiVersion = process.env["AZURE_OPENAI_API_VERSION"] || "2024-04-01-preview";

if (!apiKey) throw new Error("The AZURE_OPENAI_API_KEY environment variable is missing or empty.");
if (!resource) throw new Error("The AZURE_OPENAI_RESOURCE environment variable is missing or empty.");
if (!deployment) throw new Error("The AZURE_OPENAI_DEPLOYMENT environment variable is missing or empty.");

const openai = new OpenAI({
  apiKey,
  baseURL: `https://${resource}.openai.azure.com/openai/deployments/${deployment}`,
  defaultQuery: { "api-version": apiVersion },
  defaultHeaders: { "api-key": apiKey },
});
const serviceAdapter = new OpenAIAdapter({ openai });
const runtime = new CopilotRuntime({
    // ...existing configuration
    remoteEndpoints: [
        { url: "http://localhost:8000/copilotkit_remote" },
    ],
});
export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: '/api/copilotkit',
  });
  return handleRequest(req);
};