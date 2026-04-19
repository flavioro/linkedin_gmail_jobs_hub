$ErrorActionPreference = "Stop"
. "$PSScriptRoot\config.ps1"

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "=================================================="
    Write-Host $Message
    Write-Host "=================================================="
}

function Get-SqliteDbPath {
    $defaultDbPath = Join-Path $ProjectRoot "data\jobs_hub.db"
    return $defaultDbPath
}

function New-PythonInspectorScript {
    param(
        [string]$ScriptPath,
        [string]$DbPath,
        [string]$JsonOutPath,
        [string]$TxtOutPath
    )

@"
import json
import sqlite3
from pathlib import Path
from datetime import datetime

db_path = Path(r"$DbPath")
json_out = Path(r"$JsonOutPath")
txt_out = Path(r"$TxtOutPath")

if not db_path.exists():
    raise SystemExit(f"Banco não encontrado: {db_path}")

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

tables = conn.execute(
    '''
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
    '''
).fetchall()

results = []
for row in tables:
    table_name = row["name"]
    count = conn.execute(f'SELECT COUNT(*) AS total FROM "{table_name}"').fetchone()["total"]
    results.append({
        "table_name": table_name,
        "row_count": count
    })

payload = {
    "generated_at": datetime.now().isoformat(),
    "database_path": str(db_path),
    "tables": results
}

json_out.parent.mkdir(parents=True, exist_ok=True)
txt_out.parent.mkdir(parents=True, exist_ok=True)

json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

lines = []
lines.append("Resumo do banco SQLite")
lines.append(f"Gerado em: {payload['generated_at']}")
lines.append(f"Banco: {payload['database_path']}")
lines.append("")
lines.append("Tabelas e quantidades:")
for item in results:
    lines.append(f"- {item['table_name']}: {item['row_count']} registro(s)")

txt_out.write_text("\n".join(lines), encoding="utf-8")

print("")
print("Banco analisado:", db_path)
print("")
print("Tabelas encontradas:")
for item in results:
    print(f"- {item['table_name']}: {item['row_count']} registro(s)")
print("")
print("JSON:", json_out)
print("TXT :", txt_out)

conn.close()
"@ | Set-Content -Path $ScriptPath -Encoding UTF8
}

Write-Step "Inspecionando tabelas do banco"

$dbPath = Get-SqliteDbPath
$jsonOut = Join-Path $LogsDir "db_tables_summary.json"
$txtOut = Join-Path $LogsDir "db_tables_summary.txt"
$tempPy = Join-Path $LogsDir "_inspect_sqlite_tables.py"

Write-Host "Banco: $dbPath"
Write-Host "JSON:  $jsonOut"
Write-Host "TXT:   $txtOut"

if (!(Test-Path $dbPath)) {
    throw "Banco não encontrado em: $dbPath"
}

New-PythonInspectorScript `
    -ScriptPath $tempPy `
    -DbPath $dbPath `
    -JsonOutPath $jsonOut `
    -TxtOutPath $txtOut

$cmdCommand = "call `"$CondaActivateBat`" && conda activate $CondaEnvName && cd /d `"$ProjectRoot`" && python `"$tempPy`""

$allOutput = & cmd.exe /c $cmdCommand 2>&1
$exitCode = $LASTEXITCODE

$runLog = Join-Path $LogsDir "db_tables_run.log"
$allOutput | Out-File -FilePath $runLog -Encoding utf8

$allOutput

if ($exitCode -ne 0) {
    throw "Falha ao inspecionar banco. Veja: $runLog"
}

Write-Host ""
Write-Host "Resumo do banco gerado com sucesso."
Write-Host "run log: $runLog"
Write-Host "json   : $jsonOut"
Write-Host "txt    : $txtOut"
exit 0