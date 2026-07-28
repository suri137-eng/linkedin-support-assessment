// Infrastructure for the LinkedIn Global Support Consultant chat assessment.
// Target: Azure Container Apps (single replica) with an Azure Files-backed
// volume for SQLite persistence, image pulled from an existing ACR via a
// user-assigned managed identity (no registry passwords).
//
// The ACR is created (and the image built) BEFORE this deployment by the
// deploy script, so `containerImage` already exists when the app is created.

@description('Short prefix used in resource names (letters/digits only).')
param namePrefix string = 'lsa'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Name of the pre-created Azure Container Registry.')
param acrName string

@description('Full image reference to run, e.g. myacr.azurecr.io/assessment:2026...')
param containerImage string

@description('Recruiter console admin token.')
@secure()
param adminToken string

@description('OpenAI API key. Leave empty to run the built-in offline demo simulator.')
@secure()
param openAiApiKey string = ''

@description('OpenAI model to use when an API key is supplied.')
param openAiModel string = 'gpt-4o-mini'

var resourceToken = uniqueString(resourceGroup().id)
var logName = '${namePrefix}-log-${resourceToken}'
var uamiName = '${namePrefix}-id-${resourceToken}'
var envName = '${namePrefix}-env-${resourceToken}'
var appName = '${namePrefix}-app'
var storageName = toLower('${namePrefix}st${resourceToken}')
var shareName = 'appdata'
var hasOpenAi = !empty(openAiApiKey)

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: uamiName
  location: location
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

// Grant the managed identity permission to pull images from the ACR.
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, uami.id, 'acrpull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: shareName
  properties: {
    shareQuota: 5
    enabledProtocols: 'SMB'
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource envStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: env
  name: 'appdata'
  properties: {
    azureFile: {
      accountName: storage.name
      accountKey: storage.listKeys().keys[0].value
      shareName: shareName
      accessMode: 'ReadWrite'
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: uami.id
        }
      ]
      secrets: hasOpenAi ? [
        {
          name: 'admin-token'
          value: adminToken
        }
        {
          name: 'openai-api-key'
          value: openAiApiKey
        }
      ] : [
        {
          name: 'admin-token'
          value: adminToken
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'assessment'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: hasOpenAi ? [
            {
              name: 'ADMIN_TOKEN'
              secretRef: 'admin-token'
            }
            {
              name: 'OPENAI_API_KEY'
              secretRef: 'openai-api-key'
            }
            {
              name: 'OPENAI_MODEL'
              value: openAiModel
            }
            {
              name: 'DB_PATH'
              value: '/app/data/assessment.db'
            }
            {
              name: 'PORT'
              value: '8000'
            }
            {
              name: 'HOST'
              value: '0.0.0.0'
            }
          ] : [
            {
              name: 'ADMIN_TOKEN'
              secretRef: 'admin-token'
            }
            {
              name: 'OPENAI_MODEL'
              value: openAiModel
            }
            {
              name: 'DB_PATH'
              value: '/app/data/assessment.db'
            }
            {
              name: 'PORT'
              value: '8000'
            }
            {
              name: 'HOST'
              value: '0.0.0.0'
            }
          ]
          volumeMounts: [
            {
              volumeName: 'datavol'
              mountPath: '/app/data'
            }
          ]
          probes: [
            {
              type: 'liveness'
              httpGet: {
                path: '/api/health'
                port: 8000
              }
              initialDelaySeconds: 15
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'readiness'
              httpGet: {
                path: '/api/health'
                port: 8000
              }
              initialDelaySeconds: 8
              periodSeconds: 10
              failureThreshold: 6
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      volumes: [
        {
          name: 'datavol'
          storageType: 'AzureFile'
          storageName: envStorage.name
        }
      ]
    }
  }
}

output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output containerAppName string = app.name
output containerAppFqdn string = app.properties.configuration.ingress.fqdn
output resourceGroupName string = resourceGroup().name
