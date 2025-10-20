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
var targetPort = 80
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
    environmentId: environmentId
    
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
      }
    }
    template: {
      
      containers: [
        {
          name: 'hello'
          image: containerImage
          probes: []
        }
      ]
      scale: {
        minReplicas: 0
      }
    }
  }
}

@description('Container App name')
output name string = app.name

@description('Container App resource id')
output id string = app.id

@description('Container App FQDN (only if ingress enabled)')
output fqdn string = app.properties.configuration.ingress.fqdn

@description('Managed Identity Principal Id')
output principalId string = userIdentityPrincipalId
