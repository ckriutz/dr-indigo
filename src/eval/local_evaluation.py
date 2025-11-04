"""
Local evaluation script for Dr. Indigo agent.
Reads questions and answers from a CSV file and evaluates agent responses locally.
"""

import os
import csv
import json
import sys
import argparse
from typing import List, Dict, Tuple
from datetime import datetime
from tqdm import tqdm
import requests
import dotenv
from openai import AzureOpenAI

# Load environment variables
dotenv.load_dotenv()

# Server configuration
SERVER_URL = os.getenv("AGENT_SERVER_URL", "http://localhost:8000")

def load_csv_dataset(csv_path: str) -> List[Dict[str, str]]:
    """
    Load questions and expected answers from a CSV file.
    
    Args:
        csv_path: Path to the CSV file containing 'input' and 'expected_output' columns
        
    Returns:
        List of dictionaries with 'input' and 'expected_output' keys
    """
    dataset = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dataset.append({
                'input': row['input'],
                'expected_output': row['expected_output']
            })
    return dataset

def query_agent(question: str) -> str:
    """
    Query the Dr. Indigo agent via HTTP using the /ask endpoint.
    
    Args:
        question: The user's question
        
    Returns:
        The agent's response as a string
    """
    try:
        # Call the simple REST endpoint
        url = f"{SERVER_URL}/ask"
        
        payload = {
            "question": question
        }
        
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        
        data = response.json()
        
        # The response should contain the result from the action
        if isinstance(data, dict) and "response" in data:
            return data["response"]
        elif isinstance(data, dict) and "error" in data:
            return f"Error from server: {data['error']}"
        else:
            return json.dumps(data, indent=2)
        
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

def compare_with_llm(input_text: str, response: str, expected_output: str, llm_client: AzureOpenAI) -> Tuple[int, str]:
    """
    Compare the agent's response with the expected output using an LLM for semantic similarity.
    
    Args:
        input_text: The original user input
        response: The actual output from the agent
        expected_output: The expected output from the dataset
        llm_client: Azure OpenAI client for evaluation
        
    Returns:
        Tuple of (score, explanation) where score is 1 for pass, 0 for fail
    """
    prompt = f"""
You are an evaluator assessing responses from a medical assistant AI agent called Dr. Indigo.
The agent's purpose is to help patients with questions about joint surgery recovery using information from a medical guide.

EVALUATION GUIDELINES:
- The agent should answer questions about joint surgery recovery, pain management, wound care, physical therapy, etc.
- Answers should be based on the medical guide and should be accurate and helpful
- The agent should cite the guide when providing information (e.g., "Guide, p. 15")
- For questions outside the scope of joint surgery, the agent should politely decline
- For medical emergencies, the agent should direct users to call 911 or seek immediate help
- The response doesn't need to match the expected output word-for-word, but should convey the same key information

Respond with ONLY 'YES' if the agent response is appropriate and conveys the same key information as the expected output.
Respond with ONLY 'NO' if the response is inappropriate, incorrect, or missing key information.

After YES or NO, provide a brief explanation on a new line.

---
User Input: {input_text}

Expected Output: {expected_output}

Agent Response: {response}
---
Evaluation:
"""

    try:
        completion = llm_client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=1.0  # Use default temperature (0.0 not supported by this model)
        )

        evaluation_text = completion.choices[0].message.content.strip()
        lines = evaluation_text.split('\n', 1)
        result = lines[0].upper()
        explanation = lines[1] if len(lines) > 1 else ""

        if result == "YES":
            return 1, explanation
        else:
            return 0, explanation
    except Exception as e:
        print(f"Error during LLM comparison: {e}")
        return 0, f"Error: {str(e)}"

def run_evaluation(csv_path: str, output_path: str = None, n_items: int = None) -> Dict:
    """
    Run the evaluation on the dataset.
    
    Args:
        csv_path: Path to CSV file with questions and expected answers
        output_path: Optional path to save results JSON file
        n_items: Optional limit on number of items to evaluate
        
    Returns:
        Dictionary with evaluation results
    """
    # Load dataset
    print(f"Loading dataset from {csv_path}...")
    dataset = load_csv_dataset(csv_path)
    
    if n_items:
        dataset = dataset[:n_items]
    
    print(f"Loaded {len(dataset)} items")
    
    # Initialize Azure OpenAI client for evaluation
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    
    llm_client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version
    )
    
    # Run evaluation
    results = []
    scores = []
    
    print("\nEvaluating agent responses...")
    for idx, item in enumerate(tqdm(dataset, desc="Processing items")):
        input_text = item['input']
        expected_output = item['expected_output']
        
        # Query the agent
        response = query_agent(input_text)
        
        # Compare with expected output
        score, explanation = compare_with_llm(input_text, response, expected_output, llm_client)
        
        scores.append(score)
        results.append({
            'item_number': idx + 1,
            'input': input_text,
            'expected_output': expected_output,
            'agent_response': response,
            'score': score,
            'pass': score == 1,
            'explanation': explanation
        })
    
    # Calculate overall metrics
    total_items = len(scores)
    passed_items = sum(scores)
    failed_items = total_items - passed_items
    pass_rate = (passed_items / total_items * 100) if total_items > 0 else 0
    
    evaluation_results = {
        'timestamp': datetime.now().isoformat(),
        'dataset_path': csv_path,
        'total_items': total_items,
        'passed': passed_items,
        'failed': failed_items,
        'pass_rate': round(pass_rate, 2),
        'results': results
    }
    
    # Save results if output path provided
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Results saved to {output_path}")
    
    return evaluation_results

def print_results_summary(evaluation_results: Dict):
    """Print a summary of evaluation results."""
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS SUMMARY")
    print("=" * 80)
    print(f"Timestamp: {evaluation_results['timestamp']}")
    print(f"Dataset: {evaluation_results['dataset_path']}")
    print(f"Total Items: {evaluation_results['total_items']}")
    print(f"Passed: {evaluation_results['passed']}")
    print(f"Failed: {evaluation_results['failed']}")
    print(f"Pass Rate: {evaluation_results['pass_rate']}%")
    print("=" * 80)
    
    # Print failed items if any
    failed_results = [r for r in evaluation_results['results'] if not r['pass']]
    if failed_results:
        print("\nFAILED ITEMS:")
        print("-" * 80)
        for result in failed_results:
            print(f"\nItem #{result['item_number']}")
            print(f"Input: {result['input']}")
            print(f"Expected: {result['expected_output'][:100]}...")
            print(f"Agent Response: {result['agent_response'][:100]}...")
            print(f"Explanation: {result['explanation']}")
            print("-" * 80)
    else:
        print("\n✅ All items passed!")

def main():
    """Main entry point for the evaluation script."""
    parser = argparse.ArgumentParser(
        description="Evaluate Dr. Indigo agent responses against expected outputs from a CSV file."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="questions_answers.csv",
        help="Path to CSV file with questions and expected answers (default: questions_answers.csv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save results JSON file (default: evaluation_results_<timestamp>.json)"
    )
    parser.add_argument(
        "--n_items",
        type=int,
        default=None,
        help="Number of items to evaluate (default: all items)"
    )
    
    args = parser.parse_args()
    
    # Check if environment variables are set
    required_env_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set them in your .env file")
        sys.exit(1)
    
    # Resolve CSV path
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(os.path.dirname(__file__), csv_path)
    
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found at {csv_path}")
        sys.exit(1)
    
    # Generate output path if not provided
    output_path = args.output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            os.path.dirname(__file__),
            f"evaluation_results_{timestamp}.json"
        )
    
    # Run evaluation
    try:
        evaluation_results = run_evaluation(csv_path, output_path, args.n_items)
        print_results_summary(evaluation_results)
        
        # Exit with error code if any items failed
        if evaluation_results['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"\n❌ Error during evaluation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
