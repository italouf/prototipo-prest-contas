# Baixa assets JS pinados para static/js/vendor/ (executar uma vez; arquivos são commitados).
$ErrorActionPreference = "Stop"
$destino = Join-Path $PSScriptRoot "..\static\js\vendor"
New-Item -ItemType Directory -Force -Path $destino | Out-Null

$assets = @(
  @{ Url = "https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js"; Arquivo = "htmx.min.js" },
  @{ Url = "https://unpkg.com/alpinejs@3.17.2/dist/cdn.min.js"; Arquivo = "alpine.min.js" },
  @{ Url = "https://unpkg.com/chart.js@4.5.1/dist/chart.umd.js"; Arquivo = "chart.umd.js" }
)

foreach ($asset in $assets) {
  $caminho = Join-Path $destino $asset.Arquivo
  Invoke-WebRequest -Uri $asset.Url -OutFile $caminho
  # Remove sourceMappingURL (o .map não é vendorizado e quebra o
  # pós-processamento do Whitenoise/ManifestStaticFilesStorage).
  $texto = Get-Content $caminho -Raw
  $texto = $texto -replace '(?m)^//# sourceMappingURL=.*\r?\n?', ''
  [IO.File]::WriteAllText($caminho, $texto, [System.Text.UTF8Encoding]::new($false))
  Write-Output ("{0} ({1:N0} bytes)" -f $asset.Arquivo, (Get-Item $caminho).Length)
}
