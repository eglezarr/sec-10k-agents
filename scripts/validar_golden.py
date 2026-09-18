"""Validador del golden set (enunciado §3 y celda 32 de la S1).

Un golden set solo sirve si sus respuestas esperadas son VERDAD: una cifra
mal copiada o un ancla que no está literal en el informe convierten la
evaluación en ruido. Este validador aplica dos capas:

NÚCLEO (las reglas del taller — un incumplimiento es FALLO):
  - Los 16 campos del esquema presentes; id único; familia válida.
  - ticker y fiscal_year existen en el corpus.
  - herramienta_esperada: lista no vacía, subconjunto de las 4 tools.
  - numerica  -> cifra_esperada y concept_xbrl obligatorios.
  - extractiva -> ancla_texto obligatoria.
  - comparativa -> cifra_esperada, concept_xbrl Y ancla_texto obligatorios.
  - concept_xbrl (si lo hay) existe para ese (ticker, fiscal_year).
  - ancla_texto (si la hay): <=40 palabras, item_esperado declarado, y
    aparece LITERAL (normalizada) en esa sección.

PROPIAS (posibles porque generamos desde el corpus — también FALLO):
  - cifra_esperada coincide con el valor del parquet (y unidad con unit).
  - ancla_inicio/ancla_fin reproducen el ancla exacta en la sección.
  - chunk_id_esperado existe y contiene el ancla.

A nivel de FICHERO (con --final): 20 preguntas y >=6 comparativas.

Uso:
    python scripts/validar_golden.py golden/golden_set.jsonl --final
    python scripts/validar_golden.py golden/propio_borrador.jsonl
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agente import datos  # noqa: E402

CAMPOS = ["id", "pregunta", "familia", "ticker", "fiscal_year",
          "respuesta_esperada", "cifra_esperada", "unidad", "concept_xbrl",
          "item_esperado", "ancla_texto", "ancla_inicio", "ancla_fin",
          "chunk_id_esperado", "herramienta_esperada", "autor"]
FAMILIAS = {"numerica", "extractiva", "comparativa"}
HERRAMIENTAS = {"list_available", "get_xbrl_fact", "search_filings",
                "read_section"}
MAX_PALABRAS_ANCLA = 40


def validar(preguntas: list[dict], final: bool = False):
    """Devuelve (fallos, avisos): listas de mensajes 'id: problema'."""
    xbrl = datos.cargar_xbrl()
    secciones = {(s["ticker"], int(s["fiscal_year"]), s["item"]): s
                 for s in datos.cargar_secciones()}
    chunks = {c["chunk_id"]: c for c in datos.cargar_chunks()}
    tickers = {t for t, _, _ in secciones}
    ejercicios = {fy for _, fy, _ in secciones}

    fallos: list[str] = []
    avisos: list[str] = []
    vistos: set[str] = set()

    for n, g in enumerate(preguntas, 1):
        ident = g.get("id") or f"(línea {n})"
        F = lambda m: fallos.append(f"{ident}: {m}")      # noqa: E731
        A = lambda m: avisos.append(f"{ident}: {m}")      # noqa: E731

        faltan = [c for c in CAMPOS if c not in g]
        if faltan:
            F(f"faltan campos {faltan}")
            continue
        extras = [c for c in g if c not in CAMPOS]
        if extras:
            A(f"campos fuera del esquema {extras}")

        if g["id"] in vistos:
            F("id duplicado")
        vistos.add(g["id"])

        if g["familia"] not in FAMILIAS:
            F(f"familia desconocida {g['familia']!r}")
            continue
        if g["ticker"] not in tickers:
            F(f"ticker {g['ticker']!r} fuera del corpus")
            continue
        if int(g["fiscal_year"]) not in ejercicios:
            F(f"fiscal_year {g['fiscal_year']} fuera del corpus")
            continue

        hs = g["herramienta_esperada"]
        if not isinstance(hs, list) or not hs or not set(hs) <= HERRAMIENTAS:
            F(f"herramienta_esperada inválida: {hs!r}")

        fam = g["familia"]
        if fam in ("numerica", "comparativa"):
            if g["cifra_esperada"] is None or not g["concept_xbrl"]:
                F(f"{fam} exige cifra_esperada y concept_xbrl")
        if fam in ("extractiva", "comparativa") and not g["ancla_texto"]:
            F(f"{fam} exige ancla_texto")

        # --- concepto y cifra contra el parquet -------------------------
        if g["concept_xbrl"]:
            fila = xbrl[(xbrl.ticker == g["ticker"])
                        & (xbrl.fiscal_year == int(g["fiscal_year"]))
                        & (xbrl.concept == g["concept_xbrl"])]
            if fila.empty:
                F(f"{g['ticker']} FY{g['fiscal_year']} no reporta "
                  f"'{g['concept_xbrl']}'")
            else:
                valor = float(fila.iloc[0].value)
                if g["cifra_esperada"] is not None:
                    esperada = float(g["cifra_esperada"])
                    ref = abs(valor) if valor else 1.0
                    if abs(esperada - valor) / ref > 1e-6:
                        F(f"cifra_esperada {esperada!r} != parquet {valor!r}")
                    if g["unidad"] and g["unidad"] != fila.iloc[0].unit:
                        A(f"unidad {g['unidad']!r} != parquet "
                          f"{fila.iloc[0].unit!r}")

        # --- ancla contra la sección ------------------------------------
        if g["ancla_texto"]:
            palabras = len(str(g["ancla_texto"]).split())
            if palabras > MAX_PALABRAS_ANCLA:
                F(f"ancla de {palabras} palabras (máx "
                  f"{MAX_PALABRAS_ANCLA})")
            elif palabras > 30:
                A(f"ancla de {palabras} palabras, cerca del límite")
            if not g["item_esperado"]:
                F("ancla sin item_esperado")
            else:
                clave = (g["ticker"], int(g["fiscal_year"]),
                         g["item_esperado"])
                seccion = secciones.get(clave)
                if seccion is None:
                    F(f"no existe la sección {clave}")
                else:
                    texto = seccion["texto"]
                    if datos.normalizar(g["ancla_texto"]) not in \
                            datos.normalizar(texto):
                        F("el ancla NO aparece literal en la sección")
                    ini, fin = g["ancla_inicio"], g["ancla_fin"]
                    if ini is not None and fin is not None \
                            and texto[ini:fin] != g["ancla_texto"]:
                        F("ancla_inicio/fin no reproducen el ancla")
            cid = g["chunk_id_esperado"]
            if cid:
                if cid not in chunks:
                    F(f"chunk_id_esperado {cid!r} no existe")
                elif datos.normalizar(g["ancla_texto"]) not in \
                        datos.normalizar(chunks[cid]["texto"]):
                    F(f"el ancla no está dentro de {cid}")

        if not str(g.get("respuesta_esperada") or "").strip():
            A("respuesta_esperada vacía")
        if str(g.get("autor") or "").strip() in ("", "pendiente"):
            A("autor sin rellenar")

    if final:
        if len(preguntas) != 20:
            fallos.append(f"(fichero): {len(preguntas)} preguntas, "
                          f"deben ser 20")
        comparativas = sum(1 for g in preguntas
                           if g.get("familia") == "comparativa")
        if comparativas < 6:
            fallos.append(f"(fichero): {comparativas} comparativas, "
                          f"mínimo 6")

    return fallos, avisos


def main() -> int:
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    final = "--final" in sys.argv
    if not argumentos:
        print(__doc__)
        return 2
    from agente.evaluadores import cargar_golden

    preguntas = cargar_golden(argumentos[0])
    fallos, avisos = validar(preguntas, final=final)

    familias = {}
    for g in preguntas:
        familias[g.get("familia", "?")] = familias.get(
            g.get("familia", "?"), 0) + 1
    print(f"{argumentos[0]}: {len(preguntas)} preguntas {familias}"
          f"{'  [modo final]' if final else ''}")

    for a in avisos:
        print(f"  AVISO  {a}")
    for f in fallos:
        print(f"  FALLO  {f}")
    if not fallos:
        print(f"  VALIDADO{' (final)' if final else ''}: sin fallos"
              f"{f', {len(avisos)} avisos' if avisos else ''}.")
        return 0
    print(f"  {len(fallos)} fallos, {len(avisos)} avisos.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
