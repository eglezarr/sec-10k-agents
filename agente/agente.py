"""El agente: esquema de respuesta, prompts, sistemas y constructor.

1. `RespuestaFinanciera` es el esquema del enunciado §7 (los ocho campos,
   literales) MÁS tres campos añadidos — el enunciado permite añadir campos,
   no quitarlos ni renombrarlos:
   - `concept_xbrl`: el concepto del que sale `cifra`, para que el
     verificador la compare contra ESE hecho y no contra cualquiera (en
     Microsoft FY2024 los pasivos y los ingresos están a un 0,6 %).
   - `cifra_anterior` y `variacion_pct`: las otras dos cifras de una
     comparativa, que el verificador también comprueba contra XBRL.

2. Tres prompts, cada uno sobre el anterior:
   - `SYSTEM` (v1, el del baseline): parte del prompt del profesor con dos
     matices nuestros — las magnitudes que solo existen en la prosa (capex,
     guidance) van por search_filings con cita, y las comparativas se
     consultan ejercicio a ejercicio.
   - `SYSTEM_V2`: la convención de `cifra` en las comparativas, las citas
     literales y el vocabulario del informe (sale del notebook 03).
   - `SYSTEM_V3`: las tres cifras de cada comparativa (sistema oficial).

3. `CONFIGURACIONES`: los cinco sistemas de la ablación (notebook 05), cada
   uno con una mejora más que el anterior. `CONFIG_POR_DEFECTO` es el
   sistema oficial, el que ejecutan `responder()` y `evaluar()` el día 24.

4. `crear_agente()` monta el `create_agent` de LangChain 1.x con las cuatro
   herramientas, la salida estructurada y, si la configuración lo pide, los
   guardrails de `guardrails.py` (límites, reintento y verificador).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# El modelo de referencia del curso (notebooks S1 y S2), vía OpenRouter.
# temperature=0 en todo lo evaluable: reduce la variabilidad entre
# ejecuciones, aunque no la elimina (el proveedor no es determinista; el
# notebook 05 lo mide), así que las diferencias pequeñas se leen como ruido.
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

    # ---- Campos AÑADIDOS solo para las COMPARACIONES entre dos ejercicios ----
    # En `cifra` va el valor del ejercicio más reciente; en una comparación el
    # agente también recupera el del ejercicio anterior y calcula la variación.
    # Estos dos campos permiten verificar contra XBRL las tres cifras y no solo
    # una. Fuera de las comparaciones se dejan vacíos.
    cifra_anterior: float | None = Field(
        default=None,
        description="SOLO en comparaciones entre dos ejercicios: valor XBRL "
                    "del ejercicio anterior, mismo concept_xbrl y en "
                    "unidades base")
    variacion_pct: float | None = Field(
        default=None,
        description="SOLO en comparaciones: variación porcentual de cifra "
                    "frente a cifra_anterior, con un decimal")


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


# Prompt v2: el v1 más tres reglas que salen del diagnóstico del baseline
# (notebook 03): la convención de `cifra` en las comparaciones, las citas
# literales y el vocabulario de las consultas. El v1 no se toca: es el baseline.
SYSTEM_V2 = SYSTEM + """
Reglas añadidas:
- COMPARACIONES entre dos ejercicios: una llamada a get_xbrl_fact por ejercicio
  y una búsqueda de texto (Item 7 del ejercicio más reciente) para la
  explicación. En `cifra` y `ejercicio` va el valor XBRL del ejercicio MÁS
  RECIENTE. La variación (absoluta o en %) y su explicación van SOLO en
  `respuesta`, nunca en `cifra`. Cita el fragmento que explica el cambio.
- CITAS: en `cita` copia LITERALMENTE una frase del fragmento recuperado, sin
  traducir ni parafrasear, y en `chunk_id` el identificador de ESE fragmento.
- CONSULTAS: usa el vocabulario del propio informe (por ejemplo "net sales",
  "revenue increased", "operating income", "useful lives") en lugar de
  traducir la pregunta palabra por palabra. Pasa ticker, ejercicio e item
  siempre que la pregunta los mencione.
"""

# Prompt v3: el v2 más la petición de las tres cifras en las comparaciones, que
# el verificador comprueba contra XBRL. Solo afecta a las comparaciones.
SYSTEM_V3 = SYSTEM_V2 + """- CIFRAS DE UNA COMPARACIÓN: además de `cifra`, rellena `cifra_anterior` con el
  valor XBRL del ejercicio anterior (mismo concepto, en unidades base) y
  `variacion_pct` con la variación porcentual ((cifra / cifra_anterior - 1) x 100,
  con un decimal). Se verifican las tres contra XBRL. Fuera de las
  comparaciones, déjalas vacías.
"""

# Los sistemas que se comparan. Cada uno añade UNA mejora al anterior, para
# poder atribuir cada efecto. `busqueda` es la que usa la herramienta search_filings.
CONFIGURACIONES = {
    "baseline":   {"prompt": SYSTEM,    "guardrails": False, "busqueda": "densa"},
    "prompt_v2":  {"prompt": SYSTEM_V2, "guardrails": False, "busqueda": "densa"},
    "guardrails": {"prompt": SYSTEM_V2, "guardrails": True,  "busqueda": "densa"},
    "final":      {"prompt": SYSTEM_V2, "guardrails": True,  "busqueda": "hibrida"},
    # El final más las cifras completas de las comparaciones (prompt v3): el
    # sistema OFICIAL. En su tirada del notebook 05 rellenó cifra_anterior y
    # variacion_pct en 12 de las 13 comparativas (propio + oficial), todas
    # correctas contra XBRL y sin un solo aviso del verificador; la que falta
    # es pr-c11, que responde con una cifra del texto.
    "cifras_comparadas": {"prompt": SYSTEM_V3, "guardrails": True, "busqueda": "hibrida"},
}
CONFIG_POR_DEFECTO = "cifras_comparadas"     # el sistema oficial: el que ejecuta responder() el día 24


def crear_agente(modelo: str = MODELO, middleware: list | None = None,
                 config: str | None = None):
    """El agente montado: modelo + 4 herramientas + salida estructurada.

    Devuelve el agente de `create_agent` con checkpointer en memoria (la
    memoria entre turnos que exige `thread_id`). Sin argumentos es el
    baseline: prompt v1 y sin middleware. `config` elige uno de los sistemas
    de CONFIGURACIONES (baseline, prompt_v2, guardrails o final).

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

    system = SYSTEM
    if config is not None:       # una de las CONFIGURACIONES fija prompt y guardrails
        from .guardrails import crear_guardrails
        system = CONFIGURACIONES[config]["prompt"]
        middleware = crear_guardrails() if CONFIGURACIONES[config]["guardrails"] else []

    return create_agent(
        model=modelo,
        tools=HERRAMIENTAS,
        system_prompt=system,
        response_format=RespuestaFinanciera,
        middleware=middleware or [],
        checkpointer=InMemorySaver(),
    )
