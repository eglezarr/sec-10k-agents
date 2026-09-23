# Agente investigador sobre informes 10-K de la SEC

Práctica de *LLMs aplicados a Finanzas* (MIAX 2026) · Luis Coello, Eneko
Amezcua y Eduardo González.

Un agente con cuatro herramientas que responde preguntas sobre los 10-K de
NVIDIA, Microsoft, Apple, Alphabet, Meta y Amazon (ejercicios 2024 y 2025).
Las cifras salen de los datos oficiales XBRL, el texto va con cita
verificable y, si el dato no está en el corpus, lo dice. Un verificador
comprueba cada cifra contra XBRL antes de entregar la respuesta, y todo el
sistema se evalúa con tres evaluadores automáticos midiendo calidad, coste
y latencia.

## Resultado en una tabla

Golden propio (20 preguntas), baseline congelado frente al sistema oficial:

| Sistema | Cita | Cifra | Herramienta | Recall@5 | Coste / pregunta | Latencia media | Llamadas / pregunta |
|---|---|---|---|---|---|---|---|
| Baseline | 11/13 | 10/13 | 20/20 | 9/13 | **1,28 ¢** | **23 s** | 3,6 |
| Sistema oficial | **13/14** | **12/13** | 20/20 | **12/13** | 2,08 ¢ | 26 s | 3,6 |

*Aciertos sobre preguntas evaluables; en negrita, el mejor valor.*

- **Dónde está la mejora:** las numéricas (7/7) y las extractivas (7/7) ya
  salían bien en el baseline; lo que fallaba eran las comparativas: cifra
  3/6 → 5/6 y cita 4/6 → 5/6. En el golden oficial, las comparativas pasan
  de 1/7 a 7/7 en cifra.
- **En las 40 preguntas** (propio y oficial): de 14 preguntas con algún
  fallo a 3, por 0,25 ¢ más por pregunta de media (1,52 → 1,77 ¢).
- **Enrutado:** la herramienta correcta en el 100 % de las preguntas, ya
  desde el baseline.
- **Ensayo del hold-out** (notebook 06, sistema oficial sobre el golden
  oficial): cifra 14/14, cita 15/15, herramienta 20/20, recall 11/13, sin
  errores.

Detalle completo, sistema a sistema: `resultados/tabla_baseline_vs_final_propio.md`,
`resultados/tabla_baseline_vs_final_oficial.csv` y el notebook 05.

## Contrato del día 24

El hold-out de 10 preguntas ciegas se ejecuta contra este repositorio, en
un clon limpio y sin editar nada:

```python
from agente.interfaz import responder, evaluar

r = responder("¿Cuál fue el revenue de NVIDIA en FY2024?")
r["structured_response"]                        # RespuestaFinanciera validada
evaluar("holdout.jsonl", etiqueta="holdout")    # -> resultados/eval_holdout.csv
```

- `responder(pregunta, thread_id=None, config=CONFIG_POR_DEFECTO, modelo=MODELO)`
  devuelve el resultado de la invocación más `coste_usd` y `latencia_s`.
- `evaluar(ruta_jsonl, etiqueta="eval", config=CONFIG_POR_DEFECTO, modelo=MODELO)`
  ejecuta cada pregunta en su propia conversación, aplica los tres
  evaluadores y guarda el detalle en `resultados/eval_<etiqueta>.csv`.
- El sistema por defecto es el **oficial** (`cifras_comparadas`) con
  `google/gemini-3.8-flash` vía OpenRouter.
- El día 24 se usa el **notebook 06**, que envuelve `evaluar()`: valida el
  fichero, cronometra la tirada y calcula el delta contra el golden propio
  (`resultados/holdout_vs_propio.csv`). La página
  [`web/holdout.html`](https://raw.githack.com/eglezarr/sec-10k-agents/main/web/holdout.html)
  muestra el resultado pregunta a pregunta.

Las firmas de las cuatro herramientas (`list_available`, `get_xbrl_fact`,
`search_filings`, `read_section`) y los ocho campos de `RespuestaFinanciera`
son contrato del enunciado y no se modifican.

## Puesta en marcha

Requiere **Python 3.10 o superior** (probado con 3.12): las versiones
fijadas de LangChain no instalan en 3.9.

```bash
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt       # tarda: sentence-transformers instala PyTorch

python scripts/preparar_corpus.py     # extrae dataset/*.zip -> corpus/ y verifica los hashes
python scripts/humo_herramientas.py   # las 4 herramientas, sin clave
python scripts/humo_evaluadores.py    # los 3 evaluadores, sin clave
python scripts/validar_golden.py golden/golden_set.jsonl --final
```

La primera búsqueda descarga el modelo de embeddings (`BAAI/bge-small-en-v1.5`,
unos 130 MB). Los dos ZIP del profesor van versionados en `dataset/`;
`corpus/` es derivado y no se versiona (cualquier import de `agente.datos`
lo extrae si falta).

Para ejecutar el agente hace falta una clave de OpenRouter:

```bash
export OPENROUTER_API_KEY=...         # openrouter.ai/keys
python scripts/humo_agente.py         # tres preguntas reales, unos céntimos
```

Nunca se escribe en código ni se versiona. Los notebooks la piden con
`getpass` si no está en el entorno (el kernel de Jupyter no hereda el
`export` del terminal).

## Cómo funciona

**Cuatro herramientas** (`agente/herramientas.py`). El modelo solo ve su
nombre y su descripción, así que las descripciones son el enrutado: la
herramienta exacta, `get_xbrl_fact`, para cifras (su descripción enumera
los 13 conceptos XBRL y avisa de que el concepto de ingresos cambia por
compañía); la difusa, `search_filings`, para el texto, con consultas en
inglés; `list_available` para saber qué hay en el corpus; y `read_section`
para una sección completa.

**Respuesta estructurada** (`agente/agente.py`). `RespuestaFinanciera` tiene
los ocho campos del enunciado más tres añadidos: `concept_xbrl` (el
concepto del que sale la cifra, para verificarla contra el hecho exacto) y,
en las comparativas, `cifra_anterior` y `variacion_pct`.

**Guardrails** (`agente/guardrails.py`), como middleware de LangChain:

- Límite de llamadas: 12 a herramientas y 16 al modelo por pregunta.
- Reintento con espera ante límites de peticiones y errores transitorios.
- **Verificador de cifras**: compara `cifra` (y, en comparativas, las tres
  cifras) con el hecho XBRL del concepto declarado, con tolerancia del
  0,1 %. Si no cuadra, devuelve el desajuste al modelo para que corrija
  (como máximo dos veces). También frena una cifra con `fuente='ninguna'`
  y exige la salida estructurada. Se verifica contra el concepto exacto
  porque en este corpus hay hechos vecinos: en Microsoft FY2024, los
  pasivos (243.686 M$) y los ingresos (245.122 M$) están a un 0,6 %.

**Búsqueda** (`agente/retrieval.py`): híbrida, densa (FAISS con
`bge-small-en-v1.5`) más BM25, fusionadas por posición (RRF), con los
filtros de compañía, ejercicio y sección.

**Sistemas** (`CONFIGURACIONES` en `agente/agente.py`); cada uno añade una
mejora al anterior:

| Configuración | Qué añade |
|---|---|
| `baseline` | Prompt v1, búsqueda densa, sin middleware (congelado) |
| `prompt_v2` | Convención de la cifra en comparativas, citas literales, vocabulario del informe |
| `guardrails` | Límites, reintento y verificador de cifras |
| `final` | Búsqueda híbrida en `search_filings` |
| `cifras_comparadas` | **Sistema oficial.** Prompt v3: las tres cifras de cada comparativa, verificadas |

## Evaluación

| Conjunto | Fichero | Papel |
|---|---|---|
| Golden propio (20) | `golden/golden_set.jsonl` | La tabla del informe: 7 numéricas · 7 extractivas · 6 comparativas |
| Golden oficial (20) | `golden/oficial_20.jsonl` | Control con las preguntas del profesor |
| Huecos (5) | `golden/huecos_humo.jsonl` | Preguntas sin respuesta en el corpus: lo correcto es `fuente='ninguna'` sin cifra |

Tres evaluadores (`agente/evaluadores.py`), funciones deterministas que
devuelven acierto, fallo o no aplica:

- **Cita:** el fragmento citado existe y la cita está dentro de él.
- **Cifra:** coincide con el dato XBRL con tolerancia relativa del 1 %. En
  un hueco, inventarse una cifra es fallo.
- **Herramienta:** la trayectoria pasa por las herramientas esperadas.

El golden propio pasa `scripts/validar_golden.py --final`: cada cifra
coincide con el XBRL y cada ancla es una frase literal del informe
(≤40 palabras) presente en su sección y en un fragmento. Cubre las seis
empresas, los dos ejercicios, las cuatro secciones y las trampas del
corpus (el concepto de ingresos que cambia por empresa, los hechos
vecinos de Microsoft, el calendario fiscal de NVIDIA, leasings y
financiación fuera de balance, cambios de política de amortización).

## Estructura

```
agente/
  interfaz.py        responder() y evaluar(): el contrato del día 24
  agente.py          RespuestaFinanciera, prompts v1-v3, CONFIGURACIONES y crear_agente()
  herramientas.py    las 4 herramientas del contrato
  guardrails.py      límites, reintento y verificador de cifras (middleware)
  retrieval.py       búsqueda densa, filtros, híbrida RRF y reescritura de consultas
  evaluadores.py     cita / cifra / trayectoria, evaluar(), resumir(), por_familia()
  metricas.py        recall@5 y posición del ancla
  trazas.py          coste, tokens, latencia y trayectoria (pretty_trace)
  datos.py           localización, verificación SHA-256 y carga del corpus
golden/              golden propio, golden oficial y huecos
notebooks/
  01_retrieval.ipynb             escalera de recall@5 y matriz de embeddings × LLM de reescritura
  02_congelacion_baseline.ipynb  tirada del baseline (propio / oficial / huecos)
  03_diagnostico_fallos.ipynb    causa de cada fallo del baseline
  04_guardrails.ipynb            los guardrails, probados con modelo simulado y real
  05_mejoras_y_evaluacion.ipynb  ablación, tabla baseline vs final, sensibilidad y tabla de decisiones
  06_hold_out.ipynb              lanzador de las 10 preguntas ciegas (día 24)
resultados/          CSV de todas las mediciones (eval_<sistema>_<golden>.csv y tablas)
scripts/             preparar_corpus, validar_golden y pruebas de humo
web/holdout.html     página estática con el resultado del hold-out pregunta a pregunta
dataset/             los dos ZIP del profesor (versionados) y sus hashes
```

Todas las cifras del informe salen de `resultados/*.csv` y se regeneran
con los notebooks sin volver a llamar al modelo (reutilizan los CSV
existentes salvo que se pida repetir).

## Versiones congeladas

- Tag **`baseline-v2`**: el baseline válido, congelado sobre el golden
  propio final. Es el que se compara en todas las tablas.
- Tag `baseline`: el primer baseline, sobre una versión anterior del
  golden. Se conserva como histórico; no es comparable.

## Limitaciones conocidas

- **Variabilidad entre tiradas.** El modelo no es determinista ni con
  `temperature=0`: el mismo sistema ha variado varias preguntas de una
  tirada a otra. La mejora del baseline al sistema oficial es estable en
  las tres tiradas; el reparto del mérito entre mejoras, no.
- **Resultado algo optimista en el golden propio**: las mejoras se
  eligieron mirando esas preguntas. El hold-out es la comprobación real.
- **El verificador no revisa las cifras con `fuente='texto'`** (no hay hecho
  XBRL contra el que compararlas): es el fallo que queda en `pr-c11`.
- **Sin tiempo máximo por llamada al modelo**: un atasco del proveedor ha
  llegado a tardar 174 s en una pregunta.
- La cuenta de OpenRouter limita a 20 peticiones por minuto; el reintento
  con espera lo absorbe, pero conviene no lanzar tandas en paralelo.
