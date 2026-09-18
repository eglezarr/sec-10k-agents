"""Búsqueda sobre el corpus — el punto de intercambio baseline/final.

`search_filings` (herramientas.py) delega aquí. La escalera de mejoras de
la sesión 2 vive en este módulo, se mide con recall@5 en
`notebooks/01_retrieval.ipynb`, y solo la configuración ganadora se conecta
a la herramienta — sin tocar jamás el contrato de la tool, y NUNCA antes de
congelar el baseline.

Los cuatro escalones, cada uno un arreglo con su argumento:

  A. `buscar_densa` sin filtros — el punto de partida del día 10.
  B. `buscar_densa` con filtros de metadatos — busca donde hay que buscar.
     Los filtros se aplican DESPUÉS de la búsqueda, recorriendo el orden
     del índice: con 1.749 vectores es instantáneo e idéntico en resultado
     a filtrar antes; con un corpus grande habría que pre-filtrar.
  C. `buscar_hibrida` — denso + BM25 fusionados con Reciprocal Rank Fusion.
     RRF y no suma de puntuaciones: un coseno en [-1, 1] y un score BM25
     sin escala fija no se pueden sumar; las POSICIONES sí se pueden
     combinar (celda 11 de la S2).
  D. `reescribir` — la consulta en español se reescribe en inglés con
     vocabulario de 10-K antes de buscar. Ataca el cuello real del corpus
     (embeddings monolingües en inglés). Es pieza del ARNÉS DE MEDICIÓN:
     el agente ya escribe sus consultas en inglés por system prompt, así
     que la reescritura no va dentro de la tool.
"""

from __future__ import annotations

import functools
import re

from . import datos

RRF_KK = 60          # constante de la fórmula RRF, el valor clásico y el de la S2
_AUSENTE = 10 ** 6   # posición asignada a un fragmento que no está en una lista


# ---------------------------------------------------------------------------
# A y B · Búsqueda densa (con o sin filtros)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# C · Híbrida: denso + BM25 con Reciprocal Rank Fusion
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenizar(texto: str) -> list[str]:
    """Minúsculas y alfanumérico: suficiente para BM25 sobre este corpus."""
    return _TOKEN.findall(texto.lower())


@functools.lru_cache(maxsize=1)
def _bm25():
    """El índice léxico, construido una vez sobre los mismos 1.749 textos
    (y en el mismo orden) que el índice denso, para poder fusionar por
    posición."""
    from rank_bm25 import BM25Okapi

    _, meta, _ = datos.cargar_indice()
    return BM25Okapi([_tokenizar(t) for t in meta["texto"]])


def _posiciones_permitidas(meta, ticker, fiscal_year, item) -> set[int]:
    mascara = meta.index == meta.index                # todo True
    if ticker:
        mascara &= meta["ticker"] == ticker
    if fiscal_year:
        mascara &= meta["fiscal_year"].astype(int) == int(fiscal_year)
    if item:
        mascara &= meta["item"] == item
    return set(int(i) for i in meta.index[mascara])


def buscar_hibrida(
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    item: str | None = None,
    k: int = 5,
    kk: int = RRF_KK,
) -> list[dict]:
    """Fusión RRF del ranking denso y el ranking BM25, ambos ya filtrados.

    RRF(d) = 1/(kk + pos_densa(d)) + 1/(kk + pos_bm25(d)), con posición
    1-indexada dentro de cada lista FILTRADA y `_AUSENTE` si el fragmento
    no aparece en una de ellas. El denso aporta semántica (parafraseo);
    BM25 aporta literalidad (tickers, nombres de producto, términos
    exactos). La puntuación devuelta es el score RRF (escala ~1/kk), no
    una similitud.
    """
    indice, meta, _ = datos.cargar_indice()
    permitidas = _posiciones_permitidas(meta, ticker, fiscal_year, item)
    if not permitidas:
        return []

    # Ranking denso, restringido a las posiciones permitidas.
    vector = datos.codificar([query])
    _, posiciones = indice.search(vector, indice.ntotal)
    orden_denso = [int(p) for p in posiciones[0] if int(p) in permitidas]

    # Ranking BM25, restringido al mismo subconjunto.
    puntuaciones_bm25 = _bm25().get_scores(_tokenizar(query))
    orden_bm25 = sorted(permitidas,
                        key=lambda p: -float(puntuaciones_bm25[p]))

    pos_densa = {p: i + 1 for i, p in enumerate(orden_denso)}
    pos_bm25 = {p: i + 1 for i, p in enumerate(orden_bm25)}

    def rrf(p: int) -> float:
        return (1.0 / (kk + pos_densa.get(p, _AUSENTE))
                + 1.0 / (kk + pos_bm25.get(p, _AUSENTE)))

    candidatas = set(orden_denso) | set(orden_bm25)
    mejores = sorted(candidatas, key=lambda p: -rrf(p))[:k]
    return [datos.fila_a_fragmento(meta.iloc[p], rrf(p)) for p in mejores]


# ---------------------------------------------------------------------------
# D · Reescritura de consulta (pieza del arnés de medición)
# ---------------------------------------------------------------------------
MODELO_REESCRITURA = "openrouter:google/gemini-3.5-flash-lite"

_PROMPT_REESCRITURA = (
    "Rewrite the following question as a search query IN ENGLISH for "
    "retrieving passages from SEC 10-K filings. Use the vocabulary a 10-K "
    "would use. Return ONLY the query, nothing else.\n\nQuestion: {q}"
)


@functools.lru_cache(maxsize=512)
def reescribir(pregunta: str, modelo: str = MODELO_REESCRITURA) -> str:
    """La pregunta, reescrita como consulta de búsqueda en inglés.

    Una llamada barata (modelo lite, temperature=0) por consulta DISTINTA:
    la caché evita repagar la misma pregunta dentro del proceso. Requiere
    OPENROUTER_API_KEY. Si la llamada falla, se devuelve la pregunta tal
    cual — la medición sigue, y el escalón D simplemente no mejora.
    """
    from langchain.chat_models import init_chat_model

    try:
        modelo_chat = init_chat_model(modelo, temperature=0)
        salida = modelo_chat.invoke(_PROMPT_REESCRITURA.format(q=pregunta))
        reescrita = str(salida.content).strip().strip('"').strip()
        return reescrita or pregunta
    except Exception:
        return pregunta
