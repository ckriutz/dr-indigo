using 'main.bicep'

param location = 'eastus2'
param prefix = 'drindigo'
param tags = {
  project: 'dr-indigo'
  environment: 'dev'
}

param networkAddressPrefixes = {
  vnet: '10.10.0.0/16'
  privateEndpoints: '10.10.1.0/24'
  containerAppEnv: '10.10.2.0/24'
}

param containerImage = 'mcr.microsoft.com/k8se/quickstart:latest'

param cosmosPartitionKeyPath = '/id'

param acrAdminUserEnabled = false


