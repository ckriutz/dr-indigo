@description('Prefix used for naming the user assigned identity')
param prefix string

@description('Location for the identity')
param location string

var userIdentityName = toLower('${replace(prefix, '-', '')}identity${uniqueString(resourceGroup().id)}')

resource userIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: userIdentityName
  location: location
}

output userIdentityId string = userIdentity.id
output userIdentityPrincipalId string = userIdentity.properties.principalId
