"""
Memory Helper module for CosmosDB operations.
Provides methods to read and write memory data based on thread_id.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryHelper:
    """Helper class for managing memory data in CosmosDB."""
    
    def __init__(self):
        """Initialize the CosmosDB client and database/container references."""
        self.endpoint = os.getenv("COSMOS_ENDPOINT")
        self.key = os.getenv("COSMOS_KEY")  # Keep for backward compatibility
        self.database_name = os.getenv("COSMOS_DATABASE_NAME", "dr_indigo_db")
        self.container_name = os.getenv("COSMOS_CONTAINER_NAME", "memory_container")
        
        # AAD credentials (preferred method)
        self.tenant_id = os.getenv("AZURE_TENANT_ID")
        self.client_id = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        
        if not self.endpoint:
            raise ValueError("COSMOS_ENDPOINT environment variable is required")
        
        # Initialize CosmosDB client with AAD authentication
        try:
            credential = self._get_azure_credential()
            self.client = CosmosClient(self.endpoint, credential)
            logger.info("CosmosDB client initialized with Azure AD authentication")
        except Exception as e:
            logger.error(f"Failed to initialize CosmosDB client with AAD: {e}")
            raise
        
        # Connect to existing database and container
        self._setup_database_and_container()
    
    def _get_azure_credential(self):
        """Get the appropriate Azure credential for authentication."""
        # Option 1: Use Service Principal (Client Secret) if provided
        if self.tenant_id and self.client_id and self.client_secret:
            logger.info("Using ClientSecretCredential for authentication")
            return ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
        
        # Option 2: Use DefaultAzureCredential (works in Azure environments)
        logger.info("Using DefaultAzureCredential for authentication")
        return DefaultAzureCredential()
    
    def _setup_database_and_container(self):
        """Connect to existing database and container."""
        try:
            # Connect to existing database
            self.database = self.client.get_database_client(self.database_name)
            
            # Connect to existing container
            self.container = self.database.get_container_client(self.container_name)
            
            logger.info(f"Connected to database '{self.database_name}' and container '{self.container_name}'")
            
        except exceptions.CosmosResourceNotFoundError as e:
            logger.error(f"Database or container not found: {e}")
            logger.error(f"Please create database '{self.database_name}' and container '{self.container_name}' manually in Azure Portal")
            raise
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error connecting to database/container: {e}")
            raise
    
    def write_memory(self, thread_id: str, memory_data: Dict[str, Any]) -> bool:
        """
        Write memory data to CosmosDB for a specific thread_id.
        
        Args:
            thread_id (str): The unique thread identifier
            memory_data (Dict[str, Any]): The memory data to store
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Prepare the document
            document = {
                "id": f"memory_{thread_id}_{datetime.utcnow().isoformat()}",
                "thread_id": thread_id,
                "memory_data": memory_data,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Insert or replace the document
            self.container.upsert_item(document)
            return True
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error writing memory data for thread_id {thread_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing memory data: {e}")
            return False
    
    def read_memory(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Read the latest memory data from CosmosDB for a specific thread_id.
        
        Args:
            thread_id (str): The unique thread identifier
            
        Returns:
            Optional[Dict[str, Any]]: The memory data if found, None otherwise
        """
        try:
            # Query for the latest memory record for this thread_id
            query = """
            SELECT TOP 1 * FROM c 
            WHERE c.thread_id = @thread_id 
            ORDER BY c.updated_at DESC
            """
            
            parameters = [{"name": "@thread_id", "value": thread_id}]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=thread_id
            ))
            
            if items:
                return items[0]["memory_data"]
            else:
                return None
                
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error reading memory data for thread_id {thread_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading memory data: {e}")
            return None
    
    def read_all_memory_for_thread(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Read all memory records from CosmosDB for a specific thread_id.
        
        Args:
            thread_id (str): The unique thread identifier
            
        Returns:
            List[Dict[str, Any]]: List of all memory records for the thread
        """
        try:
            query = """
            SELECT * FROM c 
            WHERE c.thread_id = @thread_id 
            ORDER BY c.created_at ASC
            """
            
            parameters = [{"name": "@thread_id", "value": thread_id}]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=thread_id
            ))
            
            return items
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error reading all memory data for thread_id {thread_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error reading all memory data: {e}")
            return []
    
    def update_memory(self, thread_id: str, memory_data: Dict[str, Any]) -> bool:
        """
        Update existing memory data or create new if it doesn't exist.
        
        Args:
            thread_id (str): The unique thread identifier
            memory_data (Dict[str, Any]): The updated memory data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the latest memory record
            existing_memory = self.read_memory(thread_id)
            
            if existing_memory:
                # Merge with existing data
                merged_data = {**existing_memory, **memory_data}
            else:
                merged_data = memory_data
            
            return self.write_memory(thread_id, merged_data)
            
        except Exception as e:
            logger.error(f"Error updating memory data for thread_id {thread_id}: {e}")
            return False
    
    def delete_memory(self, thread_id: str) -> bool:
        """
        Delete all memory records for a specific thread_id.
        
        Args:
            thread_id (str): The unique thread identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get all memory records for this thread
            records = self.read_all_memory_for_thread(thread_id)
            
            # Delete each record
            for record in records:
                self.container.delete_item(
                    item=record["id"],
                    partition_key=thread_id
                )
            
            return True
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error deleting memory data for thread_id {thread_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting memory data: {e}")
            return False


# Convenience functions for direct usage
def get_memory_helper() -> MemoryHelper:
    """Get a MemoryHelper instance."""
    return MemoryHelper()


def write_thread_memory(thread_id: str, memory_data: Dict[str, Any]) -> bool:
    """
    Convenience function to write memory data for a thread.
    
    Args:
        thread_id (str): The unique thread identifier
        memory_data (Dict[str, Any]): The memory data to store
        
    Returns:
        bool: True if successful, False otherwise
    """
    helper = get_memory_helper()
    return helper.write_memory(thread_id, memory_data)


def read_thread_memory(thread_id: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to read memory data for a thread.
    
    Args:
        thread_id (str): The unique thread identifier
        
    Returns:
        Optional[Dict[str, Any]]: The memory data if found, None otherwise
    """
    helper = get_memory_helper()
    return helper.read_memory(thread_id)
