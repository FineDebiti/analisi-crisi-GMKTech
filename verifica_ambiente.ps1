# Raccoglie i fatti dell'ambiente Windows e il modello in esecuzione. NON installa nulla. Uso: powershell -ExecutionPolicy Bypass -File verifica_ambiente.ps1
$out = "report_ambiente.txt"
$r = @()
$r += "=== REPORT AMBIENTE $(Get-Date -Format s) ==="
$r += "--- Sistema"; $r += (Get-CimInstance Win32_OperatingSystem | Select Caption,Version,OSArchitecture | Out-String)
$r += (Get-CimInstance Win32_Processor | Select Name,NumberOfCores | Out-String); $r += (Get-CimInstance Win32_ComputerSystem | Select @{n='RAM_GB';e={[math]::Round($_.TotalPhysicalMemory/1GB,1)}} | Out-String)
$r += "--- GPU"; $r += (Get-CimInstance Win32_VideoController | Select Name,AdapterRAM,DriverVersion | Out-String); try { $r += (nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv) } catch {}
$r += "--- Python"; try { $r += (py -0p 2>&1 | Out-String) } catch { $r += "py launcher non trovato" }
$r += "--- WSL"; try { $r += (wsl -l -v 2>&1 | Out-String) } catch { $r += "WSL non disponibile" }
$r += "--- OCR"; foreach ($c in "tesseract","pdftoppm") { $r += "$c : $((Get-Command $c -ErrorAction SilentlyContinue).Source)" }
$r += "--- Software modello"; foreach ($c in "llama-server","ollama","lms") { $x = Get-Command $c -ErrorAction SilentlyContinue; if ($x) { $r += "$c : $($x.Source)" } }
$r += "--- Endpoint locali"
foreach ($u in "http://127.0.0.1:8080/v1/models","http://127.0.0.1:11434/v1/models","http://127.0.0.1:1234/v1/models") { try { $r += "RISPONDE $u -> " + (Invoke-RestMethod $u -TimeoutSec 5 | ConvertTo-Json -Depth 4 -Compress) } catch { $r += "nessuna risposta: $u" } }
try { $r += "--- llama.cpp /props"; $r += (Invoke-RestMethod http://127.0.0.1:8080/props -TimeoutSec 5 | ConvertTo-Json -Depth 4 -Compress) } catch {}
if (Get-Command ollama -ErrorAction SilentlyContinue) { $r += "--- ollama"; $r += (ollama list | Out-String); foreach ($m in (ollama list | Select -Skip 1 | % { ($_ -split '\s+')[0] })) { $r += "## $m"; $r += (ollama show $m | Out-String) } }
$r += "--- File .gguf"; $r += (Get-ChildItem $HOME -Recurse -Filter *.gguf -ErrorAction SilentlyContinue -Depth 6 | Select -First 40 FullName,@{n='GB';e={[math]::Round($_.Length/1GB,1)}} | Out-String)
$r | Tee-Object -FilePath $out
"Report salvato in $out"
