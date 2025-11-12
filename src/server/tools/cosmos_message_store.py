"""
Custom ChatMessageStore implementation using Azure Cosmos DB for NoSQL.

This store persists agent chat history in Cosmos DB, enabling memory to be
shared across multiple agents and maintained per user/thread.
"""

from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from agent_framework import ChatMessage
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from pydantic import BaseModel


class CosmosStoreState(BaseModel):
    """State model for serializing and deserializing Cosmos DB chat message store data."""

    thread_id: str
    cosmos_endpoint: str | None = None
    cosmos_key: str | None = None
    database_name: str = "dr_indigo"
    container_name: str = "chat_messages"
    max_messages: int | None = None


class CosmosDBChatMessageStore:
    """Cosmos DB-backed implementation of ChatMessageStore.
    
    Stores messages in Cosmos DB for NoSQL using a one-document-per-turn model.
    Each document represents a single message in the conversation thread.
    
    Container partition key: /thread_id
    """

    def __init__(
        self,
        cosmos_endpoint: str | None = None,
        cosmos_key: str | None = None,
        thread_id: str | None = None,
        database_name: str = "dr_indigo",
        container_name: str = "chat_messages",
        max_messages: int | None = None,
    ) -> None:
        """Initialize the Cosmos DB chat message store.

        Args:
            cosmos_endpoint: Cosmos DB endpoint URL (e.g., "https://<account>.documents.azure.com:443/")
            cosmos_key: Cosmos DB account key for authentication
            thread_id: Unique identifier for this conversation thread (user session)
                      If not provided, a UUID will be auto-generated.
            database_name: Name of the Cosmos DB database (default: "dr_indigo")
            container_name: Name of the container for chat messages (default: "chat_messages")
            max_messages: Maximum number of messages to retain per thread.
                         When exceeded, oldest messages are automatically deleted.
        """
        if cosmos_endpoint is None:
            raise ValueError("cosmos_endpoint is required for Cosmos DB connection")
        if cosmos_key is None:
            raise ValueError("cosmos_key is required for Cosmos DB connection")

        self.cosmos_endpoint = cosmos_endpoint
        self.cosmos_key = cosmos_key
        self.thread_id = thread_id or f"thread_{uuid4()}"
        self.database_name = database_name
        self.container_name = container_name
        self.max_messages = max_messages

        # Initialize Cosmos DB client
        self._client = CosmosClient(self.cosmos_endpoint, credential=self.cosmos_key)
        self._database = None
        self._container = None
        self._initialize_cosmos()

    def _initialize_cosmos(self) -> None:
        """Create database and container if they don't exist."""
        try:
            print(f"🔌 Connecting to Cosmos DB: {self.cosmos_endpoint}")
            
            # Create database if it doesn't exist
            self._database = self._client.create_database_if_not_exists(id=self.database_name)
            print(f"✅ Connected to database: {self.database_name}")

            # Create container if it doesn't exist, partitioned by thread_id
            # Note: For serverless accounts, don't specify offer_throughput or autopilot
            self._container = self._database.create_container_if_not_exists(
                id=self.container_name,
                partition_key=PartitionKey(path="/thread_id"),
            )
            print(f"✅ Connected to container: {self.container_name} (thread_id: {self.thread_id})")
            
        except Exception as e:
            print(f"❌ Failed to connect to Cosmos DB: {e}")
            raise

    async def add_messages(self, messages: Sequence[ChatMessage]) -> None:
        """Add messages to the Cosmos DB store.

        Args:
            messages: Sequence of ChatMessage objects to add to the store.
        """
        if not messages:
            return

        print(f"💾 Adding {len(messages)} message(s) to Cosmos DB memory (thread_id: {self.thread_id})")
        
        try:
            # Add each message as a document in Cosmos DB
            for i, message in enumerate(messages, 1):
                message_dict = message.to_dict()
                document = {
                    "id": str(uuid4()),  # Unique document ID
                    "thread_id": self.thread_id,  # Partition key
                    "message": message_dict,
                    "timestamp": message_dict.get("timestamp"),
                }
                self._container.create_item(body=document)
                print(f"  ✓ Saved message {i}/{len(messages)} (role: {message.role})")

            print(f"✅ Successfully saved {len(messages)} message(s) to memory")

            # Apply message limit if configured
            if self.max_messages is not None:
                await self._trim_messages()
                
        except Exception as e:
            print(f"❌ Failed to save messages to Cosmos DB: {e}")
            raise

    async def list_messages(self) -> list[ChatMessage]:
        """Get all messages from the store in chronological order.

        Returns:
            List of ChatMessage objects in chronological order (oldest first).
        """
        print(f"📖 Retrieving messages from Cosmos DB memory (thread_id: {self.thread_id})")
        
        try:
            # Query all messages for this thread, ordered by timestamp
            query = """
                SELECT * FROM c 
                WHERE c.thread_id = @thread_id 
                ORDER BY c._ts ASC
            """
            parameters = [{"name": "@thread_id", "value": self.thread_id}]

            items = list(
                self._container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=False,
                    partition_key=self.thread_id,
                )
            )

            messages = []
            for item in items:
                message_data = item.get("message")
                if message_data:
                    message = ChatMessage.from_dict(message_data)
                    messages.append(message)

            print(f"✅ Retrieved {len(messages)} message(s) from memory")
            
            if messages:
                print(f"  First message: {messages[0].role} - {str(messages[0].content)[:50]}...")
                print(f"  Last message: {messages[-1].role} - {str(messages[-1].content)[:50]}...")

            return messages
            
        except Exception as e:
            print(f"❌ Failed to retrieve messages from Cosmos DB: {e}")
            raise

    async def _trim_messages(self) -> None:
        """Remove oldest messages if count exceeds max_messages."""
        if self.max_messages is None:
            return

        # Get all message IDs ordered by timestamp
        query = """
            SELECT c.id, c._ts FROM c 
            WHERE c.thread_id = @thread_id 
            ORDER BY c._ts ASC
        """
        parameters = [{"name": "@thread_id", "value": self.thread_id}]

        items = list(
            self._container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=False,
                partition_key=self.thread_id,
            )
        )

        # Delete oldest messages if we exceed the limit
        if len(items) > self.max_messages:
            messages_to_delete = items[: len(items) - self.max_messages]
            print(f"🗑️  Trimming {len(messages_to_delete)} old message(s) (max: {self.max_messages})")
            
            for item in messages_to_delete:
                try:
                    self._container.delete_item(
                        item=item["id"], partition_key=self.thread_id
                    )
                except exceptions.CosmosResourceNotFoundError:
                    # Message already deleted, skip
                    pass

            print(f"✅ Trimmed messages, now at {self.max_messages} messages")

    async def serialize_state(self, **kwargs: Any) -> Any:
        """Serialize the current store state for persistence.

        Returns:
            Dictionary containing serialized store configuration.
        """
        state = CosmosStoreState(
            thread_id=self.thread_id,
            cosmos_endpoint=self.cosmos_endpoint,
            cosmos_key=self.cosmos_key,
            database_name=self.database_name,
            container_name=self.container_name,
            max_messages=self.max_messages,
        )
        return state.model_dump(**kwargs)

    async def deserialize_state(
        self, serialized_store_state: Any, **kwargs: Any
    ) -> None:
        """Deserialize state data into this store instance.

        Args:
            serialized_store_state: Previously serialized state data.
            **kwargs: Additional arguments for deserialization.
        """
        if serialized_store_state:
            state = CosmosStoreState.model_validate(serialized_store_state, **kwargs)
            self.thread_id = state.thread_id
            self.database_name = state.database_name
            self.container_name = state.container_name
            self.max_messages = state.max_messages

            # Recreate Cosmos client if credentials changed
            if (
                state.cosmos_endpoint
                and state.cosmos_key
                and (
                    state.cosmos_endpoint != self.cosmos_endpoint
                    or state.cosmos_key != self.cosmos_key
                )
            ):
                self.cosmos_endpoint = state.cosmos_endpoint
                self.cosmos_key = state.cosmos_key
                self._client = CosmosClient(
                    self.cosmos_endpoint, credential=self.cosmos_key
                )
                self._initialize_cosmos()

    async def clear(self) -> None:
        """Remove all messages for this thread from the store."""
        # Query all messages for this thread
        query = "SELECT c.id FROM c WHERE c.thread_id = @thread_id"
        parameters = [{"name": "@thread_id", "value": self.thread_id}]

        items = list(
            self._container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=False,
                partition_key=self.thread_id,
            )
        )

        # Delete all messages
        for item in items:
            try:
                self._container.delete_item(
                    item=item["id"], partition_key=self.thread_id
                )
            except exceptions.CosmosResourceNotFoundError:
                # Message already deleted, skip
                pass
