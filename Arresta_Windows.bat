@echo off
powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select -First 1; if(-not $c){'ANALISI CRISI non e in esecuzione.';exit 0}; $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$c.OwningProcess); if($p.CommandLine -like '*interfaccia_locale.py*'){Stop-Process -Id $c.OwningProcess; 'Fermata. I dati restano salvati.'} else {'Sulla porta 8765 c e un altro programma: non lo chiudo.'}"
pause
