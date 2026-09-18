"""La interfaz del contrato del día 24.

La celda 4 del notebook de la S2 carga el agente de cada grupo con,
literalmente:

    from agente.interfaz import responder

Este módulo ES ese contrato. `responder` recibe la pregunta (y un
`thread_id` opcional, que `evaluar()` usará para aislar cada pregunta en su
propia conversación) y devuelve el dict de la invocación más `coste_usd` y
`latencia_s`, exactamente con la forma que el arnés de la S2 espera.

`evaluar(ruta_jsonl)` es la otra mitad del contrato: carga un golden en
JSONL, ejecuta `responder` sobre cada pregunta (un thread aislado por
pregunta), aplica los tres evaluadores y deja el detalle en
`resultados/eval_<etiqueta>.csv`. La columna recall se mide con la MISMA
configuración de búsqueda que usa la herramienta del agente
(`retrieval.buscar_agente`) sobre la consulta reescrita en inglés — el
régimen en el que el agente consulta de verdad.
"""

from __future__ import annotations

import functools

from pathlib import Path

from . import evaluadores, metricas, retrieval, trazas
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


def _buscar_como_el_agente(item: dict) -> list[dict]:
    """El retrieval que mide la columna recall: el MISMO que usa la tool
    (buscar_agente), sobre la consulta reescrita en inglés."""
    return retrieval.buscar_agente(
        retrieval.reescribir(item["pregunta"]),
        ticker=item.get("ticker"),
        fiscal_year=item.get("fiscal_year"),
        item=item.get("item_esperado"),
        k=metricas.K,
    )


def evaluar(ruta_jsonl: str, etiqueta: str = "eval"):
    """Evalúa el agente sobre un golden set en JSONL (contrato del día 24).

    Ejecuta las preguntas con `responder`, aplica los tres evaluadores,
    guarda el detalle por pregunta en resultados/eval_<etiqueta>.csv e
    imprime el resumen y el desglose por familia. Devuelve el DataFrame.
    """
    preguntas = evaluadores.cargar_golden(ruta_jsonl)
    raiz = Path(__file__).resolve().parents[1]
    df = evaluadores.evaluar(
        preguntas, responder, etiqueta=etiqueta,
        buscar_para_recall=_buscar_como_el_agente,
        ruta_salida=raiz / "resultados" / f"eval_{etiqueta}.csv",
        progreso=True,
    )
    resumen = evaluadores.resumir(df, etiqueta)
    print(f"[{etiqueta}] n={resumen['n']}  cita={resumen['cita_ok']:.2f}  "
          f"cifra={resumen['cifra_ok']:.2f}  tool={resumen['tool_ok']:.2f}  "
          f"recall@5={resumen['recall@5']:.2f}  "
          f"coste={resumen['coste_medio_¢']:.2f}¢  "
          f"latencia={resumen['latencia_media_s']:.1f}s  "
          f"tools/pregunta={resumen['tools_por_pregunta']:.1f}  "
          f"errores={resumen['errores']}")
    print(evaluadores.por_familia(df))
    return df
