# run_gates.ps1 — aggrega i 4 gate di FlexForge. Struttura copiata da ACTD.
#
# Gate eseguiti in sequenza, ognuno con il proprio verdetto:
#   1. py_compile via BlenderPython su flexforge\*.py (ricorsivo)
#   2. suite completa via run_tests.ps1 (tutti i tests\test_*.py)
#   3. installazione isolata via install_isolated.py sullo ZIP in dist\
#   4. audit ZIP via audit_zip.py sullo stesso ZIP
#
# Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\run_gates.ps1
#   ... -Zip dist\flexforge-1.0.2.zip
#
# Output finale: "ALL_GATES_OK | ..." se tutti i gate passano, altrimenti
# "GATE_FAIL | gate=<n> | ..." con la riga specifica del gate fallito.
# Exit code: 0 = ALL_GATES_OK, 1 = GATE_FAIL.
param(
    [string]$Blender = "",
    [string]$Zip = "",
    [string]$TaskTag = ""
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

$root = (Get-Item "$PSScriptRoot\..\..").FullName
. (Join-Path $PSScriptRoot "find_blender.ps1")
$install = Get-BlenderInstall -HintExe $Blender
$exe = $install.BlenderExe
$py = $install.BlenderPython
if (-not $py -or -not (Test-Path $py)) { throw "Python di Blender non trovato: $py" }
if (-not (Test-Path $exe)) { throw "Blender non trovato: $exe" }

function Fail-Gate {
    param([string]$Line)
    Write-Output $Line
    exit 1
}

# Risoluzione ZIP: parametro, altrimenti il piu' recente in dist\.
$zipPath = ""
if ($Zip) {
    $zipPath = if ([IO.Path]::IsPathRooted($Zip)) { $Zip } else { Join-Path $root $Zip }
} else {
    $distDir = Join-Path $root "dist"
    $candidate = Get-ChildItem $distDir -Filter "*.zip" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($candidate) { $zipPath = $candidate.FullName }
}
if (-not $zipPath -or -not (Test-Path $zipPath)) {
    Fail-Gate "GATE_FAIL | gate=3 | reason=ZIP_NOT_FOUND | zip=$zipPath | task=$TaskTag"
}

Push-Location $root
try {
    # --- Gate 1: py_compile via BlenderPython ---------------------------------
    $targets = @(Get-ChildItem (Join-Path $root "flexforge") -Filter "*.py" -File -Recurse |
        ForEach-Object { $_.FullName })
    if ($targets.Count -eq 0) {
        Fail-Gate "GATE_FAIL | gate=1 | reason=NO_SOURCES | task=$TaskTag"
    }
    $prevEA = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $compileOut = & $py -m py_compile @targets 2>&1
        $compileExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEA
    }
    if ($compileExit -ne 0) {
        $detail = ($compileOut | Select-Object -First 3) -join " | "
        Fail-Gate "GATE_FAIL | gate=1 | reason=PY_COMPILE_ERROR | detail=$detail | task=$TaskTag"
    }
    Write-Output ("GATE_OK | gate=1 | py_compile | files={0}" -f $targets.Count)

    # --- Gate 2: suite completa via run_tests.ps1 -----------------------------
    $runner = Join-Path $PSScriptRoot "run_tests.ps1"
    $prevEA = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $psExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }
        $testOut = & $psExe -NoProfile -ExecutionPolicy Bypass -File $runner -Blender $exe 2>&1
        $testExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEA
    }
    $risultato = @($testOut | Where-Object { "$_" -match '^RISULTATO ' })
    foreach ($line in $testOut) { Write-Output "$line" }
    if ($testExit -ne 0 -or $risultato.Count -eq 0 -or "$($risultato[-1])" -notmatch 'falliti=0') {
        $rLine = if ($risultato.Count -gt 0) { "$($risultato[-1])" } else { "RISULTATO assente" }
        Fail-Gate "GATE_FAIL | gate=2 | reason=TESTS_FAILED | $rLine | exit=$testExit | task=$TaskTag"
    }
    Write-Output ("GATE_OK | gate=2 | tests | {0}" -f "$($risultato[-1])")

    # --- Gate 3: installazione isolata ----------------------------------------
    $prevEA = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $installOut = & $py (Join-Path $PSScriptRoot "install_isolated.py") --zip $zipPath --blender $exe 2>&1
        $installExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEA
    }
    $installLine = @($installOut | Where-Object { "$_" -match '^INSTALL_' })
    foreach ($line in $installOut) { Write-Output "$line" }
    if ($installExit -ne 0 -or $installLine.Count -eq 0 -or "$($installLine[-1])" -notmatch '^INSTALL_OK') {
        $iLine = if ($installLine.Count -gt 0) { "$($installLine[-1])" } else { "INSTALL_FAIL | exit=$installExit" }
        Fail-Gate "GATE_FAIL | gate=3 | $iLine | task=$TaskTag"
    }
    Write-Output "GATE_OK | gate=3 | install_isolated"

    # --- Gate 4: audit ZIP ------------------------------------------------------
    $prevEA = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $auditOut = & $py (Join-Path $PSScriptRoot "audit_zip.py") $zipPath 2>&1
        $auditExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEA
    }
    $auditLine = @($auditOut | Where-Object { "$_" -match '^ZIP_AUDIT_' })
    foreach ($line in $auditOut) { Write-Output "$line" }
    if ($auditExit -ne 0 -or $auditLine.Count -eq 0 -or "$($auditLine[-1])" -notmatch '^ZIP_AUDIT_OK') {
        $aLine = if ($auditLine.Count -gt 0) { "$($auditLine[-1])" } else { "ZIP_AUDIT_FAIL | exit=$auditExit" }
        Fail-Gate "GATE_FAIL | gate=4 | $aLine | task=$TaskTag"
    }
    Write-Output "GATE_OK | gate=4 | audit_zip"

    Write-Output ("ALL_GATES_OK | gates=4/4 | zip={0} | task={1}" -f (Split-Path -Leaf $zipPath), $TaskTag)
    exit 0
}
finally {
    Pop-Location
}
