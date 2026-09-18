"""Prueba de humo de la entrega 2: el agente baseline de punta a punta.

Necesita OPENROUTER_API_KEY en el entorno y cuesta dinero de verdad
(orden de 10-15 céntimos en total con gemini-3.8-flash). Tres preguntas,
cada una con un propósito:

  1. Numérica pura — lo que TIENE que salir bien: get_xbrl_fact en la
     trayectoria, cifra exacta, fuente 'xbrl'. Aquí hay asserts duros.
  2. Extractiva — búsqueda + cita con chunk_id. Asserts blandos: el
     enrutado debe ser correcto; el chunk exacto puede variar.
  3. La trampa de Alphabet (of-012 del golden oficial) — SIN asserts:
     esta pregunta existe para OBSERVAR el baseline. Alphabet etiqueta
     'Revenues'; si el modelo pide el concepto largo de Apple, la
     herramienta le lista los disponibles. Lo que haga con ese aviso
     (corregirse o rellenar) es exactamente lo que el guardrail de la
     siguiente entrega convierte en garantía.

Uso, desde la raíz del repositorio y con el venv activado:
    export OPENROUTER_API_KEY='sk-or-...'
    python scripts/humo_agente.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if not os.environ.get("OPENROUTER_API_KEY"):
    print("Falta OPENROUTER_API_KEY en el entorno.\n"
          "  export OPENROUTER_API_KEY='sk-or-...'   (se saca en "
          "openrouter.ai/keys)\n"
          "y vuelve a lanzar este script.")
    sys.exit(1)

from agente import trazas                                  # noqa: E402
from agente.agente import RespuestaFinanciera              # noqa: E402
from agente.interfaz import responder                      # noqa: E402


def cabecera(n: int, titulo: str, pregunta: str) -> None:
    print("\n" + "=" * 72)
    print(f"[{n}] {titulo}")
    print("=" * 72)
    print(f"PREGUNTA: {pregunta}\n")


coste_total = 0.0

# ---------------------------------------------------------------------
# 1 · Numérica pura — asserts duros
# ---------------------------------------------------------------------
P1 = "¿Cuál fue el revenue de NVIDIA en el ejercicio fiscal 2024?"
cabecera(1, "Numérica: la cifra exacta por el camino exacto", P1)

r1 = responder(P1, thread_id="humo-1")
trazas.pretty_trace(r1)
print(f"\n  [{r1['latencia_s']:.1f} s · {r1['coste_usd'] * 100:.2f} ¢ · "
      f"tokens {trazas.tokens_de(r1)}]")
coste_total += r1["coste_usd"]

e1 = r1["structured_response"]
usadas1 = trazas.herramientas_usadas(r1)
assert isinstance(e1, RespuestaFinanciera), "La salida no validó el esquema"
assert "get_xbrl_fact" in usadas1, (
    "Pregunta numérica sin pasar por get_xbrl_fact: fallo de enrutado "
    "aunque la cifra saliera bien (lección central del curso)")
assert e1.cifra is not None and abs(e1.cifra - 60_922_000_000) / 60_922_000_000 <= 0.01, \
    f"Cifra fuera de tolerancia: {e1.cifra}"
assert e1.fuente in {"xbrl", "ambas"}, f"Fuente inesperada: {e1.fuente}"
print("  ✓ trayectoria por get_xbrl_fact, cifra dentro del 1 %, "
      f"fuente '{e1.fuente}', concept_xbrl={e1.concept_xbrl!r}")

# ---------------------------------------------------------------------
# 2 · Extractiva — asserts de enrutado
# ---------------------------------------------------------------------
P2 = ("¿Qué dice Microsoft en su 10-K de FY2025 sobre el uso indebido de "
      "sus sistemas de IA por parte de terceros?")
cabecera(2, "Extractiva: búsqueda en el texto + cita verificable", P2)

r2 = responder(P2, thread_id="humo-2")
trazas.pretty_trace(r2)
print(f"\n  [{r2['latencia_s']:.1f} s · {r2['coste_usd'] * 100:.2f} ¢]")
coste_total += r2["coste_usd"]

e2 = r2["structured_response"]
usadas2 = trazas.herramientas_usadas(r2)
assert "search_filings" in usadas2, "Extractiva sin search_filings"
if e2.chunk_id:
    print(f"  ✓ búsqueda usada y cita anclada a {e2.chunk_id}")
else:
    print("  ~ búsqueda usada, pero sin chunk_id en la respuesta: apuntar "
          "como fallo de baseline (el evaluador de citas lo penalizará)")

# ---------------------------------------------------------------------
# 3 · La trampa de Alphabet — solo observar
# ---------------------------------------------------------------------
P3 = "¿Cuáles fueron los ingresos de Alphabet en 2025?"
cabecera(3, "La trampa del concepto (of-012): observar, no asertar", P3)

r3 = responder(P3, thread_id="humo-3")
trazas.pretty_trace(r3)
print(f"\n  [{r3['latencia_s']:.1f} s · {r3['coste_usd'] * 100:.2f} ¢]")
coste_total += r3["coste_usd"]

e3 = r3["structured_response"]
esperada3 = 402_836_000_000
if e3.cifra is not None and abs(e3.cifra - esperada3) / esperada3 <= 0.01:
    print("  ✓ el baseline sorteó la trampa (¿pidió 'Revenues' a la "
        "primera, o se corrigió tras el aviso de la herramienta? Míralo "
        "en la trayectoria de arriba)")
else:
    print(f"  ✗ el baseline cayó en la trampa: afirmó {e3.cifra!r} "
          f"(esperado ~{esperada3:,}). Este fallo es EXACTAMENTE el que "
          f"cierra el middleware de verificación de la próxima entrega — "
          f"guarda esta salida, es material del informe.")

# ---------------------------------------------------------------------
print("\n" + "=" * 72)
print(f"HUMO AGENTE COMPLETADO · coste total de este humo: "
      f"{coste_total * 100:.1f} ¢")
print("Las tres trayectorias de arriba son el primer retrato del "
      "baseline: guárdalas.")
print("=" * 72)
