param(
    [string]$NiVivadoRoot = 'C:\NIFPGA\programs\Vivado2021_1',
    [switch]$ShowPathEntries,
    [switch]$ExportReport
)

$ErrorActionPreference = 'Continue'

function Test-PathInfo {
    param([string]$PathToTest)
    [pscustomobject]@{
        Path   = $PathToTest
        Exists = Test-Path -LiteralPath $PathToTest
        Type   = if (Test-Path -LiteralPath $PathToTest) { (Get-Item -LiteralPath $PathToTest).PSIsContainer ? 'Directory' : 'File' } else { 'Missing' }
    }
}

function Find-GccCandidates {
    param([string[]]$Roots)
    $found = @()
    foreach ($root in $Roots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        try {
            $found += Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^(gcc|g\+\+)\.exe$' } |
                Select-Object FullName
        } catch {}
    }
    $found | Sort-Object FullName -Unique
}

function Write-Section {
    param([string]$Title)
    Write-Host "`n=== $Title ===" -ForegroundColor Cyan
}

$report = [System.Collections.Generic.List[object]]::new()
function Add-ReportLine {
    param([string]$Category,[string]$Item,[string]$Value)
    $report.Add([pscustomobject]@{Category=$Category; Item=$Item; Value=$Value}) | Out-Null
}

Write-Host 'NI FPGA / Vivado 2021.1 GCC Environment Check' -ForegroundColor Yellow
Write-Host ('Timestamp: ' + (Get-Date).ToString('s'))
Write-Host ('Computer : ' + $env:COMPUTERNAME)
Write-Host ('User     : ' + $env:USERNAME)

Write-Section 'Environment Variables'
$envVars = @('XILINX','XILINX_VIVADO','XILINX_VIVADO_HLS','GCC_SIM_EXE_PATH','PATH')
foreach ($name in $envVars) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($name, 'Machine')
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($name, 'User')
    }
    Write-Host ("{0,-18}: {1}" -f $name, ($(if ($value) { $value } else { '<not set>' })))
    Add-ReportLine 'Environment' $name ($(if ($value) { $value } else { '<not set>' }))
}

Write-Section 'NI Vivado Root Checks'
$pathsToCheck = @(
    $NiVivadoRoot,
    (Join-Path $NiVivadoRoot 'bin'),
    (Join-Path $NiVivadoRoot 'bin\unwrapped\win64.o'),
    (Join-Path $NiVivadoRoot 'tps'),
    (Join-Path $NiVivadoRoot 'tps\win64'),
    (Join-Path $NiVivadoRoot 'tps\win64\jre11.0.2'),
    (Join-Path $NiVivadoRoot 'lib'),
    (Join-Path $NiVivadoRoot 'data'),
    (Join-Path $NiVivadoRoot 'data\xsim'),
    (Join-Path $NiVivadoRoot 'data\xsim\include')
)

foreach ($p in $pathsToCheck) {
    $info = Test-PathInfo -PathToTest $p
    Write-Host ("{0,-70} {1}" -f $info.Path, $(if ($info.Exists) { 'OK' } else { 'MISSING' }))
    Add-ReportLine 'PathCheck' $info.Path ($(if ($info.Exists) { 'OK' } else { 'MISSING' }))
}

Write-Section 'Executable Checks'
$exeChecks = @(
    (Join-Path $NiVivadoRoot 'bin\vivado.bat'),
    (Join-Path $NiVivadoRoot 'bin\xelab.bat'),
    (Join-Path $NiVivadoRoot 'bin\xvhdl.bat'),
    (Join-Path $NiVivadoRoot 'bin\unwrapped\win64.o\xelab.exe'),
    (Join-Path $NiVivadoRoot 'bin\unwrapped\win64.o\xvhdl.exe')
)
foreach ($p in $exeChecks) {
    $info = Test-PathInfo -PathToTest $p
    Write-Host ("{0,-70} {1}" -f $info.Path, $(if ($info.Exists) { 'OK' } else { 'MISSING' }))
    Add-ReportLine 'Executable' $info.Path ($(if ($info.Exists) { 'OK' } else { 'MISSING' }))
}

Write-Section 'PATH Scan'
$pathEntries = ($env:PATH -split ';' | Where-Object { $_ -and $_.Trim() -ne '' })
$vivadoEntries = $pathEntries | Where-Object { $_ -match 'Xilinx|Vivado|NIFPGA' }
if ($vivadoEntries) {
    $vivadoEntries | ForEach-Object { Write-Host $_ }
    foreach ($e in $vivadoEntries) { Add-ReportLine 'PATH' 'VivadoRelated' $e }
} else {
    Write-Host 'No Vivado/Xilinx/NI FPGA entries found in PATH.' -ForegroundColor DarkYellow
    Add-ReportLine 'PATH' 'VivadoRelated' '<none found>'
}

if ($ShowPathEntries) {
    Write-Section 'Full PATH Entries'
    $pathEntries | ForEach-Object { Write-Host $_ }
}

Write-Section 'GCC Candidate Search'
$searchRoots = @(
    $NiVivadoRoot,
    'C:\Xilinx',
    'C:\Program Files\Xilinx',
    'C:\Program Files (x86)\Xilinx',
    'C:\mingw64',
    'C:\msys64',
    'C:\Strawberry',
    'C:\TDM-GCC-64',
    'C:\TDM-GCC-32'
)
$gccCandidates = Find-GccCandidates -Roots $searchRoots
if ($gccCandidates) {
    $gccCandidates | ForEach-Object {
        Write-Host $_.FullName
        Add-ReportLine 'GCC' 'Candidate' $_.FullName
    }
} else {
    Write-Host 'No gcc.exe or g++.exe found in common locations.' -ForegroundColor Red
    Add-ReportLine 'GCC' 'Candidate' '<none found>'
}

Write-Section 'Likely Diagnosis'
$xilinxVar = [Environment]::GetEnvironmentVariable('XILINX', 'Process')
if ([string]::IsNullOrWhiteSpace($xilinxVar)) {
    $xilinxVar = [Environment]::GetEnvironmentVariable('XILINX', 'Machine')
}
if ([string]::IsNullOrWhiteSpace($xilinxVar)) {
    $xilinxVar = [Environment]::GetEnvironmentVariable('XILINX', 'User')
}

$jreMissing = -not (Test-Path -LiteralPath (Join-Path $NiVivadoRoot 'tps\win64\jre11.0.2'))
$niRootMissing = -not (Test-Path -LiteralPath $NiVivadoRoot)
$gccMissing = -not $gccCandidates

if ($niRootMissing) {
    Write-Host 'NI Vivado root is missing. NI FPGA compile tools likely not installed correctly.' -ForegroundColor Red
    Add-ReportLine 'Diagnosis' 'Primary' 'NI Vivado root missing'
} elseif ($jreMissing) {
    Write-Host 'NI Vivado install appears incomplete: jre11.0.2 path is missing, matching your warning.' -ForegroundColor Red
    Add-ReportLine 'Diagnosis' 'Primary' 'Vivado runtime incomplete or corrupted (missing jre11.0.2)'
} elseif ($xilinxVar -and ($xilinxVar -ne $NiVivadoRoot)) {
    Write-Host ('XILINX env var points somewhere else: ' + $xilinxVar) -ForegroundColor Yellow
    Write-Host 'This may override the NI-bundled Vivado path used by LabVIEW FPGA.' -ForegroundColor Yellow
    Add-ReportLine 'Diagnosis' 'Primary' 'XILINX variable may be overriding NI path'
} elseif ($gccMissing) {
    Write-Host 'No GCC candidate was found. XSIM may be failing because it cannot find a C compiler toolchain.' -ForegroundColor Red
    Add-ReportLine 'Diagnosis' 'Primary' 'No GCC found in common locations'
} else {
    Write-Host 'Basic path checks look reasonable. If XSIM still fails, repair the NI Vivado 2021.1 install and clear custom XILINX/GCC_SIM_EXE_PATH overrides.' -ForegroundColor Green
    Add-ReportLine 'Diagnosis' 'Primary' 'Paths mostly OK; investigate overrides or repair install'
}

Write-Section 'Suggested Actions'
$actions = @(
    '1. If XILINX is set to a non-NI path, remove or correct it.',
    '2. If C:\NIFPGA\programs\Vivado2021_1\tps\win64\jre11.0.2 is missing, repair or reinstall NI FPGA compile tools.',
    '3. If GCC_SIM_EXE_PATH is set incorrectly, clear it or point it to a valid GCC bin folder.',
    '4. Reboot after environment-variable changes, then rerun LabVIEW FPGA syntax check.',
    '5. If needed, rerun this script with -ExportReport and send the CSV to support.'
)
$actions | ForEach-Object {
    Write-Host $_
    Add-ReportLine 'Action' 'Suggested' $_
}

if ($ExportReport) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $csv = Join-Path $PWD ("NIFPGA_Vivado_GCC_Report_$stamp.csv")
    $report | Export-Csv -NoTypeInformation -Path $csv -Encoding UTF8
    Write-Section 'Report Exported'
    Write-Host $csv -ForegroundColor Green
}
