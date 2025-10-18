@description('Prefix for naming resources')
param prefix string

@description('Location for the resources')
param location string

@description('Tags to apply to resources')
param tags object = {}

var nsgName = toLower('${replace(prefix, '-', '')}nsg${uniqueString(resourceGroup().id)}')

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: nsgName
  location: location
  tags: tags
  properties: {}
}

output nsgName string = nsg.name
output nsgId string = nsg.id
