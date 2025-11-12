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

This project is designed to run in a development container with all dependencies pre-configured.

**Important**: The devcontainer includes an updated SQLite version (3.46.1) required for ChromaDB compatibility. The base devcontainer image only includes SQLite 3.34.1, which is incompatible with ChromaDB >= 1.3.3.

### Development Container Setup

1. **Open in VS Code**: Open this project in VS Code
2. **Reopen in Container**: When prompted, click "Reopen in Container" or use Command Palette → "Dev Containers: Reopen in Container"
3. **Wait for Setup**: The container will build and install dependencies automatically
4. **Verify Setup**: Run the verification script:
   ```bash
   ./.devcontainer/verify-setup.sh
   ```

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

### SQLite Compatibility Note

If you encounter the error `RuntimeError: Your system has an unsupported version of sqlite3. Chroma requires sqlite3 >= 3.35.0`, this indicates you're not using the development container. The devcontainer automatically handles this by including SQLite 3.46.1.

**Solutions:**
- **Recommended**: Use the development container (see above)
- **Manual fix**: See `.devcontainer/README.md` for manual SQLite installation instructions

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