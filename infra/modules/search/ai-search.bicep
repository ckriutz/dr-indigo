@description('Prefix to use for Azure AI Search naming')
param prefix string

@description('Location for the Azure AI Search resource')
param location string

@description('Tags to apply to the Azure AI Search resource')
param tags object = {}

// Search service names must be globally unique, 2-60 characters, lowercase letters, numbers, and hyphens
var searchName = toLower('${prefix}-search-${uniqueString(resourceGroup().id)}')

resource searchService 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchName
  location: location
  tags: tags
  sku: {
    name: 'standard'
  }
  properties: {
    hostingMode: 'default'
    partitionCount: 1
    replicaCount: 1
    publicNetworkAccess: 'Enabled'
    // Encryption is enabled by default
  }
}

output searchServiceName string = searchService.name
output searchServiceId string = searchService.id
output searchServiceEndpoint string = searchService.properties.endpoint
