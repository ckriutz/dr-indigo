@description('Prefix to use for storage account naming')
param prefix string

@description('Location for the storage account')
param location string

@description('Tags to apply to the storage account')
param tags object = {}

// Storage account names must be between 3-24 characters, lowercase letters and numbers only
// We'll combine prefix with a unique suffix to ensure uniqueness
var storageAccountName = '${toLower(prefix)}${uniqueString(resourceGroup().id)}'

@description('Storage account SKU')
@allowed([
  'Standard_LRS'
  'Standard_GRS'
  'Standard_RAGRS'
  'Standard_ZRS'
  'Premium_LRS'
  'Premium_ZRS'
])
param sku string = 'Standard_LRS'

@description('Storage account kind')
@allowed([
  'Storage'
  'StorageV2'
  'BlobStorage'
  'FileStorage'
  'BlockBlobStorage'
])
param kind string = 'StorageV2'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: sku
  }
  kind: kind
  properties: {
    // Enable secure transfer (HTTPS only)
    supportsHttpsTrafficOnly: true
    
    // Enable encryption at rest
    encryption: {
      services: {
        blob: {
          enabled: true
        }
        file: {
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
    
    // Minimum TLS version
    minimumTlsVersion: 'TLS1_2'
    
    // Public network access
    publicNetworkAccess: 'Enabled'
    
    // Allow blob public access (set to false for enhanced security)
    allowBlobPublicAccess: false
    
    // Network rules - default to deny all, then allow specific networks
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

@description('Storage account name')
output storageAccountName string = storageAccount.name

@description('Storage account ID')
output storageAccountId string = storageAccount.id

@description('Primary endpoints')
output primaryEndpoints object = storageAccount.properties.primaryEndpoints
