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

# Copiar los dos ZIP del profesor a dataset/ (ver dataset/COLOCA_AQUI.md)
python golden/
  oficial_20.jsonl       las 20 preguntas oficiales del profesor
  golden_set.jsonl       EL GOLDEN PROPIO (20 = 7/7/6, congelado)
  propio_borrador.jsonl  28 candidatas originales (histórico de la selección)
  huecos_humo.jsonl      5 preguntas sin respuesta (ensayo 'fuente=ninguna')
  revision_borrador.md   documento de revisión de las candidatas
notebooks/
  01_retrieval.ipynb  la escalera medida, con argumentación
  02_congelacion_baseline.ipynb  tirada baseline (propio/oficial/huecos) + tag
resultados/           CSV de mediciones (regenerables desde los notebooks)
scripts/preparar_corpus.py      # extrae y verifica hashes -> corpus/
python golden/
  oficial_20.jsonl       las 20 preguntas oficiales del profesor
  golden_set.jsonl       EL GOLDEN PROPIO (20 = 7/7/6, congelado)
  propio_borrador.jsonl  28 candidatas originales (histórico de la selección)
  huecos_humo.jsonl      5 preguntas sin respuesta (ensayo 'fuente=ninguna')
  revision_borrador.md   documento de revisión de las candidatas
notebooks/
  01_retrieval.ipynb  la escalera medida, con argumentación
  02_congelacion_baseline.ipynb  tirada baseline (propio/oficial/huecos) + tag
resultados/           CSV de mediciones (regenerables desde los notebooks)
scripts/humo_herramientas.py    # prueba de humo, sin clave de API
```

La clave hace falta desde la entrega 2 (el agente):
`export OPENROUTER_API_KEY=...` (se obtiene en openrouter.ai/keys). Nunca
se escribe en código ni se versiona.

## Estructura

```
agente/
  agente.py         RespuestaFinanciera + system prompt + crear_agente()
  interfaz.py       responder(pregunta, thread_id) — contrato del día 24
  trazas.py         coste, tokens, latencia, trayectoria (pretty_trace)
  datos.py          localización, verificación (SHA-256) y carga del corpus
  retrieval.py      escalera de búsqueda: densa, +filtros, híbrida RRF, reescritura
  metricas.py       acierta, recall@5, posición del ancla
  evaluadores.py    cita/cifra/trayectoria + evaluar() + resumir() + por_familia()
  herramientas.py   las 4 tools del contrato (docstrings = enrutado)
golden/
  oficial_20.jsonl       las 20 preguntas oficiales del profesor
  golden_set.jsonl       EL GOLDEN PROPIO (20 = 7/7/6, congelado)
  propio_borrador.jsonl  28 candidatas originales (histórico de la selección)
  huecos_humo.jsonl      5 preguntas sin respuesta (ensayo 'fuente=ninguna')
  revision_borrador.md   documento de revisión de las candidatas
notebooks/
  01_retrieval.ipynb  la escalera medida, con argumentación
  02_congelacion_baseline.ipynb  tirada baseline (propio/oficial/huecos) + tag
resultados/           CSV de mediciones (regenerables desde los notebooks)
scripts/
  preparar_corpus.py
  humo_herramientas.py   sin clave
  humo_agente.py         con clave (~10-15 ¢)
  humo_evaluadores.py    sin clave (resultados sintéticos)
  validar_golden.py      validador del golden (núcleo del taller + checks propios)
dataset/            los ZIP del profesor (versionados; corpus/ es derivado)
```

## Estado

- [x] Entrega 1 — corpus verificado + 4 herramientas + humo
- [x] Entrega 2 — agente baseline (`create_agent` + `RespuestaFinanciera` + `concept_xbrl`) e interfaz `responder`
- [x] Entrega 3 — escalera de retrieval (filtros / híbrido RRF / reescritura) + métricas + notebook 01 (recall@5)
- [x] Entrega 4 — evaluadores (cita / cifra con huecos / trayectoria) + `evaluar()` + `resumir()` + humo offline
- [x] Entrega 5 — validador del golden + borrador propio (28 candidatas verificadas) + set de huecos
- [x] Entrega 6 — golden propio CONGELADO (20 = 7/7/6, `--final` sin fallos) + notebook 02 de congelación del baseline
- [ ] Middleware: límites + verificación de cifras contra XBRL por concepto
- [ ] Tirada baseline + `git tag baseline` (notebook 02)
- [ ] Mejoras medidas: flip a híbrida · middleware · re-ranker candidato
- [ ] Notebook 03: tabla baseline vs final · informe PDF · ensayo del clon limpio
