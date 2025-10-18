@description('Prefix to use for Log Analytics Workspace naming')
param prefix string

@description('Location for the Log Analytics Workspace')
param location string

@description('Tags to apply to the Log Analytics Workspace')
param tags object = {}

// Workspace name: letters, numbers, -, _ ( keeping simple slug )
var workspaceName = toLower('${prefix}-logs')

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: -1
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

@description('Log Analytics Workspace resource id')
output workspaceId string = logAnalyticsWorkspace.id

@description('Log Analytics Workspace name')
output name string = logAnalyticsWorkspace.name
