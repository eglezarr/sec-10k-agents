# Revisión del golden set propio — borrador

28 candidatas (9 numéricas · 12 extractivas · 7 comparativas) para
quedarnos con **20 (7 / 7 / 6)**. Todas nacen verificadas contra el
corpus: cifra = parquet exacto, ancla literal con tramo carácter a
carácter, chunk localizado. Tu trabajo es de analista, no de técnico:

- **Descarta** 2 numéricas, 5 extractivas y 1 comparativa.
- **Reformula** libremente `pregunta` y `respuesta_esperada` (tu voz).
- **NO toques** ancla_texto, ancla_inicio/fin, chunk_id ni cifras sin
  avisarme: romperías la verificación (si quieres otro ancla, dime el
  tema y te lo extraigo verificado).
- Si quieres proponer 2-3 preguntas tuyas, adelante: dímelas y las
  anclo yo al corpus.

## Numéricas (9 → elige 7)

**pr-n01** · MSFT FY2024 · OperatingIncomeLoss
- P: ¿Cuál fue el resultado operativo de Microsoft en el ejercicio fiscal 2024?
- R: Microsoft reportó resultado operativo de 109.433 M USD en FY2024 (cierre 2024-06-30).

**pr-n02** · AAPL FY2025 · NetIncomeLoss
- P: ¿Cuál fue el beneficio neto de Apple en el ejercicio fiscal 2025?
- R: Apple reportó beneficio neto de 112.010 M USD en FY2025 (cierre 2025-09-27).

**pr-n03** · NVDA FY2024 · ResearchAndDevelopmentExpense
- P: ¿Cuál fue el gasto en I+D de NVIDIA en el ejercicio fiscal 2024?
- R: NVIDIA reportó gasto en I+D de 8.675 M USD en FY2024 (cierre 2024-01-28).
- Nota: FY2024 de NVIDIA cierra en enero de 2024: buen test de calendario fiscal

**pr-n04** · GOOGL FY2024 · Assets
- P: ¿Cuál fue el activos totales de Alphabet en el ejercicio fiscal 2024?
- R: Alphabet reportó activos totales de 450.256 M USD en FY2024 (cierre 2024-12-31).

**pr-n05** · AMZN FY2024 · EarningsPerShareDiluted
- P: ¿Cuál fue el beneficio por acción diluido de Amazon en el ejercicio fiscal 2024?
- R: Amazon reportó beneficio por acción diluido de 5.53 USD por acción en FY2024 (cierre 2024-12-31).
- Nota: única con decimales: vigila el formato del EPS de punta a punta

**pr-n06** · META FY2025 · CashAndCashEquivalentsAtCarryingValue
- P: ¿Cuánta caja y equivalentes de efectivo tenía Meta al cierre de FY2025?
- R: Meta reportó caja y equivalentes de efectivo de 35.873 M USD en FY2025 (cierre 2025-12-31).

**pr-n07** · AAPL FY2024 · StockholdersEquity
- P: ¿Cuál fue el patrimonio neto de Apple en el ejercicio fiscal 2024?
- R: Apple reportó patrimonio neto de 56.950 M USD en FY2024 (cierre 2024-09-28).
- Nota: patrimonio 'pequeño' por las recompras: cifra contraintuitiva a propósito

**pr-n08** · NVDA FY2024 · NetIncomeLoss
- P: ¿Cuál fue el beneficio neto de NVIDIA en el ejercicio fiscal 2024?
- R: NVIDIA reportó beneficio neto de 29.760 M USD en FY2024 (cierre 2024-01-28).
- Nota: el FY pre-boom: contrasta con el FY2025 que pregunta el oficial

**pr-n09** · GOOGL FY2025 · NetCashProvidedByUsedInOperatingActivities
- P: ¿Cuál fue el flujo de caja de operaciones de Alphabet en el ejercicio fiscal 2025?
- R: Alphabet reportó flujo de caja de operaciones de 164.713 M USD en FY2025 (cierre 2025-12-31).

## Extractivas (12 → elige 7)

**pr-e01** · AAPL FY2025 · Item 1A
- P: ¿Qué advierte Apple en el Item 1A de FY2025 sobre los aranceles y otras restricciones al comercio internacional?
- R: Que las restricciones al comercio internacional, como aranceles y controles a importaciones o exportaciones de bienes, tecnología o datos, pueden afectar material y adversamente a su negocio y su cadena de suministro.
- Ancla (29 palabras, AAPL-2025-1A-0002): «Restrictions on international trade, such as tariffs and other controls on imports or exports of goods, technology or data, can ma…»

**pr-e02** · AAPL FY2025 · Item 1A
- P: ¿Qué riesgo señala Apple sobre su dependencia de socios externos de fabricación y logística?
- R: Que depende de la fabricación de componentes y productos y de servicios logísticos de socios de outsourcing, muchos de ellos fuera de EE. UU.
- Ancla (24 palabras, AAPL-2025-1A-0007): «The Company depends on component and product manufacturing and logistical services provided by outsourcing partners, many of which…»

**pr-e03** · AAPL FY2025 · Item 7A
- P: ¿Por qué puede Apple optar por no cubrir ciertas exposiciones de tipo de cambio, según su Item 7A de FY2025?
- R: Porque puede decidir no cubrir determinadas exposiciones por consideraciones contables o por un coste prohibitivo.
- Ancla (23 palabras, AAPL-2025-7A-0001): «However, the Company may choose to not hedge certain foreign currency exposures for a variety of reasons, including accounting con…»
- Nota: matiz de tesorería: cobertura selectiva, no total

**pr-e04** · NVDA FY2025 · Item 1A
- P: ¿Qué compromisos ha asumido NVIDIA para asegurar suministro y capacidad, y con qué efecto en costes?
- R: Ha pagado primas, entregado depósitos y firmado acuerdos de suministro y compromisos de capacidad a largo plazo, lo que ha elevado sus costes de producto y puede seguir haciéndolo.
- Ancla (31 palabras, NVDA-2025-1A-0004): «To secure future supply and capacity, we have paid premiums, provided deposits, and entered into long-term supply agreements and c…»

**pr-e05** · NVDA FY2025 · Item 1A
- P: ¿Qué riesgo describe NVIDIA si estima mal la demanda o sus clientes cambian sus pedidos?
- R: Que, como le ha ocurrido en el pasado, podría no poder reducir sus compromisos de suministro a tiempo, al mismo ritmo o en absoluto.
- Ancla (36 palabras, NVDA-2025-1A-0004): «If we inaccurately estimate demand, or our customers change orders, as we have experienced in the past, we may not be able to redu…»
- Nota: 36 palabras: cerca del límite de 40

**pr-e06** · MSFT FY2025 · Item 1A
- P: ¿Qué dice Microsoft en FY2025 sobre la expansión de sus datacenters y su capacidad de servidores?
- R: Que sigue identificando y evaluando oportunidades para ampliar ubicaciones de datacenters y aumentar la capacidad de servidores para atender la demanda creciente de sus clientes.
- Ancla (33 palabras, MSFT-2025-1A-0018): «We continue to identify and evaluate opportunities to expand our datacenter locations and increase our server capacity to meet the…»

**pr-e07** · MSFT FY2025 · Item 1A
- P: ¿Qué limitación reconoce Microsoft sobre sus políticas y controles internos de seguridad?
- R: Que sus políticas y controles internos de seguridad pueden no seguir el ritmo de las nuevas amenazas ni de la regulación emergente de ciberseguridad en el mundo.
- Ancla (26 palabras, MSFT-2025-1A-0009): «Our business policies and internal security controls may not keep pace with these changes as new threats emerge or the emerging cy…»

**pr-e08** · GOOGL FY2025 · Item 1A
- P: ¿En qué situación está el procedimiento de remedios del caso antimonopolio de Alphabet, según su 10-K de FY2025?
- R: Un procedimiento separado para determinar los remedios, cuyo rango varía ampliamente, se celebró en septiembre de 2025 con propuestas divergentes de las partes.
- Ancla (24 palabras, GOOGL-2025-1A-0026): «A separate proceeding to determine remedies, the range of which varies widely, took place in September 2025 with the parties prese…»
- Nota: tema jugoso para la defensa: litigio vivo con fechas

**pr-e09** · GOOGL FY2025 · Item 7A
- P: ¿Qué movimiento adverso de los tipos de cambio considera Alphabet razonablemente posible en su Item 7A?
- R: Considera razonablemente posible, a la vista de tendencias históricas, experimentar movimientos adversos del 10% en los tipos de cambio.
- Ancla (25 palabras, GOOGL-2025-7A-0000): «Considering historical trends in foreign exchange rates, we determined that it was reasonably possible that adverse changes in exc…»
- Nota: estilo 'sensibilidad/VaR': muy de tesorería

**pr-e10** · AMZN FY2025 · Item 7A
- P: ¿A qué se debe principalmente la exposición de Amazon al riesgo de tipos de interés?
- R: Principalmente a su cartera de inversiones y a su deuda.
- Ancla (19 palabras, AMZN-2025-7A-0001): «Our exposure to market risk for changes in interest rates relates primarily to our investment portfolio and our debt.»

**pr-e11** · AMZN FY2025 · Item 1A
- P: ¿Qué riesgo operativo señala Amazon respecto a los picos estacionales de demanda?
- R: Que podría no dotar de personal suficiente su red logística y de atención al cliente en los picos, y que transportistas y co-sourcers podrían no cubrir la demanda estacional.
- Ancla (38 palabras, AMZN-2025-1A-0006): «In addition, we may be unable to adequately staff our fulfillment network and customer service centers during these peak periods a…»
- Nota: 38 palabras: la más larga; el validador avisará

**pr-e12** · GOOGL FY2025 · Item 7
- P: ¿Qué explica el aumento de la pérdida operativa de Other Bets en 2025, según el MD&A de Alphabet?
- R: Principalmente el aumento de gastos de compensación, en gran parte por un cargo de compensación ligado a valoración relacionado con Waymo.
- Ancla (28 palabras, GOOGL-2025-7-0016): «The increase in operating loss was primarily driven by an increase in employee compensation expenses largely due to an increase in…»
- Nota: MD&A fuera del 1A: diversifica el item de búsqueda

## Comparativas (7 → elige 6)

**pr-c01** · NVDA FY2025 · Item 7 · OperatingIncomeLoss
- P: ¿Cómo varió el resultado operativo de NVIDIA entre FY2024 y FY2025, y qué lo impulsó según el MD&A?
- R: Pasó de 32.972 M USD en FY2024 a 81.453 M USD en FY2025 (+147.0%). Motor citado en el MD&A: el crecimiento de ingresos por las plataformas de data center para computación acelerada e IA.
- Ancla (21 palabras, NVDA-2025-7-0001): «Revenue growth in fiscal year 2025 was driven by data center compute and networking platforms for accelerated computing and AI sol…»
- Nota: la estrella: +147% con driver limpio

**pr-c02** · MSFT FY2025 · Item 7 · OperatingIncomeLoss
- P: ¿Cómo evolucionó el resultado operativo de Microsoft entre FY2024 y FY2025, y qué papel jugó Azure?
- R: Pasó de 109.433 M USD en FY2024 a 128.528 M USD en FY2025 (+17.4%). Motor citado en el MD&A: el crecimiento del 23% de Server products, con Azure y otros servicios cloud creciendo un 34%.
- Ancla (19 palabras, MSFT-2025-7-0001): «Server products and cloud services revenue increased 23% driven by Azure and other cloud services revenue growth of 34%.»

**pr-c03** · GOOGL FY2025 · Item 7 · OperatingIncomeLoss
- P: ¿Cómo varió el resultado operativo de Alphabet entre 2024 y 2025, y qué factores lo movieron?
- R: Pasó de 112.390 M USD en FY2024 a 129.039 M USD en FY2025 (+14.8%). Motor citado en el MD&A: más ingresos, parcialmente compensados por mayores costes de infraestructura técnica y de compensación.
- Ancla (27 palabras, GOOGL-2025-7-0016): «The increase in operating income was primarily driven by an increase in revenues, partially offset by increases in usage costs for…»

**pr-c04** · META FY2025 · Item 7 · OperatingIncomeLoss
- P: ¿Cómo cambió el resultado operativo de Meta entre 2024 y 2025, y qué papel jugaron las impresiones y el precio por anuncio?
- R: Pasó de 69.380 M USD en FY2024 a 83.276 M USD en FY2025 (+20.0%). Motor citado en el MD&A: impresiones +12% interanual y precio medio por anuncio +9%.
- Ancla (22 palabras, META-2025-7-0001): «Ad impressions delivered across our Family of Apps in 2025 increased 12% year-over-year, and our average price per ad increased 9%…»
- Nota: driver con dos cifras verificables en el ancla

**pr-c05** · AMZN FY2025 · Item 7 · NetIncomeLoss
- P: ¿Cómo varió el beneficio neto de Amazon entre 2024 y 2025, y cómo se refleja en su flujo de caja operativo?
- R: Pasó de 59.248 M USD en FY2024 a 77.670 M USD en FY2025 (+31.1%). Motor citado en el MD&A: el propio MD&A liga la mejora del flujo operativo al aumento del beneficio neto y a cambios en el circulante.
- Ancla (30 palabras, AMZN-2025-7-0007): «The increase in operating cash flow in 2025, compared to the prior year, was due to an increase in net income (loss), excluding no…»
- Nota: ancla en la sección de cash flow: cruza dos métricas

**pr-c06** · AAPL FY2025 · Item 7 · NetIncomeLoss
- P: ¿Cómo evolucionó el beneficio neto de Apple entre FY2024 y FY2025, y qué papel jugaron los Servicios?
- R: Pasó de 93.736 M USD en FY2024 a 112.010 M USD en FY2025 (+19.5%). Motor citado en el MD&A: Servicios creció por publicidad, App Store y servicios cloud.
- Ancla (23 palabras, AAPL-2025-7-0003): «Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cl…»

**pr-c07** · GOOGL FY2025 · Item 7 · NetIncomeLoss
- P: ¿Cómo varió el beneficio neto de Alphabet entre 2024 y 2025, y qué factores cita el MD&A de Google Services?
- R: Pasó de 100.118 M USD en FY2024 a 132.170 M USD en FY2025 (+32.0%). Motor citado en el MD&A: más ingresos, compensados en parte por gastos legales, TAC y costes de adquisición de contenido.
- Ancla (31 palabras, GOOGL-2025-7-0016): «The increase in operating income was primarily driven by an increase in revenues, partially offset by an increase in expenses rela…»
- Nota: misma zona del MD&A que pr-c03: si entran las dos, retrieval fino

## Huecos (fichero aparte `golden/huecos_humo.jsonl`, NO entra en el golden)

5 preguntas sin respuesta en el corpus para ensayar el comportamiento
'fuente=ninguna' antes del día 24 (≥2 de las 10 ciegas serán así).
No pasan el validador a propósito: codifican huecos.