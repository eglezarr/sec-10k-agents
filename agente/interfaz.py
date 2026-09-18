"""La interfaz del contrato del día 24.

La celda 4 del notebook de la S2 carga el agente de cada grupo con,
literalmente:

    from agente.interfaz import responder

Este módulo ES ese contrato. `responder` recibe la pregunta (y un
`thread_id` opcional, que `evaluar()` usará para aislar cada pregunta en su
propia conversación) y devuelve el dict de la invocación más `coste_usd` y
`latencia_s`, exactamente con la forma que el arnés de la S2 espera.

`evaluar(ruta_jsonl)` se expone aquí mismo cuando lleguen los tres
evaluadores; hasta entonces no hay stub — un import que existe a medias es
peor que uno que no existe.
"""

from __future__ import annotations

import functools

from . import trazas
from .agente import MODELO, crear_agente


@functools.lru_cache(maxsize=1)
def _instancia():
    """Un único agente por proceso.

    Construirlo por llamada tiraría el checkpointer (y con él la memoria
    entre turnos del mismo thread_id) y pagaría el montaje cada vez. El
    aislamiento entre preguntas NO se consigue reconstruyendo el agente,
    sino pasando thread_id distintos: mismo agente, conversaciones
    separadas.
    """
    return crear_agente()


def responder(pregunta: str, thread_id: str | None = None) -> dict:
    """Ejecuta el agente sobre una pregunta y devuelve el resultado medido.

    Devuelve el dict de `agente.invoke` (claves 'messages' y
    'structured_response', una `RespuestaFinanciera` validada) más:
      - 'coste_usd': coste de la invocación a precios de OpenRouter.
      - 'latencia_s': segundos de reloj de la invocación completa.

    `thread_id` identifica la conversación: repetirlo encadena turnos con
    memoria; omitirlo usa el hilo 'interactivo'.
    """
    resultado, segundos = trazas.cronometrar(
        _instancia().invoke,
        {"messages": [{"role": "user", "content": pregunta}]},
        config={"configurable": {"thread_id": thread_id or "interactivo"}},
    )
    return {**resultado,
            "coste_usd": trazas.coste_de(resultado, MODELO),
            "latencia_s": segundos}
