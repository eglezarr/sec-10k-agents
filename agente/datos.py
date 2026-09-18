"""Acceso a los datos del corpus: localización, verificación y carga.

Reúne lo que en clase estaba repartido entre la celda de setup y
`miax_s1`/`miax_s2` (reutilización sancionada por el profesor): preparar el
corpus desde los dos ZIP, verificando hashes, y cargar secciones, chunks,
XBRL e índice FAISS una sola vez por proceso.

Decisión de diseño — auto-preparación: `dir_corpus()` extrae y verifica el
corpus él solo si encuentra los ZIP pero no la carpeta `corpus/`. El día 24
`evaluar("holdout.jsonl")` corre sobre un clon limpio sin editar nada, y
cada paso manual entre `git clone` y esa llamada es un modo de fallo en
directo. Con esto, el único requisito es que los ZIP estén en `dataset/`
(van versionados en el repo).
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes del corpus. Los hashes son los de SHA256SUMS.txt del profesor:
# si un ZIP no cuadra, está corrupto o es de otra edición, y el índice y los
# metadatos podrían quedar desalineados SIN dar error (contrato de datos §4).
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[1]          # raíz del repositorio

PAQUETES = [
    ("corpus_miax_2026.zip",
     "4233c37fc9e9d12091af7a146063ad70903a3fe51404a485854f4021c63daee4"),
    ("indice_faiss.zip",
     "6b5610ad8ac6ea50364445d39bb464d993cbd87048fb07c4fe16657d7ac11655"),
]

# Dónde pueden estar los ZIP, en orden de búsqueda. `dataset/` es el sitio
# canónico del repo; el resto mantiene compatibilidad con Colab/Drive para
# los compañeros que trabajen allí.
CANDIDATOS_ZIP = [
    RAIZ / "dataset",
    RAIZ,
    Path("."),
    Path("/content"),
    Path("/content/dataset"),
    Path("/content/drive/MyDrive/MIAX_2026"),
    Path("/content/drive/Shareddrives/MIAX_2026"),
]

DESTINO = RAIZ / "corpus"                            # carpeta extraída
CANDIDATOS_CORPUS = [DESTINO, Path("corpus"), Path("/content/corpus")]

# Modelo de embeddings del índice entregado. Tiene que coincidir con
# `corpus/indice/MANIFEST.md`. El prefijo va SOLO en la consulta, nunca en
# los fragmentos: omitirlo no da error, solo recupera peor (el fallo
# silencioso del que va media sesión 2).
MODELO_EMBEDDINGS = "BAAI/bge-small-en-v1.5"
PREFIJO_CONSULTA_BGE = (
    "Represent this sentence for searching relevant passages: "
)


class CorpusNoEncontrado(RuntimeError):
    """El corpus no está disponible. Se lanza con instrucciones, no a secas."""


# ---------------------------------------------------------------------------
# Preparación: ZIP -> corpus/ verificado
# ---------------------------------------------------------------------------
def _sha256(ruta: Path) -> str:
    d = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            d.update(bloque)
    return d.hexdigest()


def _localizar_zip(nombre: str) -> Path | None:
    for base in CANDIDATOS_ZIP:
        ruta = base / nombre
        if ruta.is_file():
            return ruta
    return None


def preparar_corpus(verbose: bool = True) -> Path:
    """Extrae y verifica los dos ZIP en `corpus/`. Idempotente.

    Verifica tres cosas, en este orden: el hash de cada ZIP, y que el hash
    de `chunks.jsonl` extraído aparezca en los DOS manifiestos — es la
    prueba de que el índice FAISS se construyó sobre exactamente esos
    fragmentos. Si eso no cuadra, el retrieval devuelve texto equivocado
    sin avisar.
    """
    for nombre, esperado in PAQUETES:
        origen = _localizar_zip(nombre)
        if origen is None:
            raise CorpusNoEncontrado(
                f"No encuentro {nombre}. Cópialo a {RAIZ / 'dataset'} "
                f"(o a una de: {[str(c) for c in CANDIDATOS_ZIP]})."
            )
        obtenido = _sha256(origen)
        if obtenido != esperado:
            raise CorpusNoEncontrado(
                f"{nombre} no coincide con lo esperado: fichero corrupto o "
                f"de otra versión.\n  esperado: {esperado}\n"
                f"  obtenido: {obtenido}"
            )
        with zipfile.ZipFile(origen) as zf:
            zf.extractall(DESTINO)
        if verbose:
            print(f"  {nombre}: hash OK, extraído.")

    huella = _sha256(DESTINO / "chunks.jsonl")
    for manifiesto in ("MANIFEST.md", "indice/MANIFEST.md"):
        ruta = DESTINO / manifiesto
        if ruta.exists() and huella not in ruta.read_text(encoding="utf-8"):
            raise CorpusNoEncontrado(
                f"chunks.jsonl no cuadra con {manifiesto}: el índice se "
                f"construyó sobre otros fragmentos."
            )
    if verbose:
        print(f"  chunks.jsonl alineado con los dos manifiestos.")
        print(f"Corpus verificado en {DESTINO}")
    return DESTINO


def dir_corpus() -> Path:
    """La carpeta del corpus, preparándola desde los ZIP si hace falta."""
    for candidato in CANDIDATOS_CORPUS:
        if (candidato / "chunks.jsonl").is_file():
            return candidato
    # No está extraído: si los ZIP están a mano, nos preparamos solos.
    if _localizar_zip(PAQUETES[0][0]) is not None:
        return preparar_corpus(verbose=False)
    raise CorpusNoEncontrado(
        "No encuentro el corpus ni los ZIP para prepararlo. Copia "
        "corpus_miax_2026.zip e indice_faiss.zip a la carpeta dataset/ "
        "del repositorio."
    )


# ---------------------------------------------------------------------------
# Carga (una vez por proceso)
# ---------------------------------------------------------------------------
def _leer_jsonl(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


@functools.lru_cache(maxsize=1)
def cargar_secciones() -> list[dict]:
    """Las 48 secciones íntegras (una por ticker, ejercicio e item)."""
    return _leer_jsonl(dir_corpus() / "secciones.jsonl")


@functools.lru_cache(maxsize=1)
def cargar_chunks() -> list[dict]:
    """Los 1.749 fragmentos del troceado base, con su chunk_id."""
    return _leer_jsonl(dir_corpus() / "chunks.jsonl")


@functools.lru_cache(maxsize=1)
def cargar_xbrl():
    """Los 135 hechos XBRL: la fuente autorizada para cualquier cifra."""
    import pandas as pd
    return pd.read_parquet(dir_corpus() / "xbrl_facts.parquet")


@functools.lru_cache(maxsize=1)
def cargar_indice():
    """`(indice, meta, codificador)`.

    La primera llamada tarda: carga FAISS y el modelo de embeddings (~130 MB
    de descarga si no está en la caché local de Hugging Face). Por eso va en
    una función cacheada y no en el import.
    """
    import faiss
    import pandas as pd
    from sentence_transformers import SentenceTransformer

    base = dir_corpus() / "indice"
    indice = faiss.read_index(str(base / "corpus.faiss"))
    meta = pd.read_parquet(base / "chunks_meta.parquet")
    if indice.ntotal != len(meta):
        raise RuntimeError(
            f"El índice tiene {indice.ntotal} vectores y los metadatos "
            f"{len(meta)} filas: están desalineados. Borra corpus/ y deja "
            f"que se regenere desde los ZIP."
        )
    return indice, meta, SentenceTransformer(MODELO_EMBEDDINGS)


def codificar(textos: list[str], es_consulta: bool = True):
    """Vectores float32 normalizados, con el prefijo BGE si son consultas."""
    _, _, codificador = cargar_indice()
    if es_consulta:
        textos = [PREFIJO_CONSULTA_BGE + t for t in textos]
    return codificador.encode(
        textos, normalize_embeddings=True, convert_to_numpy=True
    ).astype("float32")


# ---------------------------------------------------------------------------
# Utilidades compartidas por retrieval, herramientas y (luego) evaluadores
# ---------------------------------------------------------------------------
_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Espacios colapsados y minúsculas: la comparación de anclas y citas."""
    return _ESPACIOS.sub(" ", texto).strip().lower()


def fila_a_fragmento(fila, puntuacion: float) -> dict:
    """Una fila de `chunks_meta` en el dict que manejan las herramientas."""
    return {
        "chunk_id": fila["chunk_id"],
        "ticker": fila["ticker"],
        "fiscal_year": int(fila["fiscal_year"]),
        "item": fila["item"],
        "texto": fila["texto"],
        "n_tokens": int(fila["n_tokens"]),
        "contiene_tabla": bool(fila["contiene_tabla"]),
        "inicio_car": int(fila["inicio_car"]),
        "fin_car": int(fila["fin_car"]),
        "puntuacion": round(float(puntuacion), 4),
    }


def formatear_fragmentos(fragmentos: list[dict]) -> str:
    """Los fragmentos, en el texto que ve el modelo.

    El chunk_id delante de cada uno es lo que permite citar y lo que el
    evaluador `cita_correcta` comprueba después.
    """
    if not fragmentos:
        return ("Sin resultados para esa consulta con esos filtros. "
                "Prueba a quitar algún filtro o a reformular la búsqueda.")
    return "\n\n---\n\n".join(
        f"[{f['chunk_id']}] {f['ticker']} FY{f['fiscal_year']} "
        f"Item {f['item']} (similitud {f['puntuacion']:.3f})\n{f['texto']}"
        for f in fragmentos
    )
