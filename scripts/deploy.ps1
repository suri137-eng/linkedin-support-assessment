<#
    Deploys the LinkedIn Global Support Consultant chat assessment to Azure
    Container Apps using Azure CLI + Bicep (no azd / no local Docker required).

    Flow:
      1. Select subscription + create resource group
      2. Create the Azure Container Registry (Basic)
      3. Build & push the image remotely with `az acr build` (cloud build)
      4. Deploy infra/main.bicep (env, storage/files, identity, app)
      5. Print the public URL + admin token

    Usage (from anywhere):
      ./scripts/deploy.ps1 `
        -SubscriptionId f7c445af-a4de-4264-9e87-3196d6bc384d `
        -ResourceGroup rg-linkedin-support-assessment `
        -Location centralindia

    Optional:
      -AdminToken <token>       # recruiter console token (auto-generated if omitted)
      -OpenAiApiKey <key>       # enables live OpenAI role-play (demo mode if omitted)
      -OpenAiModel gpt-4o-mini
#>
[CmdletBinding()]
param(
    [string]$SubscriptionId = "f7c445af-a4de-4264-9e87-3196d6bc384d",
    [string]$ResourceGroup  = "rg-linkedin-support-assessment",
    [string]$Location       = "centralindia",
    [string]$NamePrefix     = "lsa",
    [string]$AdminToken     = "",
    [string]$OpenAiApiKey   = "",
    [string]$OpenAiModel    = "gpt-4o-mini"
)

$ErrorActionPreference = "Stop"

# Repo root = parent of this script's folder.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $root
Write-Host "Repo root: $root" -ForegroundColor DarkGray

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI (az) is required but was not found on PATH."
}

# ---- Deterministic, globally-unique ACR name from subscription + RG ----
$hashInput = "$SubscriptionId/$ResourceGroup".ToLower()
$sha = [System.Security.Cryptography.SHA256]::Create()
$bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($hashInput))
$token = -join ($bytes | Select-Object -First 6 | ForEach-Object { $_.ToString("x2") })  # 12 hex chars
$AcrName = ("{0}acr{1}" -f $NamePrefix, $token).ToLower()
if ($AcrName.Length -gt 50) { $AcrName = $AcrName.Substring(0, 50) }

if (-not $AdminToken) {
    $AdminToken = [Convert]::ToBase64String([Guid]::NewGuid().ToByteArray()).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$imageTag   = Get-Date -Format "yyyyMMddHHmmss"
$imageName  = "assessment"

Write-Host "Subscription : $SubscriptionId" -ForegroundColor Cyan
Write-Host "ResourceGroup: $ResourceGroup ($Location)" -ForegroundColor Cyan
Write-Host "ACR          : $AcrName" -ForegroundColor Cyan
Write-Host "Image        : $imageName`:$imageTag" -ForegroundColor Cyan

az account set --subscription $SubscriptionId | Out-Null

# ---- 1. Resource group ----
Write-Host "`n[1/4] Creating resource group..." -ForegroundColor Green
az group create --name $ResourceGroup --location $Location --only-show-errors | Out-Null

# ---- 2. Container registry ----
Write-Host "[2/4] Creating container registry (Basic)..." -ForegroundColor Green
az acr create --resource-group $ResourceGroup --name $AcrName --sku Basic `
    --admin-enabled false --only-show-errors | Out-Null
$acrLoginServer = az acr show --name $AcrName --query loginServer -o tsv
$containerImage = "$acrLoginServer/$imageName`:$imageTag"

# ---- 3. Remote image build (no local Docker needed) ----
Write-Host "[3/4] Building image in ACR (cloud build)..." -ForegroundColor Green
az acr build --registry $AcrName --image "$imageName`:$imageTag" --image "$imageName`:latest" --file Dockerfile . --only-show-errors

# ---- 4. Deploy infrastructure ----
Write-Host "[4/4] Deploying infrastructure (Bicep)..." -ForegroundColor Green
$deployName = "lsa-$imageTag"
$outputs = az deployment group create `
    --resource-group $ResourceGroup `
    --name $deployName `
    --template-file infra/main.bicep `
    --parameters infra/main.parameters.json `
    --parameters namePrefix=$NamePrefix acrName=$AcrName containerImage=$containerImage `
                 adminToken=$AdminToken openAiApiKey=$OpenAiApiKey openAiModel=$OpenAiModel `
    --query properties.outputs -o json --only-show-errors | ConvertFrom-Json

$appUrl = $outputs.appUrl.value

Write-Host "`n========================================================" -ForegroundColor Yellow
Write-Host " Deployment complete" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Yellow
Write-Host " Candidate URL : $appUrl/"
Write-Host " Recruiter URL : $appUrl/admin"
Write-Host " ADMIN_TOKEN   : $AdminToken"
if (-not $OpenAiApiKey) {
    Write-Host " Mode          : DEMO (offline simulator). Add OPENAI_API_KEY to enable live AI." -ForegroundColor DarkYellow
} else {
    Write-Host " Mode          : OpenAI live role-play." -ForegroundColor DarkGreen
}
Write-Host "========================================================" -ForegroundColor Yellow
