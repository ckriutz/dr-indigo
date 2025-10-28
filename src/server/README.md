# Dr. Indigo Medical Agents

A FastAPI-based medical triage and information system powered by Azure OpenAI agents.

## Overview

This project implements a workflow-based medical agent system that:
- Triages medical questions to detect emergencies and provide appropriate routing
- Provides information about joint surgery procedures
- Uses CopilotKit for interactive agent actions

## Project Structure

- `api.py` - Main FastAPI application (run this to start the server)
- `main.py` - Testing script for workflow debugging
- `medical_triage_agent.py` - Medical triage agent implementation
- `joint_surgery_info_agent.py` - Joint surgery information agent
- `requirements.txt` - Python dependencies

## Setup

### Prerequisites

This project runs in a dev container, so no virtual environment (venv) setup is needed.

### Environment Configuration

1. **Copy the environment template:**
   ```bash
   cp .env.sample .env
   ```

2. **Configure your `.env` file with Azure OpenAI credentials:**

   ```bash
   AZURE_OPENAI_API_KEY=your-actual-api-key-here
   AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT=your-deployment-name
   ```

   **Example values:**
   - `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key (e.g., `abc123def456ghi789jkl012mno345pq`)
   - `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI resource endpoint (e.g., `https://my-openai-resource.openai.azure.com/`)
   - `AZURE_OPENAI_DEPLOYMENT`: The name of your deployed model (e.g., `gpt-4`, `gpt-35-turbo`, or `grok-3-mini`)

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Application

### Production Mode (FastAPI Server)

To start the FastAPI server:

```bash
python api.py
```

The server will start on `http://localhost:8000` with hot-reload enabled.

**Available endpoints:**
- `/copilotkit_remote` - CopilotKit remote endpoint for agent actions
- FastAPI automatic docs: `http://localhost:8000/docs`

### Testing Mode

To test the workflow directly without the API:

```bash
python main.py
```
This runs a standalone test of the medical triage workflow with debug output showing all workflow events.

### Docker Container

Building the container:
```bash
docker build --tag agent-api:v1.1 . 
```

Running the container:
```bash
docker run -d --name dr-indigo-server -p 8000:8000 --env-file ./.env agent-api:v1.2 
```
Checking container logs: 
```bash
docker logs dr-indigo-server
```
If the container is running successfully, the API will be available at the following urls for the: 
- Documentation
  - http://localhost:8000/docs
- CopilotKit Endpoint
  - http://localhost:8000/copilotkit_remote


Stopping the container:
```bash
docker stop dr-indigo-server
```
Deleting the container:
```bash
docker rm dr-indigo-server
```

## Features

### Medical Triage Workflow

The application uses a multi-agent workflow:

1. **Triage Agent** - Analyzes incoming medical questions to detect:
   - Medical emergencies (routes to emergency response)
   - Requests for medical advice (provides appropriate disclaimer)
   - General joint surgery questions (routes to surgery info agent)

2. **Joint Surgery Info Agent** - Provides information about joint surgery procedures

3. **CopilotKit Actions** - Two available actions:
   - `askMedicalQuestionAgent` - Send questions to the medical agent workflow
   - `replyGreeting` - Handle user greetings

## Development Notes

- Built with FastAPI and CopilotKit integration
- Uses Azure OpenAI for LLM capabilities
- Implements conditional workflow routing based on agent responses
- All agent responses are validated using Pydantic models