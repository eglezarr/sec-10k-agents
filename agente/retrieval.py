"""Búsqueda sobre el corpus — el punto de intercambio baseline/final.

`search_filings` (en herramientas.py) delega aquí. Así, la escalera de
mejoras de la sesión 2 (filtros -> híbrido RRF -> reescritura) se añade en
este módulo, se mide con recall@5, y solo se conecta a la herramienta la
configuración ganadora, sin tocar jamás el contrato de la tool.

Hoy contiene únicamente el escalón de partida: la búsqueda densa con los
filtros de metadatos que el propio modelo decide pasar. Es funcionalmente
idéntica a `miax_s1.buscar` (el baseline del día 10): se busca en TODO el
índice y se filtra después, recorriendo en orden de puntuación. Con 1.749
vectores eso es instantáneo y no cambia el resultado; con un corpus grande
habría que filtrar antes (conversación del día 17, no problema de hoy).
"""

from __future__ import annotations

from . import datos


def buscar_densa(
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    item: str | None = None,
    k: int = 5,
) -> list[dict]:
    """Los `k` fragmentos más parecidos a `query` que pasen los filtros.

    La puntuación es similitud coseno directa (vectores normalizados sobre
    `IndexFlatIP`), entre -1 y 1. Los filtros que sean None no se aplican.
    """
    indice, meta, _ = datos.cargar_indice()

    vector = datos.codificar([query])                 # prefijo BGE incluido
    puntuaciones, posiciones = indice.search(vector, indice.ntotal)

    resultados: list[dict] = []
    for puntuacion, posicion in zip(puntuaciones[0], posiciones[0]):
        fila = meta.iloc[int(posicion)]
        # Ojo: `fila.item` es el método Series.item, no la columna.
        # Con una columna llamada 'item', corchetes siempre.
        if ticker and fila["ticker"] != ticker:
            continue
        if fiscal_year and int(fila["fiscal_year"]) != int(fiscal_year):
            continue
        if item and fila["item"] != item:
            continue
        resultados.append(datos.fila_a_fragmento(fila, puntuacion))
        if len(resultados) >= k:
            break
    return resultados
