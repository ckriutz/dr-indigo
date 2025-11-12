# Dr. Indigo Development Container

This development container is configured with all the necessary dependencies for the Dr. Indigo medical agents project, including an updated SQLite version required for ChromaDB compatibility.

## What's Included

- **Python 3.12** - Latest Python runtime
- **SQLite 3.46.1** - Updated SQLite version (ChromaDB requires >= 3.35.0)
- **Development tools** - Python extensions, linters, and formatters
- **Port forwarding** - Port 8000 automatically forwarded for the FastAPI server

## SQLite Fix for ChromaDB

The base devcontainer image includes SQLite 3.34.1, but ChromaDB requires SQLite >= 3.35.0. This container automatically:

1. Downloads and builds SQLite 3.46.1 from source
2. Installs it to `/usr/local/lib` and `/usr/local/bin`
3. Sets up the correct library path (`LD_LIBRARY_PATH`)
4. Verifies ChromaDB compatibility during container setup

## Quick Start

1. **Open in devcontainer** - VS Code will automatically detect and offer to reopen in the container
2. **Wait for setup** - The `postCreateCommand` will install dependencies and verify the setup
3. **Verify installation** - Run the verification script:
   ```bash
   ./.devcontainer/verify-setup.sh
   ```

## Container Features

### Environment Variables
- `LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH` - Points to updated SQLite
- `PATH=/usr/local/bin:$PATH` - Includes updated SQLite binary

### VS Code Extensions
- Python language support
- Pylint for code analysis
- Black formatter for code formatting
- isort for import sorting

### Port Forwarding
- Port 8000 is automatically forwarded for the FastAPI development server

## Troubleshooting

If you encounter SQLite version issues:

1. **Check the setup**:
   ```bash
   ./.devcontainer/verify-setup.sh
   ```

2. **Verify SQLite version**:
   ```bash
   python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
   ```

3. **Test ChromaDB**:
   ```bash
   python3 -c "import chromadb; print('Success!')"
   ```

4. **Rebuild container** - If issues persist, rebuild the devcontainer:
   - Command Palette → "Dev Containers: Rebuild Container"

## Running the Application

Once the container is set up:

```bash
# Install dependencies (if not already done by postCreateCommand)
pip install -e .

# Run the FastAPI server
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Or test the workflow directly
python main.py
```

The server will be available at `http://localhost:8000` with automatic reload enabled for development.