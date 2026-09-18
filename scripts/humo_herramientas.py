"""Prueba de humo de la entrega 1: corpus + las cuatro herramientas.

No necesita clave de API: aquí no hay modelo, solo datos y herramientas
invocadas a mano. Si este script termina en HUMO OK, la base está sana y
la siguiente entrega (agente + interfaz) se monta encima.

AVISO: la comprobación 7 carga el modelo de embeddings. La primera vez
descarga ~130 MB de Hugging Face y tarda un par de minutos; después queda
en caché y es instantáneo.

Uso, desde la raíz del repositorio:
    python scripts/humo_herramientas.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agente import datos                                   # noqa: E402
from agente.herramientas import (                          # noqa: E402
    get_xbrl_fact, list_available, read_section, search_filings,
)


def paso(n: int, titulo: str) -> None:
    print(f"\n[{n}] {titulo}")


print("=" * 72)
print("HUMO · entrega 1 — corpus y herramientas (sin modelo, sin clave)")
print("=" * 72)

paso(1, "Preparación y verificación del corpus (hashes + manifiestos)")
datos.preparar_corpus(verbose=True)

paso(2, "list_available: el modelo puede comprobar el mundo")
listado = list_available.invoke({})
print(listado)
assert "NVDA" in listado and "2025" in listado, "list_available incompleto"

paso(3, "get_xbrl_fact: la cifra exacta (NVDA FY2024 Revenues)")
r = get_xbrl_fact.invoke(
    {"ticker": "NVDA", "fiscal_year": 2024, "concept": "Revenues"})
print(r)
assert "60,922,000,000" in r, "El revenue de NVDA FY2024 no cuadra"

paso(4, "get_xbrl_fact: los decimales del EPS sobreviven (AAPL FY2024)")
r = get_xbrl_fact.invoke(
    {"ticker": "AAPL", "fiscal_year": 2024,
     "concept": "EarningsPerShareBasic"})
print(r)
assert "6.11" in r, ("El EPS ha perdido los decimales: el bug de formato "
                     "de la tool de repuesto sigue vivo")

paso(5, "get_xbrl_fact: un hueco real dice 'no reportó' (AMZN GrossProfit)")
r = get_xbrl_fact.invoke(
    {"ticker": "AMZN", "fiscal_year": 2025, "concept": "GrossProfit"})
print(r)
assert "no reportó" in r, "El hueco XBRL debe declararse explícitamente"

paso(6, "get_xbrl_fact: compañía fuera del corpus (TSLA)")
r = get_xbrl_fact.invoke(
    {"ticker": "TSLA", "fiscal_year": 2025, "concept": "Revenues"})
print(r)
assert "No hay datos" in r, "Una compañía ausente debe declararse"

paso(7, "read_section: la vía cara devuelve la sección entera (META 1A)")
texto = read_section.invoke(
    {"ticker": "META", "fiscal_year": 2025, "item": "1A"})
print(f"META FY2025 Item 1A: {len(texto):,} caracteres "
      f"(la sección más larga del corpus, ~34.7k tokens)")
assert len(texto) > 100_000, "La sección llega recortada"

paso(8, "search_filings: búsqueda densa con filtros (carga el codificador)")
t0 = time.perf_counter()
salida = search_filings.invoke({
    "query": "risks from misuse of our AI systems by third parties",
    "ticker": "MSFT", "fiscal_year": 2025, "item": "1A", "k": 3,
})
t1 = time.perf_counter()
print(salida[:600], "…")
print(f"\n(búsqueda + carga del codificador: {t1 - t0:.1f} s; "
      f"las siguientes serán casi instantáneas)")
assert "MSFT-2025-1A-0017" in salida, (
    "El fragmento del riesgo de IA de MSFT (el de la demo de la S1) "
    "debería estar en el top-3 de esta consulta")

print("\n" + "=" * 72)
print("HUMO OK — corpus verificado y cuatro herramientas operativas.")
print("Siguiente entrega: agente/agente.py + agente/interfaz.py "
      "(create_agent, RespuestaFinanciera, responder).")
print("=" * 72)
