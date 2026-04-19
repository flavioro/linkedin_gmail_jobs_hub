$ProjectRoot = "D:\Python\projetos\gmail_linkedin\linkedin_gmail_jobs_hub"
$CondaActivateBat = "D:\Python\anaconda3\Scripts\activate.bat"
$CondaEnvName = "linkedin_gmail_jobs_hub"

$ApiHost = "127.0.0.1"
$ApiPort = 8000
$ApiBaseUrl = "http://$ApiHost`:$ApiPort"
$ApiKey = "change-me"

$JobUrls = @(
    "https://www.linkedin.com/jobs/view/4400740159"
)

$LogsDir = Join-Path $ProjectRoot "logs"
$ResponsesDir = Join-Path $LogsDir "responses"

if (!(Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

if (!(Test-Path $ResponsesDir)) {
    New-Item -ItemType Directory -Path $ResponsesDir -Force | Out-Null
}
