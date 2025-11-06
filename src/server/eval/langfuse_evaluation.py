"""
Langfuse Evaluation Script for Dr. Indigo Agent

This script pulls the 'joint_surgery_guide_faq' dataset from Langfuse,
runs experiments against the Dr. Indigo agent, and records results back to Langfuse.

Usage:
    python langfuse_evaluation.py --experiment_name "Production Test" --endpoint /ask
    python langfuse_evaluation.py --experiment_name "Workflow Test" --endpoint /ask_workflow --max_concurrency 5
"""

import os
import argparse
import time
import ssl
import warnings
from typing import Dict
from threading import Lock
import httpx
import requests
from dotenv import load_dotenv
from langfuse import Langfuse, Evaluation
from openai import AzureOpenAI
from tqdm import tqdm

# Suppress SSL warnings if we're using custom certificate
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Load environment variables
load_dotenv()

# Configuration
SERVER_URL = os.getenv("AGENT_SERVER_URL", "http://localhost:8000")
DEFAULT_ENDPOINT = "/ask"
DATASET_NAME = "joint_surgery_guide_faq"

# Get absolute path to SSL certificate
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_PATH = os.path.join(SCRIPT_DIR, "novant_ssl.cer")

# Configure SSL for Langfuse (both OTEL and HTTPX)
if os.path.exists(CERT_PATH):
    # Set environment variable for OpenTelemetry span exporter
    os.environ["OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE"] = CERT_PATH
    print(f"✅ SSL certificate configured for Langfuse: {CERT_PATH}")
    
    # Create HTTPX client with certificate for Langfuse API requests
    httpx_client = httpx.Client(verify=CERT_PATH)
else:
    print(f"⚠️  Warning: SSL certificate not found at {CERT_PATH}")
    print("Note: Langfuse connections may fail with SSL errors")
    httpx_client = httpx.Client()

# Initialize Langfuse client
print("Initializing Langfuse client...")

langfuse = Langfuse(
    secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
    public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
    host=os.environ.get("LANGFUSE_HOST"),
    httpx_client=httpx_client
)

# Verify Langfuse connection
try:
    if langfuse.auth_check():
        print("✅ Langfuse client authenticated and ready!")
    else:
        print("⚠️  Langfuse authentication failed")
except Exception as e:
    print(f"⚠️  Langfuse auth check error: {e}")

# Initialize Azure OpenAI client for LLM-based evaluation
print("Initializing Azure OpenAI client for evaluation...")
llm_client = AzureOpenAI(
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
)


def agent_task(*, item, endpoint: str, **kwargs) -> Dict[str, any]:
    """
    Task function that queries the Dr. Indigo agent.
    
    This function is called by the Langfuse experiment runner for each dataset item.
    
    Args:
        item: Dataset item from Langfuse (has .input and .expected_output attributes)
        endpoint: API endpoint to use (/ask or /ask_workflow)
        **kwargs: Additional arguments passed by the experiment runner
        
    Returns:
        Dictionary with 'response' and 'response_time' keys
    """
    question = item.input
    
    try:
        url = f"{SERVER_URL}{endpoint}"
        payload = {"question": question}
        
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=120)
        response_time = time.time() - start_time
        
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict) and "response" in data:
            response_text = data["response"]
        elif isinstance(data, dict) and "error" in data:
            response_text = f"Error from server: {data['error']}"
        else:
            response_text = str(data)
        
        return {
            "response": response_text,
            "response_time": response_time
        }
        
    except Exception as e:
        response_time = time.time() - start_time if 'start_time' in locals() else 0
        return {
            "response": f"Error: {str(e)}",
            "response_time": response_time
        }


def accuracy_evaluator(*, input, output, expected_output, metadata, **kwargs) -> Evaluation:
    """
    Evaluator that uses an LLM to compare the agent's response with the expected output.
    
    Args:
        input: The user's input question
        output: Dictionary with 'response' and 'response_time' from agent_task
        expected_output: Expected response from the dataset
        metadata: Additional metadata from the dataset item
        **kwargs: Additional arguments
        
    Returns:
        Evaluation object with score (1 for pass, 0 for fail) and explanation
    """
    # Extract the response text from the output dictionary
    response = output.get("response", "") if isinstance(output, dict) else str(output)
    
    prompt = f"""You are an expert evaluator for a medical guidance chatbot that helps patients with total joint replacement recovery.

Compare the agent's response to the expected response for semantic equivalence. The responses don't need to match word-for-word, but should convey the same medical guidance and key information.

Consider a response CORRECT if it:
1. Provides the same core medical advice or information
2. Mentions the same key steps, timeframes, or precautions
3. Maintains the same level of care and safety (e.g., "call your doctor" conditions)

Consider a response INCORRECT if it:
1. Provides contradictory medical advice
2. Omits critical safety information
3. Gives significantly different guidance
4. Is an error message or refuses to help when it should answer

User Question: {input}

Expected Response: {expected_output}

Agent Response: {response}

Respond with ONLY 'PASS' or 'FAIL' followed by a brief explanation.
"""

    try:
        completion = llm_client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=1.0
        )
        
        llm_response = completion.choices[0].message.content.strip()
        
        # Parse the response
        if llm_response.upper().startswith("PASS"):
            score = 1.0
            explanation = llm_response[4:].strip()
        elif llm_response.upper().startswith("FAIL"):
            score = 0.0
            explanation = llm_response[4:].strip()
        else:
            # Fallback parsing
            score = 1.0 if "PASS" in llm_response.upper() else 0.0
            explanation = llm_response
        
        return Evaluation(
            name="accuracy",
            value=score,
            comment=explanation if explanation else llm_response
        )
        
    except Exception as e:
        return Evaluation(
            name="accuracy",
            value=0.0,
            comment=f"Evaluation error: {str(e)}"
        )


def response_time_evaluator(*, input, output, expected_output, metadata, **kwargs) -> Evaluation:
    """
    Evaluator that records the response time as a score.
    
    Args:
        input: The user's input question
        output: Dictionary with 'response' and 'response_time' from agent_task
        expected_output: Expected response from the dataset
        metadata: Additional metadata from the dataset item
        **kwargs: Additional arguments
        
    Returns:
        Evaluation object with response time in seconds
    """
    response_time = output.get("response_time", 0.0) if isinstance(output, dict) else 0.0
    
    return Evaluation(
        name="response_time",
        value=response_time,
        comment=f"Response time: {response_time:.3f} seconds"
    )


def average_accuracy_evaluator(*, item_results, **kwargs) -> Evaluation:
    """
    Run-level evaluator that calculates average accuracy across all items.
    
    Args:
        item_results: List of results from each item in the experiment
        **kwargs: Additional arguments
        
    Returns:
        Evaluation object with average accuracy score
    """
    accuracies = [
        eval.value
        for result in item_results
        for eval in result.evaluations
        if eval.name == "accuracy"
    ]
    
    if not accuracies:
        return Evaluation(
            name="avg_accuracy",
            value=None,
            comment="No accuracy scores found"
        )
    
    avg = sum(accuracies) / len(accuracies)
    passed = sum(1 for a in accuracies if a == 1.0)
    total = len(accuracies)
    
    return Evaluation(
        name="avg_accuracy",
        value=avg,
        comment=f"Average accuracy: {avg:.2%} ({passed}/{total} passed)"
    )


def average_response_time_evaluator(*, item_results, **kwargs) -> Evaluation:
    """
    Run-level evaluator that calculates average response time across all items.
    
    Args:
        item_results: List of results from each item in the experiment
        **kwargs: Additional arguments
        
    Returns:
        Evaluation object with average response time
    """
    response_times = [
        eval.value
        for result in item_results
        for eval in result.evaluations
        if eval.name == "response_time"
    ]
    
    if not response_times:
        return Evaluation(
            name="avg_response_time",
            value=None,
            comment="No response time scores found"
        )
    
    avg_time = sum(response_times) / len(response_times)
    min_time = min(response_times)
    max_time = max(response_times)
    
    return Evaluation(
        name="avg_response_time",
        value=avg_time,
        comment=f"Avg: {avg_time:.3f}s, Min: {min_time:.3f}s, Max: {max_time:.3f}s"
    )


def run_experiment(
    experiment_name: str,
    dataset_name: str = DATASET_NAME,
    endpoint: str = DEFAULT_ENDPOINT,
    max_concurrency: int = 1,
    run_description: str = None
):
    """
    Run an experiment on the Langfuse dataset.
    
    Args:
        experiment_name: Name of the experiment run
        dataset_name: Name of the Langfuse dataset to use
        endpoint: API endpoint to query (/ask or /ask_workflow)
        max_concurrency: Maximum number of concurrent requests
        run_description: Optional description for the experiment run
    """
    print(f"\n{'='*80}")
    print(f"LANGFUSE EXPERIMENT: {experiment_name}")
    print(f"{'='*80}")
    print(f"Dataset: {dataset_name}")
    print(f"Endpoint: {endpoint}")
    print(f"Server URL: {SERVER_URL}")
    print(f"Max Concurrency: {max_concurrency}")
    print(f"{'='*80}\n")
    
    # Get dataset from Langfuse
    print(f"Loading dataset '{dataset_name}' from Langfuse...")
    try:
        dataset = langfuse.get_dataset(dataset_name)
        print(f"✅ Dataset loaded: {len(dataset.items)} items found\n")
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        print(f"Make sure the dataset '{dataset_name}' exists in Langfuse.")
        return
    
    # Create progress bar
    total_items = len(dataset.items)
    progress_bar = tqdm(total=total_items, desc="Processing items", unit="item")
    progress_lock = Lock()
    
    # Wrapper function to track progress
    def task_with_progress(*, item, **kwargs):
        try:
            result = agent_task(item=item, endpoint=endpoint, **kwargs)
            return result
        finally:
            with progress_lock:
                progress_bar.update(1)
    
    # Run experiment
    print("Running experiment...")
    result = dataset.run_experiment(
        name=experiment_name,
        description=run_description or f"Testing Dr. Indigo agent with endpoint {endpoint}",
        task=task_with_progress,
        evaluators=[accuracy_evaluator, response_time_evaluator],
        run_evaluators=[average_accuracy_evaluator, average_response_time_evaluator],
        max_concurrency=max_concurrency,
        metadata={
            "endpoint": endpoint,
            "server_url": SERVER_URL,
            "agent": "dr-indigo"
        }
    )
    
    # Close progress bar
    progress_bar.close()
    
    # Flush to ensure all data is sent to Langfuse
    langfuse.flush()
    
    # Display results
    print("\n" + "="*80)
    print("EXPERIMENT RESULTS")
    print("="*80)
    print(result.format())
    
    # Extract key metrics
    avg_accuracy = None
    avg_response_time = None
    
    for eval in result.run_evaluations:
        if eval.name == "avg_accuracy":
            avg_accuracy = eval.value
        elif eval.name == "avg_response_time":
            avg_response_time = eval.value
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    if avg_accuracy is not None:
        print(f"Average Accuracy: {avg_accuracy:.2%}")
    if avg_response_time is not None:
        print(f"Average Response Time: {avg_response_time:.3f}s")
    print("="*80)
    
    print(f"\n✅ Experiment complete! View results in Langfuse: {os.environ.get('LANGFUSE_HOST')}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Run Langfuse experiment on Dr. Indigo agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run experiment on /ask endpoint
  python langfuse_evaluation.py --experiment_name "Direct Agent Test"
  
  # Run experiment on /ask_workflow endpoint with more concurrency
  python langfuse_evaluation.py --experiment_name "Workflow Test" --endpoint /ask_workflow --max_concurrency 5
  
  # Use a different dataset
  python langfuse_evaluation.py --experiment_name "Custom Test" --dataset my_dataset
        """
    )
    
    parser.add_argument(
        "--experiment_name",
        type=str,
        required=True,
        help="Name of the experiment run (will be visible in Langfuse)"
    )
    
    parser.add_argument(
        "--dataset",
        type=str,
        default=DATASET_NAME,
        help=f"Name of the Langfuse dataset to use (default: {DATASET_NAME})"
    )
    
    parser.add_argument(
        "--endpoint",
        type=str,
        choices=["/ask", "/ask_workflow"],
        default=DEFAULT_ENDPOINT,
        help=f"API endpoint to query (default: {DEFAULT_ENDPOINT})"
    )
    
    parser.add_argument(
        "--max_concurrency",
        type=int,
        default=1,
        help="Maximum number of concurrent requests (default: 1)"
    )
    
    parser.add_argument(
        "--description",
        type=str,
        default=None,
        help="Optional description for the experiment run"
    )
    
    args = parser.parse_args()
    
    # Validate environment variables
    required_vars = [
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_HOST",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set them in your .env file.")
        return
    
    # Run the experiment
    run_experiment(
        experiment_name=args.experiment_name,
        dataset_name=args.dataset,
        endpoint=args.endpoint,
        max_concurrency=args.max_concurrency,
        run_description=args.description
    )


if __name__ == "__main__":
    main()
