param(
    [string]$Source = "tank3_lvrt.c",
    [string]$Output = "tank3_lvrt.so",
    [string]$Compiler = "wsl x86_64-linux-gnu-gcc"
)

$cmd = "$Compiler -O2 -shared -fPIC -Wall -Wextra -std=c99 -D_GNU_SOURCE -o $Output $Source -lm"
Write-Host "Building NI Linux RT shared library..."
Write-Host $cmd
Invoke-Expression $cmd
if ($LASTEXITCODE -ne 0) {
    throw "Build failed with exit code $LASTEXITCODE"
}
Write-Host "Build complete: $Output"
