"""Prueba de humo de la entrega 4: los tres evaluadores, sin modelo.

No necesita clave: construye resultados SINTÉTICOS (la estructura exacta
que devuelve `responder`) y los pasa por los evaluadores contra el corpus
y el golden REALES. Nueve casos, cada uno un comportamiento que el día 24
tiene que estar bien juzgado — incluida la mejora de huecos, que es la
diferencia entre penalizar o regalar una cifra inventada en las ciegas.

Uso, desde la raíz del repositorio:
    python scripts/humo_evaluadores.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, ToolMessage   # noqa: E402

from agente import datos, evaluadores                        # noqa: E402
from agente.agente import RespuestaFinanciera                # noqa: E402


def resultado_sintetico(estructura: RespuestaFinanciera,
                        herramientas: list[str]) -> dict:
    """El dict que devuelve responder(), fabricado a mano."""
    mensajes = []
    for i, nombre in enumerate(herramientas):
        mensajes.append(AIMessage(content="", tool_calls=[
            {"name": nombre, "args": {}, "id": f"c{i}"}]))
        mensajes.append(ToolMessage(content="(sintético)",
                                    tool_call_id=f"c{i}", name=nombre))
    mensajes.append(AIMessage(content="fin"))
    return {"messages": mensajes, "structured_response": estructura,
            "coste_usd": 0.0001, "latencia_s": 1.0}


def caso(n, titulo, evaluador, item, resultado, esperado):
    obtenido = evaluador(item, resultado)
    assert obtenido is esperado, (
        f"[{n}] {titulo}: esperado {esperado!r}, obtenido {obtenido!r}")
    print(f"  [{n}] {titulo:64s} -> {obtenido}")


print("=" * 72)
print("HUMO · entrega 4 — evaluadores (sin modelo, sin clave)")
print("=" * 72)

# Ítems del golden con los que se juzga (reales, del oficial):
oficial = evaluadores.cargar_golden("golden/oficial_20.jsonl")
of = {g["id"]: g for g in oficial}
numerica = of["of-008"]        # numérica con cifra_esperada
extract = of["of-002"]         # extractiva con ancla en MSFT-2025-1A-0004
chunk_real = datos.normalizar(
    next(c for c in datos.cargar_chunks()
         if c["chunk_id"] == "MSFT-2025-1A-0004")["texto"])

print(f"\nÍtems de prueba: {numerica['id']} (numérica, esperada "
      f"{numerica['cifra_esperada']:.3e}) · {extract['id']} (extractiva)")

R = RespuestaFinanciera   # abreviatura

print("\ncuadra(): la tolerancia del 1% con sus dos caras")
assert evaluadores.cuadra(100.0, 100.4) and evaluadores.cuadra(100.4, 100.0)
assert not evaluadores.cuadra(100.0, 150.0)
assert evaluadores.cuadra(numerica["cifra_esperada"] * 1.009,
                          numerica["cifra_esperada"])
print("  redondeo del 0.4% pasa · desviación del 50% no · +0.9% pasa")

print("\ncifra_coincide_xbrl:")
bien = R(respuesta="x", cifra=numerica["cifra_esperada"], unidad="USD",
         fuente="xbrl", concept_xbrl=numerica["concept_xbrl"])
caso(1, "numérica clavada", evaluadores.cifra_coincide_xbrl,
     numerica, resultado_sintetico(bien, ["get_xbrl_fact"]), True)

mal = bien.model_copy(update={"cifra": numerica["cifra_esperada"] * 0.8})
caso(2, "numérica desviada un 20%", evaluadores.cifra_coincide_xbrl,
     numerica, resultado_sintetico(mal, ["get_xbrl_fact"]), False)

hueco = {"id": "hx-01", "familia": "numerica", "cifra_esperada": None,
         "herramienta_esperada": ["get_xbrl_fact"]}
honesto = R(respuesta="No está en el corpus", cifra=None, fuente="ninguna")
caso(3, "HUECO respondido con fuente='ninguna' (mejora nuestra)",
     evaluadores.cifra_coincide_xbrl, hueco,
     resultado_sintetico(honesto, ["get_xbrl_fact"]), True)

inventada = R(respuesta="Unos 340.000M", cifra=340e9, unidad="USD",
              fuente="xbrl")
caso(4, "HUECO con cifra inventada (el taller devolvía None aquí)",
     evaluadores.cifra_coincide_xbrl, hueco,
     resultado_sintetico(inventada, ["get_xbrl_fact"]), False)

caso(5, "extractiva sin cifra: no aplica", evaluadores.cifra_coincide_xbrl,
     extract, resultado_sintetico(
         R(respuesta="x", fuente="texto", chunk_id="MSFT-2025-1A-0004",
           cita=chunk_real[100:220]), ["search_filings"]), None)

print("\ncita_correcta:")
con_cita = R(respuesta="x", fuente="texto", chunk_id="MSFT-2025-1A-0004",
             cita=chunk_real[100:260])
caso(6, "cita literal dentro del chunk citado", evaluadores.cita_correcta,
     extract, resultado_sintetico(con_cita, ["search_filings"]), True)

chunk_falso = con_cita.model_copy(update={"chunk_id": "MSFT-2025-1A-9999"})
caso(7, "chunk_id inventado", evaluadores.cita_correcta,
     extract, resultado_sintetico(chunk_falso, ["search_filings"]), False)

sin_chunk = R(respuesta="x", fuente="texto")
caso(8, "extractiva sin chunk_id", evaluadores.cita_correcta,
     extract, resultado_sintetico(sin_chunk, ["search_filings"]), False)
caso(9, "numérica sin chunk_id: no aplica", evaluadores.cita_correcta,
     numerica, resultado_sintetico(bien, ["get_xbrl_fact"]), None)

print("\nuso_la_tool_correcta:")
assert evaluadores.uso_la_tool_correcta(
    numerica, resultado_sintetico(bien, ["list_available", "get_xbrl_fact"]))
assert not evaluadores.uso_la_tool_correcta(
    numerica, resultado_sintetico(bien, ["search_filings"]))
comparativa = {"id": "cx", "familia": "comparativa",
               "herramienta_esperada": ["get_xbrl_fact", "search_filings"]}
assert evaluadores.uso_la_tool_correcta(
    comparativa, resultado_sintetico(bien,
        ["get_xbrl_fact", "get_xbrl_fact", "search_filings"]))
print("  subconjunto sin orden: extra no penaliza, faltante sí")

print("\nevaluar() + resumir() con un responder falso:")
guion = {
    numerica["id"]: resultado_sintetico(bien, ["get_xbrl_fact"]),
    extract["id"]: resultado_sintetico(con_cita, ["search_filings"]),
    "hx-01": resultado_sintetico(inventada, ["get_xbrl_fact"]),
}
def responder_falso(pregunta, thread_id=None):
    ident = thread_id.split("humo-", 1)[1]
    if ident == "explota":
        raise RuntimeError("fallo provocado")
    return guion[ident]

items = [numerica, extract, hueco,
         {"id": "explota", "familia": "numerica", "cifra_esperada": 1.0,
          "pregunta": "x", "herramienta_esperada": ["get_xbrl_fact"]}]
for it in items:
    it.setdefault("pregunta", "x")

df = evaluadores.evaluar(items, responder_falso, etiqueta="humo")
print(df[["id", "familia", "cita_ok", "cifra_ok", "tool_ok", "error"]]
      .to_string(index=False))
assert df.loc[df.id == "hx-01", "cifra_ok"].item() is False
assert df.loc[df.id == "explota", "error"].notna().item()
resumen = evaluadores.resumir(df, "humo")
assert resumen["errores"] == 1 and resumen["n"] == 4
print(f"\n  resumen: cita={resumen['cita_ok']:.2f} "
      f"cifra={resumen['cifra_ok']:.2f} tool={resumen['tool_ok']:.2f} "
      f"errores={resumen['errores']}")
print(evaluadores.por_familia(df).round(2))

print("\n" + "=" * 72)
print("HUMO EVALUADORES OK — la regla de medir está operativa.")
print("Siguiente: golden set propio (20 preguntas) y congelación del "
      "baseline con evaluar().")
print("=" * 72)
