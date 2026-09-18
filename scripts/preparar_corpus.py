"""Extrae y verifica el corpus desde dataset/*.zip. Idempotente.

Equivale a la celda de setup de clase. `agente.datos.dir_corpus()` hace
esto mismo solo si hace falta; el script existe para poder lanzarlo a mano
y ver la verificación con detalle.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agente import datos  # noqa: E402

datos.preparar_corpus(verbose=True)
