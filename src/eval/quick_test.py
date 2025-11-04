"""
Quick test script to verify the evaluation setup works.
Tests the agent with just a few sample questions.
"""

import sys
import os
import requests
import dotenv
import json

dotenv.load_dotenv()

# Default server URL
SERVER_URL = os.getenv("AGENT_SERVER_URL", "http://localhost:8000")

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
        
        response = requests.post(url, json=payload, timeout=60)
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

def quick_test():
    """Run a quick test with a few sample questions."""
    print("=" * 80)
    print("QUICK TEST - Dr. Indigo Agent")
    print("=" * 80)
    print(f"Server URL: {SERVER_URL}")
    print("=" * 80)
    
    # Test server connection
    print("\nTesting server connection...")
    try:
        response = requests.get(f"{SERVER_URL}/copilotkit_remote", timeout=5)
        print(f"✅ Server is responding (status: {response.status_code})")
    except Exception as e:
        print(f"❌ Server connection failed: {e}")
        print("Make sure the server is running (python api.py in the server directory)")
        sys.exit(1)
    
    # Test questions
    test_questions = [
        "I'm home, but I'm still in a good bit of pain. What's the best thing to do for it?",
        "When should I take my pain medication?",
        "Can I finally take a shower?"
    ]
    
    print("\nTesting agent with sample questions...\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'=' * 80}")
        print(f"Question {i}: {question}")
        print("-" * 80)
        
        try:
            response = query_agent(question)
            print(f"Response: {response}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("=" * 80)
    
    print("\n✅ Quick test completed!")

if __name__ == "__main__":
    quick_test()
