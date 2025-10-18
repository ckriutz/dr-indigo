@description('Prefix for naming resources')
param prefix string
@description('Location for the resources')
param location string


@description('Tags to apply to resources')
param tags object = {}



@description('Object containing all address prefixes for the VNet and subnets')
param addressPrefixes object = {
  vnet: '10.10.0.0/16'
  privateEndpoints: '10.10.1.0/24'
  containerAppEnv: '10.10.2.0/24'
}

var vnetName = toLower('${replace(prefix, '-', '')}vnet${uniqueString(resourceGroup().id)}')
var subnetPrivateEndpointsName = toLower('${replace(prefix, '-', '')}endpoints')
var subnetContainerAppEnvName = toLower('${replace(prefix, '-', '')}aca')

@description('Network Security Group resource ID to associate with subnets')
param nsgId string

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        addressPrefixes.vnet
      ]
    }
    subnets: [
      {
        name: subnetPrivateEndpointsName
        properties: {
          addressPrefix: addressPrefixes.privateEndpoints
          networkSecurityGroup: {
            id: nsgId
          }
        }
      }
      {
        name: subnetContainerAppEnvName
        properties: {
          addressPrefix: addressPrefixes.containerAppEnv
          networkSecurityGroup: {
            id: nsgId
          }
          // NAT Gateway association handled in nat.bicep
        }
      }
    ]
  }
}


output vnetName string = vnet.name
output vnetId string = vnet.id
output subnetPrivateEndpointsName string = subnetPrivateEndpointsName
output subnetContainerAppEnvName string = subnetContainerAppEnvName

