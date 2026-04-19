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
    return Join-Path $ProjectRoot "data\jobs_hub.db"
}

function New-PythonExportScript {
    param(
        [string]$ScriptPath,
        [string]$DbPath,
        [string]$ExcelOutPath
    )

@"
import sqlite3
import pandas as pd
from pathlib import Path

db_path = Path(r"$DbPath")
excel_out = Path(r"$ExcelOutPath")

if not db_path.exists():
    raise SystemExit(f"Erro: Banco de dados não encontrado em {db_path}")

try:
    # Conecta ao banco e lê a tabela jobs
    conn = sqlite3.connect(str(db_path))
    query = "SELECT * FROM jobs"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("Aviso: A tabela 'jobs' está vazia. O arquivo será criado apenas com cabeçalhos.")

    # Garante que a pasta de destino existe
    excel_out.parent.mkdir(parents=True, exist_ok=True)

    # Exporta para Excel
    df.to_excel(excel_out, index=False, engine='openpyxl')
    
    print(f"Sucesso! {len(df)} registros exportados.")
    print(f"Arquivo: {excel_out}")

except Exception as e:
    print(f"Erro durante a exportação: {e}")
    exit(1)
"@ | Set-Content -Path $ScriptPath -Encoding UTF8
}

Write-Step "Exportando tabela JOBS para Excel"

$dbPath = Get-SqliteDbPath
$excelOut = Join-Path $ProjectRoot "logs\jobs_export_$(Get-Date -Format 'yyyyMMdd_HHmm').xlsx"
$tempPy = Join-Path $LogsDir "_export_jobs_to_excel.py"

Write-Host "Banco: $dbPath"
Write-Host "Saída: $excelOut"

# Cria o script Python temporário
New-PythonExportScript `
    -ScriptPath $tempPy `
    -DbPath $dbPath `
    -ExcelOutPath $excelOut

# Comando para rodar no ambiente Conda
$cmdCommand = "call `"$CondaActivateBat`" && conda activate $CondaEnvName && python `"$tempPy`""

# Executa e captura saída
$allOutput = & cmd.exe /c $cmdCommand 2>&1
$exitCode = $LASTEXITCODE

$allOutput

if ($exitCode -ne 0) {
    Write-Error "Falha ao exportar para Excel."
    exit 1
}

Write-Host ""
Write-Host "Processo concluído com sucesso!"
exit 0