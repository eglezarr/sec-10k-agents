"""Guardrails del agente: límite de llamadas y verificador de cifras.

Cuatro piezas, tres de ellas ya hechas por LangChain:

1. Límites de llamadas por invocación. `ToolCallLimitMiddleware` corta el
   exceso de llamadas a herramienta y `ModelCallLimitMiddleware` el de
   llamadas al modelo: el segundo cubre a un modelo que da vueltas sin llamar
   a ninguna herramienta, que el primero no ve. Van los primeros en la lista.

2. Reintento con espera (`ModelRetryMiddleware`). Los límites de peticiones
   del proveedor (429) y sus errores transitorios no deberían costar una
   pregunta, y menos la de un hold-out.

3. `VerificadorDeCifras`. Cuando el modelo da su respuesta final, se
   comprueba su `cifra` contra los datos XBRL y, si es una comparación entre
   dos ejercicios, también `cifra_anterior` y `variacion_pct`. Si no cuadra, el desajuste
   se le devuelve al modelo como un mensaje para que lo corrija. También
   exige la salida estructurada: si el modelo termina en texto suelto, se le
   pide que use el esquema. Solo se insiste `MAX_CORRECCIONES` veces: un
   guardrail no puede colgar al agente.

Se usa así:

    agente = crear_agente(middleware=crear_guardrails())
"""

from __future__ import annotations

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
    hook_config,
)
from langchain_core.messages import AIMessage, HumanMessage

from . import datos, evaluadores

LIMITE_LLAMADAS = 12      # a herramientas, por invocación; el baseline hace entre 2 y 11
LIMITE_MODELO = 16        # al modelo: las de herramientas + 1, más hasta 2 avisos
MAX_CORRECCIONES = 2      # veces que se le devuelve un desajuste al modelo
MARCA = "VERIFICACIÓN:"

# Más estricta que el 1 % del evaluador. El agente recibe el valor exacto de
# get_xbrl_fact, así que copiarlo bien es fácil, y con un 0,1 % se distinguen
# dos hechos vecinos (el pasivo y el revenue de Microsoft FY2024 están a un 0,59 %).
TOLERANCIA = 0.001

# Margen en puntos porcentuales para la variación: el agente la redondea a un
# decimal, o incluso a un entero.
TOLERANCIA_PP = 0.15


def valor_xbrl(ticker: str, ejercicio: int, concepto: str) -> float | None:
    """El valor que la compañía reportó en XBRL, o None si no lo reportó."""
    xbrl = datos.cargar_xbrl()
    fila = xbrl[(xbrl.ticker == ticker)
                & (xbrl.fiscal_year == int(ejercicio))
                & (xbrl.concept == concepto)]
    return float(fila.iloc[0].value) if len(fila) else None


def revisar_cifra(r) -> str | None:
    """Aviso para el modelo si la cifra de `r` no cuadra con XBRL.

    Devuelve None cuando no hay nada que decir. `r` es una
    `RespuestaFinanciera`.
    """
    if r.cifra is None:
        return None            # sin cifra no hay nada que comprobar

    if r.fuente == "ninguna":
        return ("Has marcado fuente='ninguna' pero das una cifra. Si el dato "
                "no está en el corpus, deja `cifra` vacía y no lo estimes.")

    if r.fuente == "texto":
        return None            # sale del texto del informe: no hay hecho XBRL

    # fuente 'xbrl' o 'ambas': la cifra tiene que poder comprobarse
    if not (r.ticker and r.ejercicio and r.concept_xbrl):
        return ("Rellena `ticker`, `ejercicio` y `concept_xbrl` para poder "
                "verificar la cifra contra XBRL.")

    esperado = valor_xbrl(r.ticker, r.ejercicio, r.concept_xbrl)
    if esperado is None:
        return (f"{r.ticker} no reporta '{r.concept_xbrl}' en FY{r.ejercicio}. "
                f"Consulta get_xbrl_fact y usa un concepto que exista; si el dato no "
                f"está en el corpus, responde con fuente='ninguna' y sin cifra.")

    if evaluadores.cuadra(r.cifra, esperado, TOLERANCIA):
        return None

    variacion = _es_variacion(r, esperado)
    if variacion:
        return (f"Tu cifra {r.cifra:,.2f} es {variacion} de {r.concept_xbrl} de {r.ticker} "
                f"entre FY{r.ejercicio - 1} y FY{r.ejercicio}, no el valor del ejercicio. En "
                f"`cifra` va el valor XBRL de FY{r.ejercicio}, {esperado:,.2f}; la variación "
                f"va en `respuesta`.")

    pista = ""
    if any(evaluadores.cuadra(r.cifra * k, esperado, TOLERANCIA)
           for k in (1e3, 1e6, 1e9)):
        pista = (" Parece estar en miles o millones: escribe el valor "
                 "absoluto en unidades base.")
    return (f"Tu cifra {r.cifra:,.2f} no coincide con XBRL: {r.concept_xbrl} de "
            f"{r.ticker} en FY{r.ejercicio} es {esperado:,.2f}.{pista} En `cifra` "
            f"va el valor XBRL del ejercicio pedido; si comparas dos ejercicios "
            f"o das una variación, ponla en `respuesta`.")


def _es_variacion(r, actual: float) -> str | None:
    """Si la cifra de `r` es la variación entre ejercicios y no el valor del ejercicio.

    Es el error que más se repite en las comparaciones: el agente calcula la
    variación (absoluta o en %) y la escribe en `cifra`. Devuelve una descripción
    para el aviso, o None si la cifra no se parece a ninguna de las dos.
    """
    anterior = valor_xbrl(r.ticker, r.ejercicio - 1, r.concept_xbrl)
    if anterior is None:
        return None
    if evaluadores.cuadra(abs(r.cifra), abs(actual - anterior), TOLERANCIA):
        return "la variación absoluta"
    if anterior != 0 and abs(abs(r.cifra) - abs((actual / anterior - 1) * 100)) <= TOLERANCIA_PP:
        return "la variación porcentual"
    return None


def revisar_comparacion(r) -> str | None:
    """Aviso si `cifra_anterior` o `variacion_pct` no cuadran con XBRL.

    Solo actúa en las comparaciones: si el agente no rellena esos campos, no
    hace nada. La variación se contrasta con la que sale de los valores XBRL,
    no con los números que el propio agente haya escrito.
    """
    if r.cifra_anterior is None and r.variacion_pct is None:
        return None            # no es una comparación, o no las rellenó
    if r.fuente not in ("xbrl", "ambas") or not (r.ticker and r.ejercicio and r.concept_xbrl):
        return None            # revisar_cifra ya avisa de lo que falte

    actual = valor_xbrl(r.ticker, r.ejercicio, r.concept_xbrl)
    if actual is None:
        return None            # revisar_cifra ya avisa de que el concepto no existe
    anterior = valor_xbrl(r.ticker, r.ejercicio - 1, r.concept_xbrl)
    if anterior is None:
        return (f"{r.ticker} no reporta '{r.concept_xbrl}' en FY{r.ejercicio - 1}, así que "
                f"no se puede comparar. Deja `cifra_anterior` y `variacion_pct` vacíos y "
                f"explícalo en `respuesta`.")

    avisos = []
    if r.cifra_anterior is not None and not evaluadores.cuadra(r.cifra_anterior, anterior, TOLERANCIA):
        avisos.append(f"Tu cifra_anterior {r.cifra_anterior:,.2f} no coincide con XBRL: "
                      f"{r.concept_xbrl} de {r.ticker} en FY{r.ejercicio - 1} es {anterior:,.2f}.")
    if r.variacion_pct is not None and anterior != 0:
        esperada = (actual / anterior - 1) * 100
        if abs(r.variacion_pct - esperada) > TOLERANCIA_PP:
            avisos.append(f"Tu variacion_pct {r.variacion_pct:+.1f} % no coincide con la que sale de "
                          f"XBRL: de {anterior:,.0f} a {actual:,.0f} es {esperada:+.1f} %.")
    return " ".join(avisos) or None


def revisar_respuesta(r) -> str | None:
    """Todos los avisos de una respuesta: la cifra y, en comparaciones, las otras dos."""
    avisos = [a for a in (revisar_cifra(r), revisar_comparacion(r)) if a]
    return " ".join(avisos) or None


class VerificadorDeCifras(AgentMiddleware):
    """Comprueba la cifra y exige que la respuesta venga estructurada."""

    @hook_config(can_jump_to=["model"])
    def after_model(self, state, runtime):
        respuesta = state.get("structured_response")
        ultimo = state["messages"][-1]

        if respuesta is None:
            # Sin respuesta estructurada. Si el modelo aún pide herramientas no pasa
            # nada; si ha terminado en texto suelto o vacío, se le pide el esquema.
            if isinstance(ultimo, AIMessage) and not ultimo.tool_calls:
                aviso = ("No has devuelto la respuesta estructurada. "
                         "Responde de nuevo usando el esquema completo.")
            else:
                return None
        else:
            aviso = revisar_respuesta(respuesta)
            if aviso is None:
                return None        # la cifra cuadra
            aviso += " Vuelve a responder usando el esquema completo."

        avisos_previos = sum(1 for m in state["messages"]
                             if isinstance(m, HumanMessage)
                             and str(m.content).startswith(MARCA))
        if avisos_previos >= MAX_CORRECCIONES:
            return None            # ya se avisó suficiente: se deja pasar

        # Devolvemos el aviso al modelo y volvemos a él
        return {"jump_to": "model",
                "messages": [HumanMessage(f"{MARCA} {aviso}")]}


def crear_guardrails() -> list:
    """La lista que se pasa a `crear_agente(middleware=...)`.

    El orden importa: los límites van primero y el verificador el último,
    porque es el que puede provocar vueltas extra.
    """
    return [ToolCallLimitMiddleware(run_limit=LIMITE_LLAMADAS,
                                    exit_behavior="continue"),
            ModelCallLimitMiddleware(run_limit=LIMITE_MODELO,
                                     exit_behavior="end"),
            ModelRetryMiddleware(max_retries=4, initial_delay=5.0,
                                 backoff_factor=2.0, max_delay=40.0,
                                 on_failure="error"),
            VerificadorDeCifras()]
