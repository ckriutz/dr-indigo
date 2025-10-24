This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://github.com/vercel/next.js/tree/canary/packages/create-next-app).

## Environment Setup

Before running the development server, you need to configure your environment variables:

1. **Rename `.env.sample` to `.env`** in the project root directory
2. **Update the environment variables** with your Azure OpenAI configuration

The environment variables are used in `app/api/copilotkit/route.ts` to configure the CopilotKit runtime with Azure OpenAI.

### Environment Variables Example

Create a `.env` file with the following variables:

```bash
AZURE_OPENAI_API_KEY=your-azure-openai-api-key
AZURE_OPENAI_RESOURCE=your-resource-name
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-04-01-preview
COPILOTKIT_REMOTE_ENDPOINT=http://localhost:8000/copilotkit_remote
```

**Variable Descriptions:**
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key (required)
- `AZURE_OPENAI_RESOURCE`: Your Azure resource name (required)
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL (optional - defaults to https://{resource}.openai.azure.com/)
- `AZURE_OPENAI_DEPLOYMENT`: Your deployment name (required)
- `AZURE_OPENAI_API_VERSION`: API version for Azure OpenAI (optional - defaults to 2024-04-01-preview)
- `COPILOTKIT_REMOTE_ENDPOINT`: Remote endpoint for CopilotKit (optional - defaults to http://localhost:8000/copilotkit_remote)

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.js`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Docker

Docker deployment configuration is planned. (TBD)
