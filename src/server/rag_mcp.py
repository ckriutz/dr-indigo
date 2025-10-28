# MCP imports
import os
import asyncio
import json
import logging
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import AzureOpenAI
import mcp.types as types
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
# 1. Create MCP Server with proper configuration
WORKSPACE_MCP_PORT = int(os.getenv("GRAPHRAG_MCP_PORT", 8111))
WORKSPACE_MCP_BASE_URI = "localhost"#@os.getenv("GRAPHRAG_MCP_BASE_URI", "http://localhost")

server = FastMCP(
    name="rag_tool",
    host=WORKSPACE_MCP_BASE_URI,
    port=WORKSPACE_MCP_PORT
)

# 2. RAG Initialization (Global State)
class RAGServer:
    def __init__(self):
        self.search_client = None
        self.openai_client = None
        self.openai_deployment = None
        self.initialized = False
        self.init_error = None
        self._init_lock = asyncio.Lock()


    async def initialize(self):
        async with self._init_lock:
            if self.initialized:
                return
            try:
                # Initialize your RAG components here
                load_dotenv()
                logger.info("Reading env vars.")
                search_key = os.getenv("SEARCH_API_KEY")
                search_endpoint = os.getenv("SEARCH_ENDPOINT")
                search_index = os.getenv("SEARCH_INDEX_NAME")

                openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
                openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                self.openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
                openai_model = os.getenv("AZURE_OPENAI_MODEL_NAME")
                openai_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
                
                self.openai_client = AzureOpenAI(
                    api_version=openai_version,
                    azure_endpoint=openai_endpoint,
                    api_key=openai_api_key
                )

                self.search_client = SearchClient(
                    endpoint=search_endpoint,
                    index_name=search_index,
                    credential=AzureKeyCredential(search_key)
                    )
                


                self.initialized = True
                logger.info("RAG MCP initialized successfully.")

            except Exception as e: 
                self.init_error = str(e)
                logger.error(f"Failed to initialize RAG MCP: {self.init_error}")

    async def ensure_initialized(self):
        """Ensure the server is initialized before use"""
        if not self.initialized and not self.init_error:
            await self.initialize()

rag_server = RAGServer()

@server.tool()
async def rag_search(query: str) -> types.CallToolResult:
    """Perform a search using RAG."""
    await rag_server.ensure_initialized()

    if not rag_server.initialized:
        msg = f"Server initialization failed: {rag_server.init_error}" if rag_server.init_error else "Server not initialized."
        return types.CallToolResult(
            isError=True,
            content=[types.TextContent(type="text", text=msg)]
        )
    try:
        # Provide instructions to the model
        GROUNDED_PROMPT = """
            You are an AI assistant that helps users learn from the information found in the source material.
            Answer the query using only the sources provided below.
            If the answer is longer than 3 sentences, provide a summary.
            Answer ONLY with the facts listed in the list of sources below. Cite your source when you answer the question
            If there isn't enough information below, say you don't know.
            Do not generate answers that don't use the sources below.
            Query: {query}
            Sources:\n{sources}
        """
        vector_query = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="text_vector")

        results = rag_server.search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["title", "chunk"],
            top=5
        )
        sources_formatted = "=================\n".join(
            [f'TITLE: {document["title"]}, CONTENT: {document["chunk"]}' for document in results]
        )

        response = rag_server.openai_client.chat.completions.create(
            messages=[
            {
                "role": "user",
                "content": GROUNDED_PROMPT.format(query=query, sources=sources_formatted)
            }
            ],
            model=rag_server.openai_deployment
        )

        response_content = response.choices[0].message.content

        return types.CallToolResult(
            isError=False,
            content=[types.TextContent(type="text", text=response_content)]
        )

    except Exception as e:
        return types.CallToolResult(
            isError=True,
            content=[types.TextContent(type="text", text=f"Error performing search: {str(e)}")]
        )

# 5. Run the server
if __name__ == "__main__":
    # Use streamable-http transport for HTTP-based MCP
    server.run(transport="streamable-http")               