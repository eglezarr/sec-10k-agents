"""Prueba de humo de los guardrails, SIN clave de API.

Comprueba tres cosas:
  1. Las reglas del verificador sobre las cifras de una comparación
     (`cifra_anterior` y `variacion_pct`), con datos XBRL reales.
  2. Que sin esos campos el comportamiento es el de siempre.
  3. El bucle completo dentro de un agente de LangChain, con un modelo de
     mentira que primero responde mal y luego bien.

Uso:  python scripts/humo_guardrails.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain.agents import create_agent  # noqa: E402
from langchain.agents.structured_output import ToolStrategy  # noqa: E402
from langchain.tools import tool  # noqa: E402
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

from agente import guardrails  # noqa: E402
from agente.agente import RespuestaFinanciera  # noqa: E402

# Microsoft, gasto en I+D: 29.510 M en FY2024 y 32.488 M en FY2025 (+10,1 %)
BASE = dict(respuesta="x", fuente="ambas", ticker="MSFT", ejercicio=2025,
            concept_xbrl="ResearchAndDevelopmentExpense", cifra=32488000000.0,
            cifra_anterior=29510000000.0, variacion_pct=10.1)


def resp(**cambios):
    return RespuestaFinanciera(**{**BASE, **cambios})


CASOS = [   # (caso, respuesta, ¿debe avisar?)
    ("Comparación correcta (las tres cifras)", resp(), False),
    ("Variación redondeada a un entero (10 %)", resp(variacion_pct=10.0), False),
    ("cifra_anterior equivocada (la variación absoluta)", resp(cifra_anterior=2978000000.0), True),
    ("variacion_pct equivocada", resp(variacion_pct=30.0), True),
    ("Las dos equivocadas", resp(cifra_anterior=1.0, variacion_pct=99.0), True),
    ("Solo cifra_anterior, y bien", resp(variacion_pct=None), False),
    ("Ejercicio anterior fuera del corpus (FY2024 frente a FY2023)",
     resp(ejercicio=2024, cifra=29510000000.0, cifra_anterior=1.0, variacion_pct=5.0), True),
    ("Concepto inexistente: lo avisa revisar_cifra, no la comparación",
     resp(ticker="AMZN", concept_xbrl="GrossProfit", cifra=1e11), False),
    ("No es una comparación (campos vacíos)", resp(cifra_anterior=None, variacion_pct=None), False),
    ("fuente='texto': no se comprueba", resp(fuente="texto", cifra_anterior=1.0), False),
]

print("1) Reglas de la comparación")
fallos = 0
for nombre, respuesta, debe in CASOS:
    aviso = guardrails.revisar_comparacion(respuesta)
    bien = (aviso is not None) == debe
    fallos += not bien
    print(f"   {'OK ' if bien else 'MAL'} {nombre}")
assert fallos == 0, f"{fallos} caso(s) no se comportan como se esperaba"

print("\n   Lo que recibiría el modelo si se equivoca en la variación:")
print("  ", guardrails.revisar_comparacion(resp(variacion_pct=30.0)))

print("\n1b) La cifra es la variación y no el valor del ejercicio")
CASOS_VARIACION = [   # (caso, respuesta, texto que debe llevar el aviso o None si no debe nombrar variación)
    ("Variación absoluta en `cifra` (MSFT I+D, 2.978 M)", resp(cifra=2978000000.0), "variación absoluta"),
    ("Variación de un descenso, con signo negativo", resp(cifra=-2978000000.0), "variación absoluta"),
    ("Variación porcentual en `cifra` (10,1)", resp(cifra=10.1), "variación porcentual"),
    ("Valor equivocado que no es la variación", resp(cifra=5e9), None),
    ("Valor correcto: no avisa", resp(), "correcto"),
]
for nombre, respuesta, esperado in CASOS_VARIACION:
    aviso = guardrails.revisar_cifra(respuesta)
    if esperado == "correcto":
        bien = aviso is None
    elif esperado is None:
        bien = aviso is not None and "variación" not in aviso.split("no coincide")[0]
    else:
        bien = aviso is not None and esperado in aviso
    fallos += not bien
    print(f"   {'OK ' if bien else 'MAL'} {nombre}")
assert fallos == 0, f"{fallos} caso(s) no se comportan como se esperaba"

print("\n   Lo que recibiría el modelo si pone la variación absoluta en `cifra`:")
print("  ", guardrails.revisar_cifra(resp(cifra=2978000000.0)))

print("\n2) Compatibilidad: sin los campos nuevos, todo como antes")
for cifra in (32488000000.0, 2978000000.0):
    antes = guardrails.revisar_cifra(RespuestaFinanciera(
        respuesta="x", fuente="xbrl", ticker="MSFT", ejercicio=2025,
        concept_xbrl="ResearchAndDevelopmentExpense", cifra=cifra))
    ahora = guardrails.revisar_respuesta(RespuestaFinanciera(
        respuesta="x", fuente="xbrl", ticker="MSFT", ejercicio=2025,
        concept_xbrl="ResearchAndDevelopmentExpense", cifra=cifra))
    assert antes == ahora, "revisar_respuesta cambia el comportamiento sin campos nuevos"
print("   OK: revisar_respuesta coincide con revisar_cifra cuando no hay comparación")

print("\n3) Bucle completo con un modelo de mentira")


@tool
def relleno() -> str:
    """Herramienta de relleno: el agente real tiene herramientas."""
    return "ok"


class ModeloDeMentira(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def respuesta_guion(n, **cambios):
    argumentos = {**BASE, **cambios}
    return AIMessage(content="", tool_calls=[
        {"name": "RespuestaFinanciera", "args": argumentos, "id": f"r{n}"}])


guion = iter([respuesta_guion(1, variacion_pct=30.0),      # mal: la variación
              respuesta_guion(2)])                          # bien
agente = create_agent(model=ModeloDeMentira(messages=guion), tools=[relleno],
                      response_format=ToolStrategy(RespuestaFinanciera),
                      middleware=[guardrails.VerificadorDeCifras()])
r = agente.invoke({"messages": [{"role": "user", "content": "¿Cuánto creció el gasto en I+D de Microsoft?"}]})
final = r["structured_response"]
avisos = [m for m in r["messages"] if type(m).__name__ == "HumanMessage"][1:]
print(f"   variación final: {final.variacion_pct} % · avisos recibidos: {len(avisos)}")
assert final.variacion_pct == 10.1 and len(avisos) == 1, "el verificador no corrigió la variación"

print("\n" + "=" * 72)
print("HUMO GUARDRAILS OK: la comparación se verifica y lo demás no cambia.")
print("=" * 72)
