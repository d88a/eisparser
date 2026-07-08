param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Get-StatusCode($url) {
    try {
        $resp = Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -TimeoutSec 10
        return [int]$resp.StatusCode
    }
    catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            return [int]$_.Exception.Response.StatusCode.value__
        }
        return -1
    }
}

$healthUrl = "$BaseUrl/api/health"
$publicUrl = "$BaseUrl/public/zakupki"

$healthCode = Get-StatusCode $healthUrl
$publicCode = Get-StatusCode $publicUrl
$healthStatus = "unknown"

try {
    $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 10
    if ($health.status) {
        $healthStatus = [string]$health.status
    }
}
catch {
    # keep unknown
}

Write-Output "GET $healthUrl -> $healthCode"
Write-Output "GET $publicUrl -> $publicCode"
Write-Output "health.status = $healthStatus"
