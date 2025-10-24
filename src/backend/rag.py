

import os
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient
from azure.search.documents.indexes import (
    SearchIndexerClient,
    SearchIndexClient
)
from azure.search.documents.indexes.models import (
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection
)

from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    AzureOpenAIEmbeddingSkill,
    SemanticSearch,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    CognitiveServicesAccountKey,
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SearchIndexerSkillset,
    SearchIndexer

)



BLOB_CONTAINER_NAME = os.environ.get('BLOB_CONTAINER_NAME', '')
BLOB_ACCOUNT_URL = os.environ.get('BLOB_ACCOUNT_URL', '')
LOCAL_FILE_PATH = os.environ.get('LOCAL_FILE_PATH', '')
BLOB_CONNECTION_STRING = os.environ.get('BLOB_CONNECTION_STRING', '')

AZURE_SEARCH_ENDPOINT = os.environ.get('AZURE_SEARCH_ENDPOINT', '')
AZURE_SEARCH_KEY: str = os.environ.get('AZURE_SEARCH_KEY', '')

AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
AZURE_OPENAI_KEY: str = os.environ.get('AZURE_OPENAI_KEY', '')

AOAI_EMBEDDING_DEPLOYMENT = os.environ.get('AOAI_EMBEDDING_DEPLOYMENT', '')
AOAI_EMBEDDING_MODEL = os.environ.get('AOAI_EMBEDDING_MODEL', '')

AZURE_MULTISERVICES_KEY = os.environ.get('AZURE_MULTISERVICES_KEY', '')


def get_client(account_url):
    credential = DefaultAzureCredential()
    service = BlobServiceClient(account_url=account_url, credential=credential)
    return service

def get_indexer_client(endpoint, api_key):
    indexer_client = SearchIndexerClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    return indexer_client

def get_index_client(endpoint, api_key):
    index_client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    return index_client

def get_multi_service_key(api_key):
    multi_service_key = CognitiveServicesAccountKey(key=api_key)
    return multi_service_key

def upload_blob_file(blob_service_client: BlobServiceClient, container_name: str, file_name: str, data: bytes, overwrite: bool = True):
    print('>>> uploading file to blob')
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=file_name)
    blob_client.upload_blob(data, blob_type="BlockBlob", overwrite=overwrite)
    print('<<< finished uploading file to blob')


def create_data_source(data_source_name, indexer_client, blob_connection_string, blob_container):
# Create a data source
    container = SearchIndexerDataContainer(name=blob_container)
    data_source_connection = SearchIndexerDataSourceConnection(
        name=data_source_name,
        type="azureblob",
        connection_string=blob_connection_string,
        container=container
    )
    data_source = indexer_client.create_or_update_data_source_connection(data_source_connection)
    print(f"Data source '{data_source.name}' created or updated")

def create_skillset(skillset_name, indexer_client, index_name, ai_multiservice_key):
    split_skill = SplitSkill(
        description="Split skill to chunk documents",
        text_split_mode="pages",
        context="/document",
        maximum_page_length=2000,
        page_overlap_length=500,
        inputs=[
            InputFieldMappingEntry(name="text", source="/document/content"),
        ],
        outputs=[
            OutputFieldMappingEntry(name="textItems", target_name="pages")
        ],
    )

    embedding_skill = AzureOpenAIEmbeddingSkill(
        description="Skill to generate embeddings via Azure OpenAI",
        context="/document/pages/*",
        resource_url=AZURE_OPENAI_ENDPOINT,
        deployment_name=AOAI_EMBEDDING_DEPLOYMENT,
        model_name=AOAI_EMBEDDING_MODEL,
        dimensions=1024,
        inputs=[
            InputFieldMappingEntry(name="text", source="/document/pages/*"),
        ],
        outputs=[
            OutputFieldMappingEntry(name="embedding", target_name="text_vector")
        ],
    )

    index_projections = SearchIndexerIndexProjection(
        selectors=[
            SearchIndexerIndexProjectionSelector(
                target_index_name=index_name,
                parent_key_field_name="parent_id",
                source_context="/document/pages/*",
                mappings=[
                    InputFieldMappingEntry(name="chunk", source="/document/pages/*"),
                    InputFieldMappingEntry(name="text_vector", source="/document/pages/*/text_vector"),
                    InputFieldMappingEntry(name="title", source="/document/metadata_storage_name"),
                ],
            ),
        ],
        parameters=SearchIndexerIndexProjectionsParameters(
            projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
        ),
    )

    skills = [split_skill, embedding_skill]

    skillset = SearchIndexerSkillset(
        name=skillset_name,
        description="Skillset to chunk documents and generate embeddings",
        skills=skills,
        index_projection=index_projections,
        cognitive_services_account=ai_multiservice_key
    )

    indexer_client.create_or_update_skillset(skillset)
    print(f"{skillset.name} created")

def create_index(index_name, index_client, AZURE_OPENAI_ACCOUNT):
    fields = [
        SearchField(name="parent_id", type=SearchFieldDataType.String),
        SearchField(name="title", type=SearchFieldDataType.String),
        SearchField(
            name="chunk_id",
            type=SearchFieldDataType.String,
            key=True,
            sortable=True,
            filterable=True,
            facetable=True,
            analyzer_name="keyword"
        ),
        SearchField(
            name="chunk",
            type=SearchFieldDataType.String,
            sortable=False,
            filterable=False,
            facetable=False
        ),
        SearchField(
            name="text_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=1024,
            vector_search_profile_name="HnswProfile"
        )
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="HnswConfig"),
        ],
        profiles=[
            VectorSearchProfile(
                name="HnswProfile",
                algorithm_configuration_name="HnswConfig",
                vectorizer_name="oaiVectorizer",
            )
        ],
        vectorizers=[
            AzureOpenAIVectorizer(
                vectorizer_name="oaiVectorizer",
                kind="azureOpenAI",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=AZURE_OPENAI_ACCOUNT,
                    deployment_name="text-embedding-3-large",
                    model_name="text-embedding-3-large"
                ),
            ),
        ],
    )

    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search
    )
    result = index_client.create_or_update_index(index)
    print(f"{result.name} created")

def runIndexer(indexer_client, index_name, skillset_name, data_source_name):
    # Create an indexer  
    indexer_name = "rag-idxr" 

    indexer_parameters = None

    indexer = SearchIndexer(  
        name=indexer_name,  
        description="Indexer to index documents and generate embeddings",  
        skillset_name=skillset_name,  
        target_index_name=index_name,  
        data_source_name=data_source_name,
        parameters=indexer_parameters
    )  

    # Create and run the indexer  
    indexer_result = indexer_client.create_or_update_indexer(indexer)  

    print(f' {indexer_name} is created and running. Give the indexer a few minutes before running a query.')

def main():
    blob_service_client = get_client(BLOB_ACCOUNT_URL)
    index_client = get_index_client(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY)
    indexer_client = get_indexer_client(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY)
    ai_multiservice_key = get_multi_service_key(AZURE_MULTISERVICES_KEY)

    index_name = "ragidx"
    skillset_name = "pdf-embedding-skillset"
    data_source_name = "rag-data-source"

    with open(LOCAL_FILE_PATH, "rb") as data:
        filename = os.path.basename(LOCAL_FILE_PATH)
        blob_path = BLOB_CONTAINER_NAME
        upload_blob_file(blob_service_client, blob_path, filename, data)
        print("File uploaded successfully.")

    create_index(index_name, index_client, AZURE_OPENAI_ENDPOINT)
    create_skillset(skillset_name, indexer_client, index_name, ai_multiservice_key)
    create_data_source(data_source_name, indexer_client, BLOB_CONNECTION_STRING, BLOB_CONTAINER_NAME)
    runIndexer(indexer_client, index_name, skillset_name, data_source_name)

if __name__ == "__main__":
    main()
