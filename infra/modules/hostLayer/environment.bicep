@description('Prefix to use for Container App Environment naming')
param prefix string

@description('Location for the Container App Environment')
param location string

@description('Tags to apply to the Container App Environment')
param tags object = {}

@description('Existing Log Analytics Workspace name')
param logAnalyticsWorkspaceName string


// Container App Environment names must be 2-60 characters, lowercase letters, numbers, and hyphens
var environmentName = toLower('${replace(prefix, '-', '')}env${uniqueString(resourceGroup().id)}')

// Reference existing Log Analytics workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    // Logging configuration
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    
  // Zone redundancy disabled (can be enabled by editing module if Premium tier adopted later)
  zoneRedundant: false
    
    // Workload profiles (Consumption by default)
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

@description('Container App Environment name')
output environmentName string = containerAppEnvironment.name

@description('Container App Environment ID')
output environmentId string = containerAppEnvironment.id

@description('Container App Environment default domain')
output defaultDomain string = containerAppEnvironment.properties.defaultDomain

@description('Container App Environment static IP')
output staticIp string = containerAppEnvironment.properties.staticIp

@description('Log Analytics Workspace ID')
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id

@description('Log Analytics Workspace name')
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
