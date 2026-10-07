#!/bin/bash
# Raccoglie i fatti dell'ambiente GMKtec (Linux o WSL) e il modello EFFETTIVAMENTE in esecuzione. NON installa nulla e NON modifica nulla.
# Uso: bash verifica_ambiente.sh        -> scrive anche report_ambiente.txt (da mandare a Claude/Aurelio)
cd "$(dirname "$0")" || exit 1
OUT=report_ambiente.txt
{
echo "=== REPORT AMBIENTE $(date -Is) ==="
echo "--- Sistema"; uname -a; grep -E '^(PRETTY_NAME|VERSION)=' /etc/os-release 2>/dev/null
grep -qi microsoft /proc/version 2>/dev/null && echo "WSL: SI ($(grep -o 'microsoft[^ ]*' /proc/version | head -1))" || echo "WSL: no"
echo "--- CPU/RAM"; lscpu 2>/dev/null | grep -E 'Model name|^CPU\(s\)|Thread' ; free -h 2>/dev/null | head -2
echo "--- GPU"; (nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>/dev/null || (rocm-smi --showproductname --showmeminfo vram 2>/dev/null) || lspci 2>/dev/null | grep -iE 'vga|3d|display' || echo "nessuna GPU rilevata dai comandi standard")
echo "--- Python"; for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do command -v $c >/dev/null 2>&1 && echo "$c -> $($c --version 2>&1) ($(command -v $c))"; done
python3 -c "import venv, ensurepip; print('modulo venv/ensurepip: OK')" 2>&1 | tail -1
echo "--- OCR locale"; for c in tesseract pdftoppm; do command -v $c >/dev/null 2>&1 && echo "$c: $(command -v $c)" || echo "$c: MANCANTE"; done
ls "${TESSDATA_PREFIX:-$HOME/tessdata}"/ita.traineddata 2>/dev/null || echo "ita.traineddata: non trovato in ${TESSDATA_PREFIX:-$HOME/tessdata}"
echo "--- Software di esecuzione del modello (presenza comandi)"; for c in llama-server llama-cli ollama lms vllm koboldcpp; do command -v $c >/dev/null 2>&1 && echo "$c: $(command -v $c)"; done
echo "--- Endpoint locali (solo loopback)"
for u in "http://127.0.0.1:8080/v1/models" "http://127.0.0.1:11434/v1/models" "http://127.0.0.1:1234/v1/models"; do
  r=$(curl -s -m 5 "$u" 2>/dev/null); [ -n "$r" ] && echo "RISPONDE $u -> $r" | cut -c1-600 || echo "nessuna risposta: $u"; done
echo "--- llama.cpp /props (contesto n_ctx, modello)"; curl -s -m 5 http://127.0.0.1:8080/props 2>/dev/null | cut -c1-900
echo "--- Ollama: modelli e dettagli (quantizzazione, contesto)"
if command -v ollama >/dev/null 2>&1; then ollama list 2>&1 | head -20; for m in $(ollama list 2>/dev/null | awk 'NR>1{print $1}'); do echo "## $m"; ollama show "$m" 2>&1 | head -25; done; fi
echo "--- File modello (.gguf) nelle cartelle comuni"
find "$HOME/models" "$HOME/.cache/lm-studio" "$HOME/.lmstudio" "$HOME/.ollama" "$HOME/llama.cpp" /opt/models /mnt -maxdepth 6 \( -iname '*.gguf' -o -iname '*qwen*' \) -type f 2>/dev/null | head -40 | while read -r f; do echo "$(du -h "$f" | cut -f1)  $f"; done
echo "--- Fine. Nome esatto, quantizzazione e contesto vanno copiati in llm_config.json (modello / quantizzazione / contesto_configurato)."
} 2>&1 | tee "$OUT"
echo; echo "Report salvato in $(pwd)/$OUT"
