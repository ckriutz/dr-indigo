from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from PyPDF2 import PdfReader
import os
import threading

# This agent will answer questions about joint surgery. It will not answer any other questions.
# All the answers it gets will be answered by data only from the GuideToTotalJointSurgery_ENG_V2.pdf
# This file is included here, but will need to be changed next to be from blob storage.
# After that, even better if it came from Azure AI Search.
# If we move to Azure AI Search, we can remove the PyPDF2==3.0.1 requirement from requirements.txt

_pdf_cache = None
_pdf_cache_lock = threading.Lock()


# This function is probably a bit over-engineered for this.
# For now we can leave it be.
def get_joint_surgery_data(force_reload: bool = False) -> str:
    """
    Reads the PDF file and extracts all text content from it.
    Uses a module-level cache to avoid re-reading the file repeatedly.
    If force_reload is True, the cache will be reloaded from disk.
    Returns the text content as a string.
    """
    global _pdf_cache

    if _pdf_cache is not None and not force_reload:
        return _pdf_cache

    with _pdf_cache_lock:
        # Double-checked locking to avoid races
        if _pdf_cache is not None and not force_reload:
            return _pdf_cache

        pdf_path = os.path.join(os.path.dirname(__file__), "GuideToTotalJointSurgery_ENG_V2.pdf")
        try:
            reader = PdfReader(pdf_path)
            text_content = ""

            # Extract text from all pages
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"

            _pdf_cache = text_content
            return _pdf_cache
        except Exception as e:
            print(f"Error reading PDF: {e}")
            _pdf_cache = ""
            return _pdf_cache

def create_agent(client: AzureOpenAIChatClient):
    # Preload the PDF content into the module cache. This avoids reading the file on every call.
    pdf_content = get_joint_surgery_data()
    
    # Create instructions that include the PDF content
    instructions = f"""
    You are a Joint Surgery Information Agent. Your role is to answer questions about total joint surgery 
    using ONLY the information provided in the guide below.

    IMPORTANT RULES:
    - Answer questions ONLY about joint surgery topics
    - Base your answers ONLY on the information in the provided guide
    - If a question is not related to joint surgery, politely decline and explain that you only answer questions about joint surgery
    - If the answer is not found in the guide, say so honestly
    - Provide clear, accurate, and helpful responses based on the guide content
    - Do not make up information or provide medical advice beyond what's in the guide

    GUIDE TO TOTAL JOINT SURGERY:
    {pdf_content}
    """
    
    agent = ChatAgent(
        chat_client=client,
        tools=[],
        instructions=instructions
    )

    return agent