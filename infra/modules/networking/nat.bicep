@description('Prefix for naming resources')
param prefix string

@description('Location for the resources')
param location string

@description('Tags to apply to resources')
param tags object = {}


@description('VNet resource name')
param vnetName string

@description('Subnet names to attach NAT Gateway to')
param subnetNames array

@description('Mapping of subnet names to address prefixes')
param subnetPrefixes object

var natGatewayName = toLower('${replace(prefix, '-', '')}natgw${uniqueString(resourceGroup().id)}')
var pipName = toLower('${replace(prefix, '-', '')}pipnatgw${uniqueString(resourceGroup().id)}')

resource publicIp 'Microsoft.Network/publicIPAddresses@2023-09-01' = {
  name: pipName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource natGateway 'Microsoft.Network/natGateways@2023-09-01' = {
  name: natGatewayName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIpAddresses: [
      {
        id: publicIp.id
      }
    ]
    idleTimeoutInMinutes: 10
  }
}


// Reference the existing VNet
resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' existing = {
  name: vnetName
}

// Attach NAT Gateway to each subnet
resource natSubnetAttachments 'Microsoft.Network/virtualNetworks/subnets@2023-09-01' = [for subnetName in subnetNames: {
  parent: vnet
  name: subnetName
  properties: {
    addressPrefix: subnetPrefixes[subnetName]
    natGateway: {
      id: natGateway.id
    }
  }
}]

output natGatewayName string = natGateway.name
output natGatewayId string = natGateway.id
output publicIpName string = publicIp.name
output publicIpId string = publicIp.id
