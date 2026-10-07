"""OCR locale per documenti scansionati (HG-3 approvato 2026-10-04, opzione A).

Usa il programma `tesseract` già installato, in locale: nessun invio all'esterno, nessuna dipendenza Python nuova.
Il modello linguistico italiano (ita.traineddata) è cercato in $TESSDATA_PREFIX o in ~/tessdata.
Ogni valore letto da OCR deve essere marcato almeno DA VERIFICARE da chi usa questo modulo.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DPI = 300


def disponibile() -> bool:
    return bool(shutil.which("tesseract") and shutil.which("pdftoppm"))


def _tessdata():
    for c in (os.environ.get("TESSDATA_PREFIX"), str(Path.home() / "tessdata")):
        if c and (Path(c) / "ita.traineddata").exists():
            return c
    return None


def _raddrizza(png, env):
    """Ruota l'immagine se tesseract (OSD) rileva una pagina girata."""
    r = subprocess.run(["tesseract", png, "-", "--psm", "0", "-l", "osd"], capture_output=True, env=env, text=True)
    for riga in r.stdout.splitlines():
        if riga.startswith("Rotate:"):
            gradi = int(riga.split(":")[1])
            if gradi:
                from PIL import Image
                im = Image.open(png)
                im.rotate(-gradi, expand=True).save(png)
            return gradi
    return 0


def testo_pagine(pdf, pagine=None):
    """Lista [(n_pagina, testo)] letta con OCR. `pagine` = iterabile di numeri (da 1); None = tutte."""
    if not disponibile():
        raise RuntimeError("tesseract/pdftoppm non disponibili")
    td = _tessdata()
    if not td:
        raise RuntimeError("manca ita.traineddata (cartella ~/tessdata)")
    env = dict(os.environ, TESSDATA_PREFIX=td)
    pdf = str(pdf)
    if pagine is None:
        import pdfplumber
        with pdfplumber.open(pdf) as d:
            pagine = range(1, len(d.pages) + 1)
    risultato = []
    with tempfile.TemporaryDirectory() as tmp:
        for n in pagine:
            base = os.path.join(tmp, f"p{n}")
            subprocess.run(["pdftoppm", "-r", str(DPI), "-f", str(n), "-l", str(n), "-png", "-singlefile", pdf, base],
                           check=True, capture_output=True)
            _raddrizza(base + ".png", env)
            out = subprocess.run(["tesseract", base + ".png", "-", "-l", "ita", "--psm", "6"],
                                 check=True, capture_output=True, env=env, text=True).stdout
            risultato.append((n, out))
            for f in Path(tmp).glob("*.png"):
                f.unlink()
    return risultato
