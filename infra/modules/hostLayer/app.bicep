@description('Prefix used for naming the container app')
param prefix string

@description('Location of the container app')
param location string

@description('Tags to apply')
param tags object = {}

@description('Container App Environment resource ID')
param environmentId string

@description('ACR login server (e.g. myregistry.azurecr.io)')
param registryServer string

@description('ACR registry name (resource name)')
param registryName string

@description('Container image to deploy (e.g. myregistry.azurecr.io/app:latest)')
param containerImage string

@description('User Assigned Managed Identity resource ID')
param userIdentityId string

@description('User Assigned Managed Identity principalId')
param userIdentityPrincipalId string

// Fixed runtime settings (simplified: edit module to change)
var targetPort = 8080
var externalIngress = true
var cpuCores = 1
var memoryGi = '2.0'

// (Revision mode kept default Single – can be exposed later if needed)

// Derive app name
var appName = toLower('${replace(prefix, '-', '')}app${uniqueString(resourceGroup().id)}')

// Reference existing ACR for role assignment
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

// Main Container App
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
      }
      registries: [
        {
          server: registryServer
          identity: userIdentityId
        }
      ]
    }
    template: {
      revisionSuffix: 'r1'
      containers: [
        {
          name: 'main'
          image: containerImage
          resources: {
            cpu: cpuCores
            memory: '${memoryGi}Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
    workloadProfileName: 'Consumption'
  }
}

// Assign AcrPull role to the container app managed identity
// Built-in role id for AcrPull: 7f951dda-4ed3-4680-a7ca-43fe172d538d
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(app.id, 'acrpull')
  scope: acr
  properties: {
    principalId: userIdentityPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalType: 'ServicePrincipal'
  }
}

@description('Container App name')
output name string = app.name

@description('Container App resource id')
output id string = app.id

@description('Container App FQDN (only if ingress enabled)')
output fqdn string = externalIngress ? app.properties.latestRevisionFqdn : ''

@description('Managed Identity Principal Id')
output principalId string = userIdentityPrincipalId
