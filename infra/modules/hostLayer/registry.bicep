@description('Prefix to use for Azure Container Registry naming')
param prefix string

@description('Location for the Azure Container Registry')
param location string

@description('Tags to apply to the Azure Container Registry')
param tags object = {}

@description('Enable admin user (not recommended for production - use managed identity instead)')
param adminUserEnabled bool = false

// ACR names must be globally unique, 5-50 characters, alphanumeric only (no hyphens)
var registryName = toLower('${replace(prefix, '-', '')}acr${uniqueString(resourceGroup().id)}')
var sku = 'Basic'

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    // Enable admin user only if explicitly requested (prefer managed identity)
    adminUserEnabled: adminUserEnabled
    
    // Public network access configuration
    publicNetworkAccess: 'Enabled'
    
    // Data endpoint configuration (Premium SKU only)
    dataEndpointEnabled: sku == 'Premium' ? true : false
    
    // Network rule bypass options
    networkRuleBypassOptions: 'AzureServices'
    
    // Zone redundancy (Premium SKU only, for high availability)
    zoneRedundancy: sku == 'Premium' ? 'Enabled' : 'Disabled'
    
    // Policies
    policies: {
      // Quarantine policy (Premium SKU only)
      quarantinePolicy: {
        status: 'Disabled'
      }
      // Trust policy for content trust (Premium SKU only)
      trustPolicy: {
        type: 'Notary'
        status: 'Disabled'
      }
      // Retention policy (Premium SKU only)
      retentionPolicy: {
        days: 7
        status: sku == 'Premium' ? 'Enabled' : 'Disabled'
      }
      // Export policy
      exportPolicy: {
        status: 'Enabled'
      }
    }
    
    // Encryption configuration (Premium SKU only with customer-managed keys)
    encryption: {
      status: 'Disabled'
    }
  }
}

@description('Container Registry name')
output registryName string = containerRegistry.name

@description('Container Registry ID')
output registryId string = containerRegistry.id

@description('Container Registry login server')
output loginServer string = containerRegistry.properties.loginServer
