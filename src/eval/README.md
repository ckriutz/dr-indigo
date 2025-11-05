# Dr. Indigo Agent Evaluation

This directory contains evaluation scripts for testing the Dr. Indigo medical assistant agent.

## Files

- `local_evaluation.py` - **Local evaluation script** that queries the running agent server via HTTP and saves results to JSON
- `langfuse_evaluation.py` - **Langfuse evaluation script** that pulls datasets from Langfuse and records experiment results
- `quick_test.py` - Simple test script to verify the agent is working (no LLM evaluation)
- `questions_answers.csv` - Local dataset of test questions and expected answers (for local_evaluation.py)
- `requirements.txt` - Additional Python dependencies needed for evaluation
- `.env` - Environment variables (Azure OpenAI, Langfuse credentials)

## Evaluation Approaches

There are two evaluation approaches available:

1. **Local Evaluation** (`local_evaluation.py`) - Uses local CSV dataset, saves results to JSON
2. **Langfuse Evaluation** (`langfuse_evaluation.py`) - Uses Langfuse datasets, records experiments in Langfuse

Both scripts query the running agent server via HTTP, which mirrors real-world usage.

## Local Evaluation

The `local_evaluation.py` script queries the running agent server via HTTP using a local CSV dataset.

### Prerequisites

1. **Start the Agent Server** - The server must be running before evaluation:
   ```bash
   cd ../server
   python api.py
   # Server should start at http://localhost:8000
   ```

2. **Install Evaluation Dependencies**:
   ```bash
   cd ../eval
   pip install -r requirements.txt
   ```

3. **Environment Variables** - Ensure your `.env` file in the server directory has Azure OpenAI credentials:
   ```
   AZURE_OPENAI_API_KEY=your_key
   AZURE_OPENAI_ENDPOINT=your_endpoint
   AZURE_OPENAI_DEPLOYMENT=your_deployment
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

### Quick Test

Before running the full evaluation, verify the agent is working:

```bash
# Test with direct endpoint (bypasses triage)
python quick_test.py

# Test with full workflow endpoint (includes triage)
python quick_test.py --endpoint /ask_workflow
```

This tests the agent with 3 sample questions without LLM evaluation.

### Usage

Run the evaluation script:

```bash
python local_evaluation.py
```

#### Options

- `--csv`: Path to CSV file (default: `questions_answers.csv`)
- `--output`: Path to save results JSON file (default: auto-generated with timestamp)
- `--n_items`: Limit number of items to evaluate (default: all items)
- `--max_workers`: Number of parallel workers (default: 5)
- `--endpoint`: API endpoint to use (default: `/ask`)
  - `/ask`: Direct to joint surgery agent (bypasses triage)
  - `/ask_workflow`: Full workflow with triage and routing

#### Examples

Evaluate all questions with direct endpoint:
```bash
python local_evaluation.py
```

Evaluate with full workflow:
```bash
python local_evaluation.py --endpoint /ask_workflow
```

Evaluate only first 5 questions:
```bash
python local_evaluation.py --n_items 5
```

Use 10 parallel workers for faster processing:
```bash
python local_evaluation.py --max_workers 10
```

Combine options:
```bash
python local_evaluation.py --n_items 10 --endpoint /ask_workflow --max_workers 3 --output workflow_test.json
```

### Output

The script produces:

1. **Console Output**: Progress bar and summary showing:
   - Total items evaluated
   - Number passed/failed
   - Pass rate percentage
   - Details of failed items

2. **JSON Results File**: Contains detailed results for each test case:
   ```json
   {
     "timestamp": "2025-11-04T10:30:00",
     "dataset_path": "questions_answers.csv",
     "total_items": 25,
     "passed": 23,
     "failed": 2,
     "pass_rate": 92.0,
     "results": [
       {
         "item_number": 1,
         "input": "I'm home, but I'm still in a good bit of pain...",
         "expected_output": "I'm sorry to hear you're uncomfortable...",
         "agent_response": "To manage your pain at home...",
         "score": 1,
         "pass": true,
         "explanation": "Response correctly addresses pain management..."
       }
     ]
   }
   ```
   
   See `sample_results.json` for a complete example.

### How It Works

1. **Server Connection**: Tests connection to the running FastAPI server
2. **Load Dataset**: Reads questions and expected answers from CSV
3. **Query Agent**: Sends HTTP POST requests to the CopilotKit endpoint for each question
4. **LLM Evaluation**: Uses Azure OpenAI to compare agent response with expected output
5. **Score Results**: Assigns pass/fail based on semantic similarity
6. **Generate Report**: Saves detailed results and prints summary

### Troubleshooting

**"Could not connect to server"**
- Make sure the server is running: `cd ../server && python api.py`
- Check the server URL matches (default is `http://localhost:8000`)
- Verify the server is accessible from your network

**"Request timed out"**
- The agent might be slow to respond
- Check server logs for errors
- Ensure Azure OpenAI is responding

**"Unparsed response"**
- The CopilotKit API response format might have changed
- Check the raw response in the error message
- Update the `query_agent()` function if needed

### CSV Format

The CSV file should have two columns:

```csv
input,expected_output
"Question text","Expected answer text"
```

See `questions_answers.csv` for examples.

## Evaluation Criteria

The LLM evaluator checks if the agent response:
- Addresses the user's question appropriately
- Provides accurate information based on the medical guide
- Cites the guide when appropriate (e.g., "Guide, p. 15")
- Directs emergency situations to call 911
- Politely declines out-of-scope questions

Responses don't need to match word-for-word but should convey the same key information.

## Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed or error occurred

This makes the script suitable for CI/CD pipelines.

## Langfuse Evaluation

The `langfuse_evaluation.py` script integrates with Langfuse for dataset management and experiment tracking. This is the recommended approach for production evaluations.

### Prerequisites

1. **Start the Agent Server** (same as local evaluation)

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Variables** - Ensure your `.env` file has:
   ```
   # Azure OpenAI (for agent and evaluation)
   AZURE_OPENAI_API_KEY=your_key
   AZURE_OPENAI_ENDPOINT=your_endpoint
   AZURE_OPENAI_DEPLOYMENT=gpt-4
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   
   # Langfuse
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_HOST=https://your-langfuse-instance.com
   
   # Agent Server (optional)
   AGENT_SERVER_URL=http://localhost:8000
   ```

4. **Create Dataset in Langfuse**:
   - Go to your Langfuse instance
   - Create a dataset named `joint_surgery_guide_faq`
   - Add dataset items with:
     - `input`: User question
     - `expected_output`: Expected answer

### Usage

Run experiments directly from the command line:

```bash
python langfuse_evaluation.py --experiment_name "Production Test"
```

#### Options

- `--experiment_name`: **Required** - Name of the experiment run (visible in Langfuse)
- `--dataset`: Dataset name in Langfuse (default: `joint_surgery_guide_faq`)
- `--endpoint`: API endpoint to use (default: `/ask`)
  - `/ask`: Direct to joint surgery agent (bypasses triage)
  - `/ask_workflow`: Full workflow with triage and routing
- `--max_concurrency`: Number of concurrent requests (default: 1)
- `--description`: Optional description for the experiment run

#### Examples

Basic experiment on direct endpoint:
```bash
python langfuse_evaluation.py --experiment_name "Direct Agent Test"
```

Test workflow with triage:
```bash
python langfuse_evaluation.py 
  --experiment_name "Workflow Test" 
  --endpoint /ask_workflow
```

Higher concurrency for faster processing:
```bash
python langfuse_evaluation.py 
  --experiment_name "Performance Test" 
  --max_concurrency 5 
  --description "Testing response times with parallel requests"
```

Use a different dataset:
```bash
python langfuse_evaluation.py 
  --experiment_name "Custom Dataset Test" 
  --dataset my_custom_dataset
```

### Features

The Langfuse evaluation provides:

1. **Automatic Tracing**: Each dataset item execution is traced in Langfuse
2. **Dataset Runs**: Experiments create dataset runs for easy comparison
3. **Multiple Evaluators**:
   - `accuracy`: LLM-based semantic comparison (pass/fail)
   - `response_time`: Time taken for each response
4. **Run-level Metrics**:
   - `avg_accuracy`: Average pass rate across all items
   - `avg_response_time`: Average, min, and max response times
5. **UI Comparison**: Compare different experiments side-by-side in Langfuse

### Output

The script displays:

1. **Console Output**: Progress and summary
   ```
   ================================================================================
   LANGFUSE EXPERIMENT: Production Test
   ================================================================================
   Dataset: joint_surgery_guide_faq
   Endpoint: /ask
   Server URL: http://localhost:8000
   Max Concurrency: 1
   ================================================================================
   
   Loading dataset 'joint_surgery_guide_faq' from Langfuse...
   ✅ Dataset loaded: 25 items found
   
   Running experiment...
   Processing items: 100%|███████████████████████| 25/25 [02:30<00:00]
   
   ================================================================================
   EXPERIMENT RESULTS
   ================================================================================
   Average Accuracy: 92.00%
   Average Response Time: 6.234s
   ================================================================================
   
   ✅ Experiment complete! View results in Langfuse: https://your-langfuse-instance.com
   ```

2. **Langfuse UI**: View detailed results in the Langfuse dashboard
   - Individual traces for each item
   - Scores and evaluations
   - Dataset run comparison
   - Aggregate metrics

### How It Works

1. **Initialize Langfuse**: Connects to Langfuse server with SSL certificate
2. **Load Dataset**: Fetches dataset items from Langfuse
3. **Run Experiment**: Uses `dataset.run_experiment()` with:
   - `task`: Function that queries the agent for each item
   - `evaluators`: Item-level evaluators (accuracy, response_time)
   - `run_evaluators`: Run-level evaluators (averages, aggregates)
4. **Record Results**: Automatically creates:
   - Traces for each execution
   - Scores for each evaluation
   - Dataset run for the full experiment
5. **Display Summary**: Shows key metrics in console and Langfuse link

### Comparing Experiments

In Langfuse UI, you can:
- Compare different experiment runs on the same dataset
- Track improvements over time
- Identify problematic questions
- Analyze response patterns

### Troubleshooting

**"Error loading dataset"**
- Verify the dataset exists in Langfuse
- Check the dataset name matches exactly
- Ensure Langfuse credentials are correct

**"Langfuse authentication failed"**
- Verify `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_HOST` in `.env`
- Check SSL certificate (`novant_ssl.cer`) is in the eval directory

**"Error querying agent"**
- Same as local evaluation troubleshooting
- Ensure the agent server is running
- Check server logs for errors

### Advantages over Local Evaluation

- **Centralized Storage**: Results stored in Langfuse, accessible to team
- **Experiment Tracking**: Compare runs over time
- **Dataset Management**: Datasets managed in Langfuse, not CSV files
- **Automatic Tracing**: Full observability of each execution
- **Team Collaboration**: Share results and insights with team
- **Production Ready**: Suitable for continuous evaluation pipelines

````
