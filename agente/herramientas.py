"""Las cuatro herramientas del agente.

CONTRATO (enunciado §4 y §7): los nombres y los parámetros no se tocan.
Las 10 preguntas ciegas del día 24 se ejecutan contra estas firmas y el
evaluador de trayectoria las busca por nombre. Se puede reimplementar el
cuerpo, añadir parámetros con valor por defecto y añadir herramientas
nuevas; nada más.

El docstring de cada herramienta es lo ÚNICO que el modelo ve para decidir
si la llama y con qué argumentos: es enrutado, no documentación (lección de
la sesión 1). Mejoras nuestras sobre la versión del profesor, argumentadas:

1. `get_xbrl_fact` enumera los 13 conceptos del corpus y avisa de que el
   concepto de ingresos varía por compañía. El modelo no puede adivinar un
   vocabulario que no ha visto, y la trampa de of-012 (pedir a Alphabet el
   concepto de Apple) empieza exactamente ahí.
2. Formato de valores: la tool de repuesto del profesor imprime todo con
   `,.0f`, así que el EPS de Apple FY2024 (6.11 USD/shares) se lo sirve al
   modelo como "6". Aquí los valores por acción conservan sus decimales.
3. Ambos docstrings dicen qué hacer cuando la magnitud NO está en XBRL
   (capex, porcentajes de segmento, previsiones): buscarla en el texto y
   citarla, no estimarla. El golden oficial contiene esas preguntas
   (of-006, of-017, of-018) y la regla gruesa "toda cifra por XBRL" las
   rompe.
"""

from __future__ import annotations

from langchain.tools import tool

from . import datos, retrieval


def _formatear_valor(valor: float) -> str:
    """Miles con separador para magnitudes grandes; decimales para las
    magnitudes por acción (EPS), que en `,.0f` perderían la información."""
    if abs(valor) >= 1000:
        return f"{valor:,.0f}"
    return f"{valor:,.2f}"


@tool
def list_available() -> str:
    """Devuelve qué compañías, ejercicios y secciones hay en el corpus.

    Úsala SIEMPRE antes de responder que un dato no existe, y antes de
    llamar a otras herramientas si no estás seguro de que la compañía o el
    ejercicio por los que te preguntan estén en el corpus. El corpus es
    limitado: si algo no aparece aquí, no está, y la respuesta correcta es
    decirlo (fuente 'ninguna'), no estimarlo.
    """
    por_ticker: dict[str, dict] = {}
    for s in datos.cargar_secciones():
        entrada = por_ticker.setdefault(
            s["ticker"],
            {"empresa": s["empresa"], "ejercicios": set(), "items": set()},
        )
        entrada["ejercicios"].add(int(s["fiscal_year"]))
        entrada["items"].add(s["item"])
    return "\n".join(
        f"{t} ({d['empresa']}): ejercicios {sorted(d['ejercicios'])}, "
        f"items {sorted(d['items'])}"
        for t, d in sorted(por_ticker.items())
    )


@tool
def get_xbrl_fact(ticker: str, fiscal_year: int, concept: str) -> str:
    """Devuelve el valor EXACTO de una magnitud financiera tal y como la
    compañía la reportó en XBRL. Es la fuente autorizada para cualquier
    cifra reportada: úsala SIEMPRE en lugar de leer un número del texto.

    Conceptos US-GAAP disponibles en este corpus: Revenues,
    RevenueFromContractWithCustomerExcludingAssessedTax, GrossProfit,
    OperatingIncomeLoss, NetIncomeLoss, EarningsPerShareBasic,
    EarningsPerShareDiluted, Assets, Liabilities, StockholdersEquity,
    CashAndCashEquivalentsAtCarryingValue,
    NetCashProvidedByUsedInOperatingActivities,
    ResearchAndDevelopmentExpense.

    OJO: el concepto varía por compañía. Para ingresos, NVIDIA y Alphabet
    usan 'Revenues'; Apple, Microsoft, Meta y Amazon usan
    'RevenueFromContractWithCustomerExcludingAssessedTax'. Si el concepto
    que pides no existe, la respuesta te dirá cuáles reportó esa compañía:
    elige de esa lista, no insistas con variantes inventadas. Y si la
    magnitud no está en XBRL (p. ej. capex, porcentajes de segmento,
    previsiones), no la estimes: búscala en el texto con search_filings y
    cita el fragmento, o responde que no está en el corpus.

    Args:
        ticker: Símbolo bursátil, p. ej. 'NVDA'.
        fiscal_year: Ejercicio fiscal reportado, p. ej. 2024.
        concept: Concepto US-GAAP exacto, p. ej. 'Revenues'.
    """
    xbrl = datos.cargar_xbrl()
    filas = xbrl[(xbrl.ticker == ticker)
                 & (xbrl.fiscal_year == int(fiscal_year))
                 & (xbrl.concept == concept)]
    if filas.empty:
        disponibles = sorted(
            xbrl[(xbrl.ticker == ticker)
                 & (xbrl.fiscal_year == int(fiscal_year))].concept.unique()
        )
        if not disponibles:
            return (f"No hay datos de {ticker} para FY{fiscal_year} en el "
                    f"corpus. Usa list_available para ver qué hay.")
        return (f"{ticker} no reportó '{concept}' en FY{fiscal_year}. "
                f"Conceptos disponibles: {', '.join(disponibles)}.")
    f = filas.iloc[0]
    return (f"{ticker} FY{fiscal_year} · {concept} = "
            f"{_formatear_valor(float(f.value))} {f.unit} "
            f"(cierre de ejercicio {f.period_end}, según el {f.form})")


@tool
def search_filings(query: str, ticker: str | None = None,
                   fiscal_year: int | None = None,
                   item: str | None = None, k: int = 5) -> str:
    """Busca fragmentos de texto relevantes en los informes 10-K del corpus.

    Úsala para preguntas cualitativas —riesgos, estrategia, litigios,
    comentarios de la dirección— y para magnitudes que SOLO existen en el
    texto y no en XBRL (porcentajes de segmento, previsiones/guidance,
    capex): en ese caso, cita el chunk_id del fragmento. NO la uses para
    cifras reportadas en XBRL: para eso está get_xbrl_fact, que es exacta.

    El corpus está EN INGLÉS: escribe la consulta en inglés, con el
    vocabulario del propio informe, aunque la pregunta llegue en español.
    Pasa los filtros siempre que la pregunta los mencione: sin ellos, los
    fragmentos más parecidos pueden ser de otra compañía u otro ejercicio.

    Args:
        query: Qué buscar, en lenguaje natural y en INGLÉS.
        ticker: Filtra por compañía si la pregunta la menciona.
        fiscal_year: Filtra por ejercicio si la pregunta lo menciona.
        item: Filtra por sección: '1A' riesgos, '7' MD&A,
            '7A' riesgo de mercado, '8' estados financieros.
        k: Número de fragmentos a devolver.

    Devuelve k fragmentos, cada uno con su chunk_id para poder citarlo.
    """
    return datos.formatear_fragmentos(
        retrieval.buscar_densa(query, ticker=ticker, fiscal_year=fiscal_year,
                               item=item, k=k)
    )


@tool
def read_section(ticker: str, fiscal_year: int, item: str) -> str:
    """Devuelve el TEXTO COMPLETO de una sección de un 10-K.

    Es una herramienta CARA: puede devolver decenas de miles de tokens.
    Úsala solo cuando search_filings devuelva fragmentos insuficientes y
    necesites el contexto entero de una sección concreta.

    Args:
        ticker: Símbolo bursátil, p. ej. 'META'.
        fiscal_year: Ejercicio fiscal, p. ej. 2025.
        item: '1A' riesgos, '7' MD&A, '7A' riesgo de mercado,
            '8' estados financieros.
    """
    for s in datos.cargar_secciones():
        if (s["ticker"] == ticker
                and int(s["fiscal_year"]) == int(fiscal_year)
                and s["item"] == item):
            return s["texto"]
    return (f"No hay Item {item} de {ticker} FY{fiscal_year} en el corpus. "
            f"Usa list_available para ver qué hay.")


# Lo que consume el agente (y, más adelante, el evaluador de trayectoria).
HERRAMIENTAS = [list_available, get_xbrl_fact, search_filings, read_section]
POR_NOMBRE = {t.name: t for t in HERRAMIENTAS}
