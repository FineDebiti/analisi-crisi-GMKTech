"""Versione del motore, parametri usati, impronta (sha256) e configurazione del motore.

config_motore.json (radice progetto): {"semaforo": "v3"} = pannello Pratica/Valutazione v3 attivo;
{"semaforo": "v2"} = ripristino al comportamento precedente (nessun pannello v3). File assente = {"semaforo": "v3"}.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analisi_crisi import semaforo_v3

MOTORE = "Preanalisi Crisi v1.0-pilota"
RIFERIMENTO_NORMATIVO = "decreto dirigenziale 23/04/2026"
QUI = Path(__file__).resolve().parent
RADICE = QUI.parent
FILE_MOTORE = [QUI / "semaforo_v3.py", RADICE / "relazione_v3.py", QUI / "word_xml.py", QUI / "versione.py", QUI / "pratica.py"]
CONFIG_DEFAULT = {"semaforo": "v3"}


def parametri():
    """Parametri usati dal motore (serializzabili in JSON)."""
    return {"SOGLIE_V3": json.loads(json.dumps(semaforo_v3.SOGLIE_V3)), "riferimento_normativo": RIFERIMENTO_NORMATIVO}


def impronta():
    """sha256 dei file del motore e dei parametri."""
    h = hashlib.sha256()
    for f in FILE_MOTORE:
        h.update(f.name.encode("utf-8") + b"\0")
        h.update(f.read_bytes() if f.is_file() else b"<ASSENTE>")
        h.update(b"\0")
    h.update(json.dumps(parametri(), sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


def leggi_config(percorso=None):
    p = Path(percorso) if percorso else RADICE / "config_motore.json"
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(c, dict) and c.get("semaforo") in ("v2", "v3"):
            return c
    except (OSError, ValueError):
        pass
    return dict(CONFIG_DEFAULT)


def semaforo_attivo(percorso=None):
    return leggi_config(percorso)["semaforo"]
