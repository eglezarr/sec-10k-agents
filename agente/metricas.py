"""Métricas de retrieval: la regla de medir de la escalera.

Tres primitivas, con la semántica exacta de la sesión 2:

- `acierta`: el ancla (una frase LITERAL del informe, ≤40 palabras) aparece
  en alguno de los fragmentos devueltos. Se compara texto normalizado
  (espacios colapsados, minúsculas), así que sobrevive a cambios de
  troceado — por eso el golden ancla a frases y no a chunk_ids.
- `recall_en_k`: fracción de preguntas ancladas cuyo ancla entra en el
  top-k. Con K=5 fijo: es la métrica que `resumir()` rotula "recall@5" y
  la única que exige el enunciado.
- `posicion_del_ancla`: para las que fallan, en qué puesto del ranking
  completo estaba el ancla. Un ancla en el puesto 7 y otra en el 1.400
  fallan igual en recall@5 y no son el mismo problema: la primera se
  arregla reordenando, la segunda no está ni cerca.
"""

from __future__ import annotations

from . import datos

K = 5   # el k del recall@k del proyecto (S2, celda 9 y resumir())


def acierta(fragmentos: list[dict], ancla: str) -> bool:
    """¿Alguno de los fragmentos contiene el ancla, literal y normalizada?"""
    objetivo = datos.normalizar(ancla)
    return any(objetivo in datos.normalizar(f["texto"]) for f in fragmentos)


def recall_en_k(items: list[dict], buscar_de_item) -> tuple[float, dict]:
    """Recall@k sobre los items CON ancla, con detalle por pregunta.

    `buscar_de_item(item) -> list[dict]` encapsula la configuración que se
    mide (qué consulta, qué filtros, qué buscador): así la misma métrica
    sirve para los cuatro escalones sin duplicar código.

    Devuelve `(recall, detalle)` con `detalle[id] = True/False`. Los items
    sin `ancla_texto` (numéricas puras) se ignoran: su calidad la miden
    otros evaluadores, no este.
    """
    detalle: dict[str, bool] = {}
    for item in items:
        ancla = item.get("ancla_texto")
        if not ancla:
            continue
        detalle[item["id"]] = acierta(buscar_de_item(item), ancla)
    if not detalle:
        return 0.0, detalle
    return sum(detalle.values()) / len(detalle), detalle


def posicion_del_ancla(fragmentos_ordenados: list[dict],
                       ancla: str) -> int | None:
    """Puesto (1-indexado) del primer fragmento que contiene el ancla,
    dentro de un ranking completo; None si no aparece en ninguno."""
    objetivo = datos.normalizar(ancla)
    for puesto, fragmento in enumerate(fragmentos_ordenados, 1):
        if objetivo in datos.normalizar(fragmento["texto"]):
            return puesto
    return None
