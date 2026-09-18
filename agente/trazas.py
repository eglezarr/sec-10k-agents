"""Trazas y medidas: coste, tokens, latencia y trayectoria.

Adaptado de `miax_s2` (reutilización sancionada). Coste y latencia son
columnas de la tabla del informe, no una nota al pie; y sin trayectoria no
se puede escribir el evaluador `uso_la_tool_correcta` — no se distingue una
respuesta correcta de una correcta por casualidad.
"""

from __future__ import annotations

import time

# USD por millón de tokens (entrada, salida). Consultado el 2/09/2026 en
# https://openrouter.ai/api/v1/models — REVISAR LA VÍSPERA de cada tanda de
# medición: OpenRouter cambia precios sin avisar, y un precio viejo
# convierte la columna de coste del informe en ficción.
PRECIOS_OPENROUTER = {
    "google/gemini-3.5-flash-lite":  (0.30,  2.50),
    "google/gemini-3.8-flash":       (0.75,  3.75),
    "anthropic/claude-opus-5":       (5.00, 25.00),
    "anthropic/claude-fable-5.1":    (10.00, 50.00),
}


def _mensajes(resultado) -> list:
    return resultado["messages"] if isinstance(resultado, dict) else resultado


def tokens_de(resultado) -> tuple[int, int]:
    """`(entrada, salida)` sumando el uso que reporta cada mensaje.

    La entrada crece con cada vuelta del bucle (el historial se reenvía
    entero), así que aquí está el motivo de que una pregunta con cuatro
    herramientas cueste bastante más que cuatro preguntas de una.
    """
    entrada = salida = 0
    for mensaje in _mensajes(resultado):
        uso = getattr(mensaje, "usage_metadata", None) or {}
        entrada += uso.get("input_tokens", 0) or 0
        salida += uso.get("output_tokens", 0) or 0
    return entrada, salida


def coste_de(resultado, modelo: str) -> float:
    """Coste en USD de una invocación, según `PRECIOS_OPENROUTER`."""
    nombre = modelo.split(":", 1)[-1]
    if nombre not in PRECIOS_OPENROUTER:
        return 0.0
    precio_entrada, precio_salida = PRECIOS_OPENROUTER[nombre]
    entrada, salida = tokens_de(resultado)
    return (entrada * precio_entrada + salida * precio_salida) / 1e6


def cronometrar(funcion, *args, **kwargs) -> tuple:
    """`(resultado, segundos)` de una llamada."""
    comienzo = time.perf_counter()
    resultado = funcion(*args, **kwargs)
    return resultado, time.perf_counter() - comienzo


def herramientas_usadas(resultado) -> list[str]:
    """Los nombres de herramienta que aparecen en la trayectoria, en orden.

    Es la primitiva del evaluador de trayectoria: una pregunta numérica en
    cuya lista no aparezca 'get_xbrl_fact' es un fallo, acierte o no.
    """
    return [llamada["name"]
            for mensaje in _mensajes(resultado)
            for llamada in (getattr(mensaje, "tool_calls", None) or [])]


def pretty_trace(resultado, max_chars: int = 200) -> None:
    """Imprime la trayectoria: herramientas, argumentos y resultados.

    Una respuesta no se puede juzgar sin ver el camino: esto es lo que se
    mira en cada depuración y lo que se enseña en la defensa.
    """
    paso = 0
    for mensaje in _mensajes(resultado):
        for llamada in getattr(mensaje, "tool_calls", None) or []:
            paso += 1
            args = ", ".join(f"{k}={v!r}" for k, v in llamada["args"].items())
            print(f"  {paso}. {llamada['name']}({args})")
        if type(mensaje).__name__ == "ToolMessage":
            contenido = str(mensaje.content).replace("\n", " ")
            print(f"       -> {contenido[:max_chars]}"
                  f"{'…' if len(contenido) > max_chars else ''}")

    if isinstance(resultado, dict) and resultado.get("structured_response"):
        r = resultado["structured_response"]
        print(f"\n  respuesta : {r.respuesta}")
        print(f"  cifra     : {r.cifra} {r.unidad or ''}"
              f"   concepto: {r.concept_xbrl}")
        print(f"  fuente    : {r.fuente}   ticker: {r.ticker}"
              f"   ejercicio: {r.ejercicio}")
        print(f"  cita      : {(r.cita or '')[:120]}")
        print(f"  chunk_id  : {r.chunk_id}")
