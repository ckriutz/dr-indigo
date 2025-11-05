from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
import os


def create_search_tool(index_name: str = None):
    """
    Factory function that creates a search tool.
    
    Args:
        index_name: Optional search index name (defaults to env var SEARCH_INDEX_NAME)
    
    Returns:
        A search_tool function that takes a query string and returns search results
    """
    
    def search_tool(query: str) -> str:
        """Search the knowledge base for relevant information."""
        print("Executing search tool with query:", query)
        
        search_key = os.getenv("SEARCH_API_KEY")
        search_endpoint = os.getenv("SEARCH_ENDPOINT")
        search_index = index_name or os.getenv("SEARCH_INDEX_NAME")
        
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=search_index,
            credential=AzureKeyCredential(search_key)
        )

        try:
            vector_query = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="text_vector")

            results = search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                select=["title", "chunk"],
                top=5
            )

            sources_formatted = "=================\n".join(
                [f'TITLE: {document["title"]}, CONTENT: {document["chunk"]}' for document in results]
            )

            if sources_formatted:
                print("Search tool found sources")
                return sources_formatted
            else:
                return "No relevant information found in the knowledge base."

        except Exception as e:
            print(f"Error performing search: {str(e)}") 
            return f"Error performing search: {str(e)}"
    
    return search_tool