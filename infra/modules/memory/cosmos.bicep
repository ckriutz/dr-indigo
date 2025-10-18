@description('Prefix to use for Cosmos DB account naming')
param prefix string

@description('Location for the Cosmos DB account')
param location string

@description('Tags to apply to the Cosmos DB account')
param tags object = {}

@description('Partition key path for the container')
param partitionKeyPath string = '/id'

// Cosmos DB account names must be globally unique, 3-44 characters, lowercase letters, numbers, and hyphens
var cosmosAccountName = toLower('${prefix}-cosmos-${uniqueString(resourceGroup().id)}')

// Generate database and container names from prefix
var databaseName = toLower('${prefix}-db')
var containerName = toLower('${prefix}-conversations')

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: cosmosAccountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
      maxIntervalInSeconds: 5
      maxStalenessPrefix: 100
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    // Enable automatic failover for high availability
    enableAutomaticFailover: false
    
    // Enable multiple write locations for multi-region writes (disabled for cost optimization)
    enableMultipleWriteLocations: false
    
    // Disable public network access for enhanced security (set to Enabled for development)
    publicNetworkAccess: 'Enabled'
    
    // Enable free tier for development (only one per subscription)
    enableFreeTier: false
    
    // Backup policy - Continuous backup for point-in-time restore
    backupPolicy: {
      type: 'Continuous'
      continuousModeProperties: {
        tier: 'Continuous7Days'
      }
    }
    
    // Capabilities
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
    // No throughput needed for serverless
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          partitionKeyPath
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/_etag/?'
          }
        ]
      }
    }
    // No throughput needed for serverless
  }
}

@description('Cosmos DB account name')
output cosmosAccountName string = cosmosAccount.name

@description('Cosmos DB account ID')
output cosmosAccountId string = cosmosAccount.id

@description('Cosmos DB endpoint')
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint

@description('Database name')
output databaseName string = database.name

@description('Container name')
output containerName string = container.name
