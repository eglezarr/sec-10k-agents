# Agente investigador sobre informes 10-K de la SEC

Práctica de *LLMs aplicados a Finanzas* (MIAX 2026). Un agente con cuatro
herramientas que responde preguntas sobre los 10-K de NVDA, MSFT, AAPL,
GOOGL, META y AMZN (FY2024–FY2025), citando de dónde sale cada dato, con
guardrails contra cifras no verificadas y evaluación automática de calidad,
coste y latencia.

## Contrato del día 24

El hold-out de 10 preguntas ciegas se ejecuta contra este repositorio, en
un clon limpio y sin editar nada:

```python
from agente.interfaz import responder, evaluar

responder("¿Cuál fue el revenue de NVIDIA en FY2024?")
evaluar("holdout.jsonl")
```

Las firmas de las cuatro herramientas (`list_available`, `get_xbrl_fact`,
`search_filings`, `read_section`) y el esquema `RespuestaFinanciera` son
contrato del enunciado y no se modifican.

## Puesta en marcha

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/preparar_corpus.py      # extrae dataset/*.zip -> corpus/ y verifica hashes
python scripts/humo_herramientas.py    # prueba de las 4 herramientas, sin clave
python scripts/validar_golden.py golden/golden_set.jsonl --final
```

Los dos ZIP del profesor van versionados en `dataset/`; `corpus/` es
derivado y no se versiona (cualquier import de `agente.datos` lo extrae si
falta).

La clave del modelo hace falta para ejecutar el agente y la reescritura de
consultas:

```bash
export OPENROUTER_API_KEY=...          # se obtiene en openrouter.ai/keys
```

Nunca se escribe en código ni se versiona. Los notebooks la piden por
`getpass` si no está en el entorno.

## Estructura

```
agente/
  agente.py         RespuestaFinanciera + system prompt + crear_agente()
  interfaz.py       responder(pregunta, thread_id) y evaluar(ruta_jsonl): contrato del día 24
  herramientas.py   las 4 tools del contrato (los docstrings son el enrutado)
  retrieval.py      escalera de búsqueda: densa, +filtros, híbrida RRF, reescritura
  metricas.py       acierta, recall@5, posición del ancla
  evaluadores.py    cita / cifra / trayectoria + evaluar() + resumir() + por_familia()
  trazas.py         coste, tokens, latencia, trayectoria (pretty_trace)
  datos.py          localización, verificación (SHA-256) y carga del corpus
golden/
  golden_set.jsonl  golden propio: 20 preguntas (7 numéricas · 7 extractivas · 6 comparativas)
  oficial_20.jsonl  las 20 preguntas oficiales del profesor (diagnóstico y comparabilidad)
  huecos_humo.jsonl 5 preguntas sin respuesta en el corpus (ensayo de fuente='ninguna')
notebooks/
  01_retrieval.ipynb           escalera de recall@5 (golden propio y oficial) y matriz de LLM × embeddings
  02_congelacion_baseline.ipynb tirada baseline (propio / oficial / huecos)
resultados/         CSV de mediciones, regenerables desde los notebooks
scripts/
  preparar_corpus.py     extrae y verifica el corpus
  validar_golden.py      validador del golden (reglas del taller + checks propios)
  humo_herramientas.py   sin clave
  humo_evaluadores.py    sin clave (resultados sintéticos)
  humo_agente.py         con clave (~10-15 ¢)
dataset/            los ZIP del profesor (versionados)
```

## Golden set propio

`golden/golden_set.jsonl` tiene 20 preguntas con respuesta verificable
contra el corpus. Pasa `scripts/validar_golden.py --final`: cada cifra
coincide con el parquet XBRL y cada ancla es una frase literal del informe
(≤40 palabras) presente en la sección y en un chunk.

| Familia | n | Mide |
|---|---|---|
| Numérica | 7 | Enrutado a `get_xbrl_fact` y guardrail de cifras |
| Extractiva | 7 | Retrieval y trazabilidad de la cita |
| Comparativa | 6 | Cifra XBRL más explicación en texto, entre dos ejercicios |

Cubre las seis empresas (3–4 preguntas cada una), los dos ejercicios
(10 y 10), las cuatro secciones (1A, 7, 7A y 8) y 10 de los 13 conceptos
XBRL. Incluye las trampas del corpus: el concepto de ingresos que varía por
empresa, el pasivo de Microsoft a un 0,6 % de su revenue, el calendario
fiscal de NVIDIA, leasings y financiación fuera de balance, y los cambios
de política de amortización de Meta y Amazon.

## Estado

- [x] Corpus verificado y cuatro herramientas
- [x] Agente baseline (`create_agent` + `RespuestaFinanciera` + `concept_xbrl`) e interfaz `responder`
- [x] Escalera de retrieval (filtros / híbrido RRF / reescritura) y métricas
- [x] Evaluadores (cita / cifra con huecos / trayectoria), `evaluar()` y `resumir()`
- [x] Validador del golden y golden propio (20 = 7/7/6) sin fallos
- [x] Notebook 01: escalera de retrieval y matriz de modelos medidas sobre el golden propio y el oficial
- [ ] Tirada baseline sobre el golden final (notebook 02) y `git tag baseline`
- [ ] Middleware: límite de llamadas y verificación de cifras contra XBRL por concepto
- [ ] Mejoras medidas: híbrida en `search_filings`, middleware, re-ranker candidato
- [ ] Notebook 03: tabla baseline frente a final, informe PDF y ensayo del clon limpio
