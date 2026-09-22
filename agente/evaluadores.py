"""Los tres evaluadores del enunciado §5, `evaluar()` y `resumir()`.

La firma común es la de la sesión 2: `evaluador(item, resultado)` devuelve
`True` (bien), `False` (mal) o `None` (no aplica a este ítem). El `None` se
excluye de las medias — no es un aprobado ni un suspenso, es "esta métrica
no mide esto".

Semántica exacta, con las dos mejoras nuestras argumentadas donde tocan:

1. `cita_correcta` — la cita existe Y respalda. El chunk citado tiene que
   existir en el corpus servido (inventarse un chunk_id es False), y los
   primeros ~120 caracteres de la cita, normalizados, tienen que estar
   dentro de su texto (el modelo recorta citas largas; 120 bastan para
   distinguir respaldo de invención). Sin chunk_id: None en numéricas
   (citar no es su trabajo), False en extractivas y comparativas (sí lo
   es). Decisión determinista, sin LLM-juez: auditable, gratis y
   reproducible.

2. `cifra_coincide_xbrl` — tolerancia RELATIVA del 1% (`cuadra`), la de la
   S2: funciona igual para un revenue de 10^11 que para un EPS de 2,97, y
   "redondear a 281.700 millones no es inventarse un número; inventárselo
   es decir 250.000".
   MEJORA DE HUECOS (nuestra): si el ítem es numérico o comparativo y trae
   `cifra_esperada = null`, codifica un hueco ("no está en el corpus") —
   al menos 2 de las 10 ciegas del día 24 son así. El evaluador del taller
   devolvía None ahí, con lo que INVENTARSE una cifra en un hueco salía
   gratis. Aquí: True solo si el agente respondió cifra=None y
   fuente='ninguna'; False en cualquier otro caso. En extractivas,
   cifra_esperada nula sigue siendo None (no aplica de verdad).

3. `uso_la_tool_correcta` — todas las herramientas de
   `herramienta_esperada` aparecen en la trayectoria (subconjunto, sin
   exigir orden). Es el evaluador que separa "acertó" de "acertó por el
   camino correcto": una numérica resuelta leyendo la prosa falla aquí
   aunque la cifra sea exacta. Siempre devuelve bool.

`evaluar()` ejecuta una lista de preguntas contra una función `responder`,
aísla cada pregunta en su propio `thread_id`, envuelve cada una en
try/except (un fallo es una fila con error, no un crash de la tanda) y
añade por pregunta: recall del componente de búsqueda (con la configuración
que se le pase — así la fila baseline mide el retrieval del baseline y la
final el suyo, no como en el arnés del taller, donde la columna recall
usaba siempre la configuración final), nº de llamadas a herramienta, coste
y latencia. `resumir()` colapsa el DataFrame en la fila de la tabla del
informe; `por_familia()` da el desglose que pide el enunciado.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import datos, metricas, trazas

TOLERANCIA = 0.01   # 1% relativo (S2): redondeo legítimo sí, invención no


# ---------------------------------------------------------------------------
# Primitivas
# ---------------------------------------------------------------------------
def cuadra(afirmada: float, esperada: float,
           tolerancia: float = TOLERANCIA) -> bool:
    """¿La cifra afirmada está a menos de `tolerancia` relativa de la
    esperada? Con esperada = 0, comparación absoluta contra la tolerancia."""
    if esperada == 0:
        return abs(afirmada) <= tolerancia
    return abs(afirmada - esperada) / abs(esperada) <= tolerancia


def _estructurada(resultado):
    r = (resultado or {}).get("structured_response")
    if r is None:
        raise RuntimeError("La invocación no devolvió structured_response")
    return r


_POR_ID: dict | None = None


def _chunks_por_id() -> dict:
    """chunk_id -> chunk del corpus SERVIDO. Si algún día se re-trocea, esta
    tabla debe construirse sobre los chunks nuevos: el evaluador comprueba
    la cita contra lo que el agente pudo ver, no contra un troceado viejo."""
    global _POR_ID
    if _POR_ID is None:
        _POR_ID = {c["chunk_id"]: c for c in datos.cargar_chunks()}
    return _POR_ID


# ---------------------------------------------------------------------------
# Evaluador 1 · la cita existe y respalda
# ---------------------------------------------------------------------------
def cita_correcta(item: dict, resultado) -> bool | None:
    r = _estructurada(resultado)
    if not r.chunk_id:
        return None if item.get("familia") == "numerica" else False
    chunk = _chunks_por_id().get(r.chunk_id)
    if chunk is None:                     # chunk_id inventado
        return False
    if not r.cita:                        # chunk sin cita: no hay respaldo
        return False
    inicio = datos.normalizar(r.cita)[:120]
    return inicio in datos.normalizar(chunk["texto"])


# ---------------------------------------------------------------------------
# Evaluador 2 · la cifra coincide con XBRL (con huecos)
# ---------------------------------------------------------------------------
def cifra_coincide_xbrl(item: dict, resultado) -> bool | None:
    esperada = item.get("cifra_esperada")
    hueco = item.get("familia") in ("numerica", "comparativa")

    if esperada is None and not hueco:
        return None                       # extractiva: no aplica

    r = _estructurada(resultado)
    if esperada is None:
        # Hueco codificado: la respuesta correcta es NO dar cifra.
        return r.cifra is None and r.fuente == "ninguna"

    if r.cifra is None:                   # había cifra y no la dio
        return False
    return cuadra(float(r.cifra), float(esperada))


# ---------------------------------------------------------------------------
# Evaluador 3 · la trayectoria pasó por donde tenía que pasar
# ---------------------------------------------------------------------------
def uso_la_tool_correcta(item: dict, resultado) -> bool:
    usadas = set(trazas.herramientas_usadas(resultado))
    return set(item.get("herramienta_esperada") or []).issubset(usadas)


EVALUADORES = {
    "cita_ok": cita_correcta,
    "cifra_ok": cifra_coincide_xbrl,
    "tool_ok": uso_la_tool_correcta,
}


# ---------------------------------------------------------------------------
# La tanda completa
# ---------------------------------------------------------------------------
def evaluar(preguntas: list[dict], funcion_responder, etiqueta: str = "run",
            buscar_para_recall=None, ruta_salida: str | Path | None = None,
            progreso: bool = False):
    """Ejecuta `funcion_responder` sobre cada pregunta y aplica los tres
    evaluadores. Devuelve un DataFrame con una fila por pregunta.

    - Cada pregunta va en su propio `thread_id` ("{etiqueta}-{id}"): sin
      aislamiento, la memoria de una contamina la siguiente.
    - `buscar_para_recall(item) -> fragmentos` define QUÉ configuración de
      retrieval mide la columna `recall` (la del sistema evaluado).
    - Un error en una pregunta produce una fila con `error` relleno y sigue.
    """
    import pandas as pd

    filas = []
    for item in preguntas:
        fila = {"id": item["id"], "familia": item.get("familia"),
                # La pregunta y lo esperado van del golden, no de la respuesta:
                # se rellenan siempre, aunque la invocación falle. Sin esto, un
                # informe (o un tablero) tendría que volver a abrir el JSONL
                # para saber de qué trataba cada fila.
                "pregunta": item.get("pregunta"),
                "cifra_esperada": item.get("cifra_esperada"),
                "cita_ok": None, "cifra_ok": None, "tool_ok": None,
                "recall": None, "n_tools": None,
                "coste_usd": None, "latencia_s": None, "error": None,
                "cifra_agente": None, "fuente": None,
                "herramientas": None, "n_avisos": None,
                "cifra_anterior": None, "variacion_pct": None,
                "avisos_texto": None,
                "respuesta": None, "cita": None, "chunk_id": None}
        try:
            resultado = funcion_responder(
                item["pregunta"], thread_id=f"{etiqueta}-{item['id']}")
            fila["cita_ok"] = cita_correcta(item, resultado)
            fila["cifra_ok"] = cifra_coincide_xbrl(item, resultado)
            fila["tool_ok"] = uso_la_tool_correcta(item, resultado)
            fila["n_tools"] = len(trazas.herramientas_usadas(resultado))
            # Lo que respondió el agente: sin esto, un fallo solo se puede
            # diagnosticar repitiendo la pregunta.
            s = resultado["structured_response"]
            fila["cifra_agente"] = s.cifra
            fila["fuente"] = s.fuente
            fila["cifra_anterior"] = s.cifra_anterior       # solo las comparaciones las rellenan
            fila["variacion_pct"] = s.variacion_pct
            fila["respuesta"] = s.respuesta                 # la prosa: para leer, no solo comparar
            fila["cita"] = s.cita
            fila["chunk_id"] = s.chunk_id
            fila["herramientas"] = ",".join(trazas.herramientas_usadas(resultado))
            avisos = [str(m.content) for m in resultado["messages"]
                      if type(m).__name__ == "HumanMessage"][1:]   # avisos de los guardrails
            fila["n_avisos"] = len(avisos)
            fila["avisos_texto"] = " || ".join(avisos)              # qué se le dijo al modelo
            fila["coste_usd"] = resultado.get("coste_usd")
            fila["latencia_s"] = resultado.get("latencia_s")
            if buscar_para_recall is not None and item.get("ancla_texto"):
                fila["recall"] = metricas.acierta(
                    buscar_para_recall(item), item["ancla_texto"])
        except Exception as e:                    # la tanda no se para
            fila["error"] = f"{type(e).__name__}: {e}"
        filas.append(fila)
        if progreso:
            marca = "ERR " if fila["error"] else "ok  "
            coste = (f"{fila['coste_usd']*100:5.2f}c"
                     if fila["coste_usd"] is not None else "  -  ")
            print(f"  {marca}{fila['id']:10s} {coste}  "
                  f"cita={fila['cita_ok']} cifra={fila['cifra_ok']} "
                  f"tool={fila['tool_ok']}", flush=True)

    df = pd.DataFrame(filas)
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(ruta_salida, index=False)
    return df


def _media(serie) -> float:
    limpia = serie.dropna()
    return float(limpia.astype(float).mean()) if len(limpia) else float("nan")


def resumir(df, etiqueta: str) -> dict:
    """La fila de la tabla del informe: aciertos, recall@5, coste medio en
    céntimos, latencia media y llamadas por pregunta — coste y latencia como
    columnas, no como nota al pie (enunciado §5)."""
    return {
        "sistema": etiqueta,
        "n": len(df),
        "cita_ok": _media(df["cita_ok"]),
        "cifra_ok": _media(df["cifra_ok"]),
        "tool_ok": _media(df["tool_ok"]),
        "recall@5": _media(df["recall"]),
        "coste_medio_¢": _media(df["coste_usd"]) * 100,
        "latencia_media_s": _media(df["latencia_s"]),
        "tools_por_pregunta": _media(df["n_tools"]),
        "errores": int(df["error"].notna().sum()),
    }


def por_familia(df):
    """Aciertos por familia (el desglose que pide el enunciado)."""
    return (df.groupby("familia")[["cita_ok", "cifra_ok", "tool_ok"]]
              .agg(_media))


def cargar_golden(ruta: str | Path) -> list[dict]:
    """Un golden set JSONL como lista de dicts (líneas vacías fuera)."""
    texto = Path(ruta).read_text(encoding="utf-8")
    return [json.loads(l) for l in texto.splitlines() if l.strip()]
