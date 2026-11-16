param(
    [ValidateRange(1,30)][int]$Seconds = 20,
    [switch]$UpdatePi
)

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$logPath = Join-Path $project 'runs/pi_balance_live.jsonl'
$connection = Get-Content -Raw (Join-Path $project 'deployment/pi/connection.local.json') | ConvertFrom-Json
$piTarget = $connection.target
$remote = $connection.remote_dir

if ($UpdatePi) {
    scp (Join-Path $project 'deployment/pi/rmd_policy_shadow.py') "${piTarget}:${remote}/deployment/pi/"
    if ($LASTEXITCODE -ne 0) { throw 'Pi telemetry update failed.' }
}

ssh -T $piTarget "cd $remote && python3 -m deployment.pi.rmd_policy_shadow deployment/pi/rmd_x6_48v.json runs/balance_lqr_ppo_s42/export --seconds $Seconds --telemetry 2>&1" |
    Tee-Object -FilePath $logPath
if ($LASTEXITCODE -ne 0) { throw 'Pi telemetry ended with an error. See the terminal or dashboard status.' }
