targetScope = 'subscription'

@description('Location for the resource group')
param location string = ''

@description('Prefix for resource naming (used for storage account)')
param prefix string

@description('Tags to apply to resources')
param tags object = {
  project: ''
  environment: ''
}

@description('Cosmos DB partition key path')
param cosmosPartitionKeyPath string = '/id'

@description('Enable ACR admin user (not recommended for production)')
param acrAdminUserEnabled bool = false
@description('Container image to deploy to Container App')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

resource resourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: toLower('${prefix}-rg')
  location: location
  tags: tags
}

@description('Address prefixes for VNet and subnets')
param networkAddressPrefixes object = {
  vnet: '10.10.0.0/16'
  privateEndpoints: '10.10.1.0/24'
  containerAppEnv: '10.10.2.0/24'
}

// Deploy Virtual Network
module vnet 'modules/networking/vnet.bicep' = {
  scope: resourceGroup
  name: 'vnetDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
    nsgId: nsg.outputs.nsgId
    addressPrefixes: networkAddressPrefixes
  }
}

// Deploy Network Security Group
module nsg 'modules/networking/nsg.bicep' = {
  scope: resourceGroup
  name: 'nsgDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
  }
}

// Deploy NAT Gateway
module nat 'modules/networking/nat.bicep' = {
  scope: resourceGroup
  name: 'natDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
    vnetName: vnet.outputs.vnetName
    subnetNames: [vnet.outputs.subnetPrivateEndpointsName, vnet.outputs.subnetContainerAppEnvName]
    subnetPrefixes: {
      '${vnet.outputs.subnetPrivateEndpointsName}': networkAddressPrefixes.privateEndpoints
      '${vnet.outputs.subnetContainerAppEnvName}': networkAddressPrefixes.containerAppEnv
    }
  }
}

// Deploy storage account module
module storageAccount 'modules/storage/storage-account.bicep' = {
  scope: resourceGroup
  name: 'storageAccountDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
  }
}

// Deploy Azure AI Search module
module aiSearch 'modules/search/ai-search.bicep' = {
  scope: resourceGroup
  name: 'aiSearchDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
  }
}

// Deploy Cosmos DB module
module cosmosDb 'modules/memory/cosmos.bicep' = {
  scope: resourceGroup
  name: 'cosmosDbDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
    partitionKeyPath: cosmosPartitionKeyPath
  }
}

// Deploy Azure Container Registry module
module containerRegistry 'modules/hostLayer/registry.bicep' = {
  scope: resourceGroup
  name: 'containerRegistryDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
    adminUserEnabled: acrAdminUserEnabled
  }
}

// Deploy Log Analytics Workspace module (monitor)
module logAnalytics 'modules/monitor/law.bicep' = {
  scope: resourceGroup
  name: 'logAnalyticsDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
  }
}

// Deploy Container App Environment module (host layer)
module containerEnvironment 'modules/hostLayer/environment.bicep' = {
  scope: resourceGroup
  name: 'containerEnvironmentDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
    logAnalyticsWorkspaceName: logAnalytics.outputs.name
  }
}

// Deploy User Assigned Managed Identity for the app
module userIdentity 'modules/hostLayer/identity.bicep' = {
  scope: resourceGroup
  name: 'userIdentityDeployment'
  params: {
    prefix: prefix
    location: location
  }
}

// Deploy Container App (application workload)
// Still working on container app template - so this module still has a couple of failures

module containerApp 'modules/hostLayer/app.bicep' = {
  scope: resourceGroup
  name: 'containerAppDeployment'
  params: {
    prefix: prefix
    location: location
    tags: tags
    environmentId: containerEnvironment.outputs.environmentId
    registryServer: containerRegistry.outputs.loginServer
    registryName: containerRegistry.outputs.registryName
    containerImage: containerImage
    userIdentityId: userIdentity.outputs.userIdentityId
    userIdentityPrincipalId: userIdentity.outputs.userIdentityPrincipalId
  }
}


output resourceGroupId string = resourceGroup.id
output storageAccountName string = storageAccount.outputs.storageAccountName
output storageAccountId string = storageAccount.outputs.storageAccountId

output aiSearchName string = aiSearch.outputs.searchServiceName
output aiSearchId string = aiSearch.outputs.searchServiceId
output aiSearchEndpoint string = aiSearch.outputs.searchServiceEndpoint

output cosmosAccountName string = cosmosDb.outputs.cosmosAccountName
output cosmosAccountId string = cosmosDb.outputs.cosmosAccountId
output cosmosEndpoint string = cosmosDb.outputs.cosmosEndpoint
output cosmosDatabaseName string = cosmosDb.outputs.databaseName
output cosmosContainerName string = cosmosDb.outputs.containerName

output acrName string = containerRegistry.outputs.registryName
output acrId string = containerRegistry.outputs.registryId
output acrLoginServer string = containerRegistry.outputs.loginServer

output logAnalyticsWorkspaceId string = logAnalytics.outputs.workspaceId
output logAnalyticsWorkspaceName string = logAnalytics.outputs.name

// output containerAppEnvironmentName string = containerEnvironment.outputs.environmentName
// output containerAppEnvironmentId string = containerEnvironment.outputs.environmentId
// output containerAppEnvironmentDomain string = containerEnvironment.outputs.defaultDomain
// output containerAppEnvironmentStaticIp string = containerEnvironment.outputs.staticIp
//
// output containerAppName string = containerApp.outputs.name
// output containerAppFqdn string = containerApp.outputs.fqdn

