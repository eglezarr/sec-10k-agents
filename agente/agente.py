"""El agente: esquema de respuesta, system prompt y constructor.

Tres piezas, y las tres son contrato o casi:

1. `RespuestaFinanciera` es el esquema del enunciado §7, literal, MÁS un
   campo añadido (`concept_xbrl`) — el enunciado permite añadir campos,
   no quitarlos ni renombrarlos. La justificación del añadido está en el
   propio campo.

2. `SYSTEM` parte del prompt del profesor (sesiones 1 y 2) con dos matices
   nuestros, los dos respaldados por el golden set oficial:
   - Magnitudes que SOLO existen en la prosa (capex, porcentajes de
     segmento, guidance) van por search_filings con cita — el corpus no
     tiene concepto XBRL de capex y of-006/of-017/of-018 las preguntan.
   - Las comparativas se descomponen: una consulta POR ejercicio. Es el
     fallo n.º 3 del diagnóstico de la S2 ("no supo comparar"), atacado
     desde el prompt antes de llegar al middleware.

3. `crear_agente()` monta el `create_agent` de LangChain 1.x igual que el
   `baseline()` de `miax_s2`: mismas piezas, nuestras herramientas. El
   parámetro `middleware` queda preparado para la entrega de guardrails
   (límites + verificación de cifras); el BASELINE se construye sin
   ninguno, que es exactamente lo que la celda 29 de la S2 compara contra
   el sistema final.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# El modelo de referencia del curso (notebooks S1 y S2), vía OpenRouter.
# temperature=0 en todo lo evaluable: con temperatura, dos ejecuciones de
# la misma pregunta dan métricas distintas y no se sabe si mejoraste el
# sistema o tuviste suerte.
MODELO = "openrouter:google/gemini-3.8-flash"


class RespuestaFinanciera(BaseModel):
    """Respuesta trazable a una pregunta sobre informes 10-K."""

    respuesta: str = Field(
        description="Respuesta en prosa, breve y directa")
    cifra: float | None = Field(
        default=None,
        description="Valor numérico, si la pregunta pide uno")
    unidad: str | None = Field(
        default=None, description="USD, shares, porcentaje…")
    ticker: str | None = None
    ejercicio: int | None = None
    fuente: Literal["xbrl", "texto", "ambas", "ninguna"] = Field(
        description="De dónde sale el dato. 'ninguna' si no está en el "
                    "corpus")
    cita: str | None = Field(
        default=None,
        description="Texto literal del informe que respalda la respuesta")
    chunk_id: str | None = Field(
        default=None,
        description="Identificador del fragmento citado, para verificar")

    # ---- Campo AÑADIDO (permitido por el enunciado) -----------------
    # Ancla la verificación de la cifra al concepto exacto consultado.
    # Sin él, el guardrail solo puede comprobar "la cifra cuadra con
    # ALGÚN hecho del emisor", y en este corpus eso colisiona de verdad:
    # MSFT FY2024 reporta Liabilities = 243.686M y revenue = 245.122M,
    # a un 0,59 % — dentro de la tolerancia del 1 %. Con el concepto
    # declarado, la comprobación es contra EL hecho, no contra cualquiera.
    concept_xbrl: str | None = Field(
        default=None,
        description="Concepto US-GAAP exacto consultado en get_xbrl_fact "
                    "del que sale 'cifra', si fuente es 'xbrl' o 'ambas'")


SYSTEM = """Eres un analista financiero que responde preguntas sobre informes
10-K usando ÚNICAMENTE las herramientas disponibles.

Reglas:
- Para cualquier cifra reportada en XBRL, usa get_xbrl_fact. Nunca leas del
  texto un número que exista en XBRL. Rellena concept_xbrl con el concepto
  exacto que consultaste.
- En el campo cifra escribe SIEMPRE el valor absoluto en unidades
  base (402836000000, nunca 402836 "millones"): el verificador
  compara contra XBRL, que guarda valores absolutos.
- Si una magnitud numérica NO existe en XBRL (capex, porcentajes de
  segmento, previsiones/guidance), búscala con search_filings, cita el
  chunk_id y marca fuente 'texto'.
- Para riesgos, estrategia o comentarios de la dirección, usa
  search_filings.
- En preguntas que comparan dos ejercicios, consulta cada ejercicio por
  separado (una llamada por ejercicio) y calcula tú la variación.
- Si no sabes si una compañía o un ejercicio están en el corpus, empieza
  por list_available.
- El corpus está en inglés: escribe las consultas de búsqueda en inglés.
- Cita el chunk_id del fragmento en el que te apoyes.
- Si el dato no está en el corpus, dilo: fuente 'ninguna' y sin cifra. No
  lo estimes nunca.
"""


def crear_agente(modelo: str = MODELO, middleware: list | None = None):
    """El agente montado: modelo + 4 herramientas + salida estructurada.

    Devuelve el agente de `create_agent` con checkpointer en memoria (la
    memoria entre turnos que exige `thread_id`). Baseline = sin middleware;
    los guardrails llegan como lista en la entrega correspondiente.

    Nota de compatibilidad: si algún modelo alternativo no soportara salida
    estructurada nativa, la línea de `response_format` se envuelve así
    (apunte de la celda 26 de la S1):
        from langchain.agents.structured_output import ToolStrategy
        response_format=ToolStrategy(schema=RespuestaFinanciera)
    Con gemini-3.8-flash vía OpenRouter no hace falta.
    """
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver

    from .herramientas import HERRAMIENTAS

    return create_agent(
        model=modelo,
        tools=HERRAMIENTAS,
        system_prompt=SYSTEM,
        response_format=RespuestaFinanciera,
        middleware=middleware or [],
        checkpointer=InMemorySaver(),
    )
