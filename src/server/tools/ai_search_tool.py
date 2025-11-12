import logging

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

from settings import AUBREY_SETTINGS

# Configure logging
logger = logging.getLogger(__name__)


def create_search_tool(index_name: str = None):
    """
    Factory function that creates a search tool.

    Args:
        index_name: Optional search index name (defaults to env var SEARCH_INDEX_NAME)

    Returns:
        A search_tool function that takes a query string and returns search results
    """
    # Create search client once when the tool is created
    search_index = index_name or AUBREY_SETTINGS.search_index_name
    search_client = SearchClient(
        endpoint=AUBREY_SETTINGS.search_endpoint,
        index_name=search_index,
        credential=AzureKeyCredential(AUBREY_SETTINGS.search_api_key)
    )

    def search_tool(query: str) -> str:
        """Search the knowledge base for relevant information."""
        logger.info(f"🔍 AI Search Tool called with query: {query[:100]}...")
        print(f"🔍 AI Search Tool called with query: {query[:100]}...")
        
        try:
            vector_query = VectorizableTextQuery(
                text=query, 
                k_nearest_neighbors=50, 
                fields="text_vector"
            )

            results = search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                select=["title", "chunk"],
                top=5,
            )

            sources = [
                f"TITLE: {doc['title']}, CONTENT: {doc['chunk']}"
                for doc in results
            ]

            result_text = "=================\n".join(sources) if sources else "No relevant information found in the knowledge base."
            
            logger.info(f"✅ AI Search Tool returned {len(sources)} results")
            print(f"✅ AI Search Tool returned {len(sources)} results")
            
            return result_text

        except Exception as e:
            logger.error(f"⛔ Error performing search: {e}")
            print(f"⛔ Error performing search: {e}")
            return f"Error performing search: {e}"

    return search_tool
