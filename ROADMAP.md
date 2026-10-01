# IntentLang: camino hacia un motor de análisis y traducción semántica

> Meta: acercarnos a un «Stockfish del significado»: un motor que explore interpretaciones y traducciones, evalúe sus diferencias, explique sus decisiones y se abstenga cuando la evidencia no alcance.
>
> Este documento describe trabajo futuro. Ningún milestone se considera implementado por aparecer aquí. Los umbrales son objetivos de ingeniería propuestos, no resultados medidos ni garantías universales.

Fecha: 2026-10-01. Base auditada: `fa9c50a19c33214c75c4f9f60a90a71d13d37744`.

Plan de arranque: [primer sprint de corrección semántica](docs/superpowers/plans/2026-10-01-semantic-trust-foundations.md).
Diseño de referencia: [DESIGN.md](DESIGN.md). Estado y uso actuales: [README.md](README.md).

## 1. Qué queremos construir

IntentLang debe ayudar a contestar cuatro preguntas diferentes:

1. **Interpretación:** ¿qué significados permite este texto dentro de este contexto?
2. **Traducción:** ¿qué expresiones del idioma destino conservan esos significados?
3. **Verificación:** ¿qué hechos, relaciones o condiciones cambió cada candidato?
4. **Compilación de intención:** si el usuario pidió una acción, ¿qué programa representa esa petición y qué permiso existe para ejecutarlo?

Una buena respuesta puede ser una traducción, varias alternativas, una pregunta de aclaración o una abstención. Una frase natural que suena bien no basta para acreditar equivalencia. Un identificador de WordNet tampoco acredita por sí solo la intención completa de una oración.

La ambición no es interpretar todo desde el primer día. Es construir un motor pequeño cuya corrección y cobertura podamos medir, y ampliar ese dominio sin perder lo que ya sabemos demostrar.

### Qué tomamos de Stockfish

| Idea del ajedrez | Aplicación útil en IntentLang |
|---|---|
| Representación de una posición | Grafo semántico con contexto, incertidumbre y procedencia |
| Generación de movimientos | Interpretaciones y realizaciones candidatas |
| Reglas de legalidad | Restricciones de significado, dominio y permisos |
| Evaluación | Diferencias semánticas, cobertura, naturalidad y coste, por separado |
| Búsqueda limitada | Exploración con presupuesto explícito y condición de parada |
| Variantes de análisis | Alternativas explicadas y rasgos que las distinguen |
| Pruebas y partidas de evaluación | Corpus independiente, contrastes y evaluación humana |

La diferencia decisiva: el ajedrez tiene reglas cerradas; el lenguaje depende del contexto y puede ser ambiguo. No copiamos minimax como si una traducción fuera una partida adversarial. Tampoco tratamos una puntuación como prueba de verdad. Cada certificado debe declarar el dominio, las reglas y los supuestos bajo los que vale.

## 2. Punto de partida: evidencia y deuda

### Lo que ya existe y conviene conservar

- Separación entre `Meaning IR` descriptiva, `Intent IR` y `Program IR`.
- Representación explícita de predicado, participantes, polaridad, tiempo, aspecto y modalidad.
- Procedencia de las interpretaciones y modo de resolución.
- Léxico multilingüe con identificadores ILI y primitivas auditables.
- Parser y realizador deterministas para un corpus controlado.
- Comparador de candidatos y varios verificadores especializados.
- Infraestructura de tests, compilación de paquete y oráculo LLM opcional.

En el entorno preparado se ejecutó una suite de **216 casos: 208 aprobados y 8 omitidos**; los omitidos requieren `javac` o `cobc`. Lint, MyPy, build, CLI y solicitudes reales a la consola web pasaron. Esto acredita esos checks sobre esa revisión, no corrección general del significado.

El corpus de 100 registros contiene 400 variantes lingüísticas. En la auditoría, las variantes inglesas produjeron **20 claves semánticas distintas, incluyendo UNKNOWN**. Contar filas, idiomas, construcciones y significados únicos responde a preguntas diferentes; los reportes deben mostrar esas diferencias.

### Contraejemplos reproducidos

| Componente | Entrada o contraste | Resultado observado | Riesgo |
|---|---|---|---|
| Resolutor ejecutable | `no borres el archivo` | `RESOLVED`, primitiva `REMOVE`; lowering permitido | Prohibición convertida en intención ejecutable |
| Resolutor ejecutable | `si falla, borra el archivo` | `RESOLVED / REMOVE` sin conservar la condición | Acción condicional convertida en incondicional |
| Meaning parser + comparador | `Alice saw the rabbit` / `The rabbit saw Alice` | Misma clave, candidato aceptado | Intercambio de agente y objeto |
| Meaning parser + comparador | `Alice saw the rabbit` / `Alice never saw the rabbit` | Misma clave, candidato aceptado | Negación perdida |
| Meaning parser + comparador | `Alice pushed the rabbit` / `Alice was pushed by the rabbit` | Misma clave, candidato aceptado | Voz pasiva mal interpretada |
| Meaning parser + comparador | `Alice is opening the door` / `Bob is opening the window` | Misma clave, candidato aceptado | Participantes y objeto inventados por una regla |
| Meaning parser + comparador | `Alice saw the rabbit and then died` | Equivalente a la oración sin la muerte | Contenido adicional ignorado |
| Meaning parser + comparador | `Alice must leave` / `Alice must not leave` | Misma clave, candidato aceptado | Obligación confundida con prohibición |
| Identidad de Meaning IR | Dos conejos blanco/negro intercambian agente y objeto | Misma clave | Pérdida del vínculo entre rol y atributos de entidad |
| Realizador | IR negativa de apertura progresiva | `Alice is opening the door` | Salida afirmativa para un significado negativo |
| Verificador de frases | `The rabbit took a watch` / `Alice took a watch` | `VERIFIED` | Agente no comprobado |
| Verificador de interfaces | `Delete the file` / `Conserva el archivo` | Un caso aprobado; hashes diferentes | Omisión de comparación semántica del destino |

Los siete contrastes dirigidos del comparador fallaron; **no constituyen una estimación de tasa de error en texto real**. Son contraejemplos que invalidan garantías demasiado amplias. La prueba de interfaces usó JSON en memoria con las funciones reales; no dependió de un servicio externo.

## 3. Reglas que gobiernan todo el roadmap

1. **Desconocido no significa equivalente.** Falta de evidencia produce abstención o revisión.
2. **No perder contenido silenciosamente.** Lo no interpretado se conserva como cobertura pendiente.
3. **No convertir descripción en autorización.** Una oración narrativa, citada o hipotética no es una orden.
4. **No usar la misma ceguera como prueba.** Parser y realizador compartidos pueden confirmar mutuamente un error.
5. **No confundir cobertura con precisión.** Un sistema que se abstiene siempre puede evitar falsos positivos y no ser útil.
6. **Las métricas llevan denominador, versión y alcance.** Nunca publicar «100%» sin explicar de qué.
7. **La ambigüedad se conserva hasta resolverla.** Se puede preguntar; no se elige el primer sentido y se lo llama certeza.
8. **El oráculo propone o aporta evidencia.** Su respuesta no sustituye contratos, pruebas o permisos.
9. **Equivalencia, implicación y contradicción son relaciones distintas.** «Algunos» y «todos» no son intercambiables.
10. **Una traducción acreditada no acredita una ejecución.** El ejecutor tiene su propia frontera de permisos.
11. **La procedencia debe permitir repetir el resultado.** Un hash sin versión de reglas, recursos y contexto es insuficiente.
12. **Cada ampliación debe pagar su prueba.** Más idiomas o construcciones necesitan ejemplos positivos, negativos y de abstención.

## 4. Arquitectura objetivo

```text
Texto + idioma + contexto explícito
                 |
         análisis con cobertura
                 |
    alternativas de Meaning IR / grafo
                 |
       validación y desambiguación
                 |
        significado(s) sustentado(s)
                 |
      generación de candidatos destino
                 |
   filtros semánticos + evaluadores independientes
                 |
    búsqueda con presupuesto + comparación
                 |
 traducción / alternativas / aclaración / abstención
                 |
        evidencia y diferencias legibles

Ruta opcional de órdenes:
significado de orden + contexto de dominio
                 |
         Intent IR validada
                 |
        Program IR + efecto previsto
                 |
       permiso explícito de ejecución
                 |
               ejecutor
```

Las interfaces siguientes son **contratos propuestos para milestones futuros**. No son APIs ya disponibles. Sus nombres finales se fijarán en el plan detallado de cada milestone, antes de implementar consumidores.

- `analyze(text, language, context) -> AnalysisResult`: alternativas, estado, spans consumidos, contenido pendiente y procedencia.
- `validate_meaning_graph(graph) -> ValidationResult`: integridad de referencias, roles y rasgos.
- `canonicalize(graph) -> CanonicalMeaning`: identidad independiente de nombres internos, preservando enlaces.
- `compare_meanings(source, target, policy) -> ComparisonResult`: relación y diferencias, con desconocidos explícitos.
- `generate_candidates(meaning, language, context, budget) -> CandidateBatch`: realizaciones y procedencia.
- `evaluate_candidate(source_analysis, candidate, evaluators) -> CandidateEvaluation`: restricciones y evidencias separadas.
- `search_translation(request, budget) -> SearchResult`: candidatas, alternativas, motivo de parada y costes.
- `compile_intent(analysis, domain) -> CompilationResult`: programa o rechazo; nunca ejecución implícita.

Se puede empezar usando los dataclasses existentes. No hace falta crear un framework de plugins o reescribir toda la biblioteca para cumplir los primeros gates.

## 5. Milestones y dependencias

Se usa el prefijo **R** para no confundir este roadmap con los M0–M7 que ya aparecen en los experimentos del repositorio. Todos los R están pendientes al escribir este documento. La ruta específica de traducción de texto usa **T** y aparece después de R12.

| Milestone | Entregable | Depende de | Gate principal |
|---|---|---|---|
| R0 | Evidencia y benchmark honesto | — | Contraejemplos reproducibles y denominadores explícitos |
| R1 | Interpretación y lowering conservadores | R0 | Ninguna prohibición, cita o condición omitida habilita acción |
| R2 | Identidad semántica estructural | R0 | Renombrar IDs conserva identidad; cambiar relaciones la altera |
| R3 | Veredicto uniforme y realizador fiel | R1, R2 | Ningún significado incompleto obtiene equivalencia acreditada |
| R4 | Corpus independiente y evaluación por fenómenos | R0; gate completo tras R3 | Falsos positivos y cobertura medidos sobre holdout |
| R5 | Gramática composicional de dominio limitado | R1–R4 | Generalización a entidades y combinaciones no vistas |
| R6 | Contexto, ambigüedad y actos de habla | R5 | Alternativas o aclaración cuando faltan referentes o alcance |
| R7 | Generación y búsqueda de traducciones | R3–R6 | Mejor calidad dentro del presupuesto sin más falsos positivos |
| R8 | Evaluación independiente y oráculos | R3, R4; integración en R7 | Desacuerdo registrado; abstención cuando no hay evidencia |
| R9 | Compilación humano→máquina con permisos | R1, R2, R6 | Fidelidad de efectos y permisos comprobados por separado |
| R10 | Expansión multilingüe y equivalencia tipada | R4–R8 | Gates por par de idiomas y fenómeno |
| R11 | Análisis de documentos y experiencia de revisión | R6–R10 | Referencias, segmentos y diferencias auditables |
| R12 | Robustez, rendimiento y entrega reproducible | Transversal; cierre tras R11 | Límites operativos y evidencia reproducida en entorno limpio |

No iniciar R7 para compensar un R3 débil: buscar más candidatos con un evaluador incorrecto produce más formas de equivocarse.

## 6. R0 — Congelar la evidencia y corregir la interpretación de las métricas

**Resultado:** una persona ajena al proyecto puede reproducir la auditoría y distinguir fallos de infraestructura de errores semánticos.

**Archivos existentes:** `ci/run_semantic_benchmark.py`, `corpus/semantic/meaning_m1.jsonl`, `.github/workflows/ci.yml`, `README.md`.
**Archivos propuestos:** `corpus/semantic/adversarial_regressions.jsonl`, `ci/run_adversarial_benchmark.py`, `tests/test_adversarial_benchmark.py`, `docs/evaluation.md`.

- [ ] Registrar los contraejemplos de esta auditoría con IDs estables y comportamiento esperado.
- [ ] Añadir controles positivos vecinos: no arreglar una negación haciendo que toda oración se vuelva UNKNOWN.
- [ ] Definir categorías `false_accept`, `false_reject`, `abstain`, `infrastructure_error` y `invalid_fixture`.
- [ ] Separar conteo de registros, variantes, construcciones, predicados y claves canónicas únicas.
- [ ] Hacer que el runner de aceptación salga distinto de cero ante falsos positivos críticos, datos inválidos o fallos de infraestructura.
- [ ] Mantener el informe incluso cuando el gate falla; registrar commit, comando, duración y recursos.
- [ ] Explicar en README el dominio controlado del experimento y el significado de sus cuatro UNKNOWN.
- [ ] Separar la evidencia del benchmark M0 de intención del benchmark de Meaning IR: hoy no son el mismo recorrido.

**Gate:** antes de arreglar producción, el runner debe detectar los fallos actuales; su exit code no puede ser verde si no ejecutó casos. Un reporte recién generado debe identificar explícitamente su revisión y datos de entrada. No incorporar estos fallos como «expected failures» permanentes para esconder deuda.

## 7. R1 — Dejar de resolver lo que no se interpretó

**Resultado:** `RESOLVED` significa una interpretación sustentada dentro de una gramática declarada.

**Archivos:** `src/intentlang/meaning_parser.py`, `src/intentlang/resolve.py`, `src/intentlang/lowering.py`, `src/intentlang/ir.py`; tests específicos de parser, resolver y lowering.

- [ ] Detectar prohibiciones, negación y alcance antes de convertir una superficie en intención ejecutable.
- [ ] Rechazar para ejecución condiciones sin representar, discurso citado y órdenes descritas por terceros.
- [ ] Eliminar participantes fijos inferidos solo por aparecer un fragmento verbal.
- [ ] Interpretar sujeto y objeto de los patrones soportados; distinguir activa y pasiva.
- [ ] Registrar cobertura: spans interpretados, conectores, cláusulas y residuos semánticos.
- [ ] Evitar que la primera regla que hace match oculte una segunda cláusula o interpretación incompatible.
- [ ] Mantener el texto original y la causa de abstención en la procedencia.
- [ ] En modo assisted, una propuesta validada léxicamente debe volver a pasar los controles de la superficie original.

**Casos obligatorios:** negación normal y con `never`; `must` frente a `must not`; sujeto distinto; objeto distinto; voz pasiva; cláusula añadida; condicional; cita; imperativo directo positivo.

**Gate:** cero falsos positivos en los contraejemplos registrados. Una construcción todavía no soportada puede dar UNKNOWN/AMBIGUOUS/INCOMPLETE; no puede dar RESOLVED con contenido relevante perdido. Los controles positivos soportados deben seguir pasando. Este gate acredita el conjunto probado, no cualquier oración imaginable.

**Entrega inicial pequeña:** bloquear conservadoramente los casos ejecutables ya reproducidos y hacer visible la limitación. **Entrega posterior:** sustituir bloqueos por interpretación estructural cuando la gramática la soporte. Una lista de palabras prohibidas no es la solución final.

## 8. R2 — Meaning IR como grafo, no como bolsa de conceptos

**Resultado:** una identidad semántica que preserve quién participa, con qué atributos y en qué relación.

**Archivos:** `src/intentlang/meaning_ir.py`, `src/intentlang/semantic_comparator.py`; propuesta `src/intentlang/meaning_validation.py`; `tests/test_meaning_ir.py` y pruebas de canonicalización.

- [ ] Validar IDs únicos, referencias existentes, nombres de rol permitidos y tipos de rasgos.
- [ ] Diferenciar dos entidades del mismo concepto; preservar identidad y correferencia.
- [ ] Definir canonicalización por estructura del grafo, independiente de IDs locales.
- [ ] Conservar el enlace entre cada rol y los atributos de su entidad.
- [ ] Diferenciar autocausación/reflexividad de dos participantes independientes.
- [ ] Modelar eventos separados y relaciones entre eventos antes de aceptar oraciones compuestas.
- [ ] Declarar dónde se aplican negación, cuantificadores y modalidad; evitar un único flag global para varias cláusulas.
- [ ] Decidir una migración versionada de `meaning/1` si cambia la identidad o el significado de campos existentes.

**Propiedades de aceptación:** permutar el orden de serialización o renombrar IDs no cambia el significado; intercambiar conejo blanco y negro como agente sí lo cambia; cambiar «dos» por «tres» sí lo cambia; reflexivo y transitivo no colapsan; referencias rotas fallan en validación.

**Gate:** fixtures positivos y negativos, pruebas metamórficas y datos antiguos migrados explícitamente. No cambiar solo `key()` sin revisar cachés, corpus, hashes, realizer y comparadores que consumen esa identidad.

## 9. R3 — Un contrato de verificación y una realización que conserve rasgos

**Resultado:** las distintas rutas explican la misma clase de garantía y dejan de aprobar ausencia de evidencia.

**Archivos:** `semantic_comparator.py`, `meaning_realizer.py`, `translation_engine/roundtrip_verifier.py`, `translation_engine/semantic_phrase/verifier.py`, `translation_engine/harness.py`; nueva especificación `docs/verification-contract.md`.

- [ ] Definir relaciones `EQUIVALENT`, `CONTRADICTS`, `SOURCE_ENTAILS_TARGET`, `TARGET_ENTAILS_SOURCE`, `DIFFERENT` y `UNDETERMINED` con alcance explícito.
- [ ] Reservar equivalencia acreditada para el dominio y rasgos efectivamente comprobados.
- [ ] Tratar campos requeridos desconocidos como incertidumbre; nunca aprobarlos por ser `None` en ambos lados.
- [ ] Reconstruir semántica del texto destino en la ruta de interfaces; no heredar la del origen ni inferirla únicamente de la misma clave JSON.
- [ ] Dar a placeholders, marcas y estructura su propia categoría de validación: preservarlos no acredita significado.
- [ ] Comparar contenido añadido y omitido, no solo rasgos compartidos.
- [ ] Contar mensajes fallidos por separado de diferencias encontradas; tres diferencias en un mensaje no son tres mensajes fallidos.
- [ ] Evitar gates verdes con cero casos comprobados; excluir passthrough con explicación y denominador visible.
- [ ] Hacer que el realizador represente polaridad, tiempo, aspecto, modalidad y atributos requeridos, o devuelva una abstención.
- [ ] Admitir `VERIFIED_WITH_LIMITATIONS` solo con límites concretos; no presentarlo como equivalencia completa.

**Gate:** `Delete the file` → `Conserva el archivo` debe fallar por cambio de acción; una IR negativa no puede generar afirmación; pérdida de agente, cantidad, condición o referencia debe producir una diferencia o `UNDETERMINED`. Los reportes de todas las rutas deben distinguir checks estructurales de checks semánticos.

## 10. R4 — Benchmark independiente que pueda decirnos «no»

**Resultado:** medir generalización, utilidad y errores aceptados fuera de los ejemplos usados para escribir reglas.

**Estructura propuesta:** `corpus/semantic/train/`, `dev/`, `holdout/`, `contrastive/`; un manifiesto versionado de particiones y licencias. Son rutas futuras, no carpetas existentes.

- [ ] Crear particiones por familia de construcción, plantilla, entidades y fuente documental, evitando variantes casi idénticas entre particiones.
- [ ] Mantener el holdout fuera del ciclo de ajuste; tras usar un caso para depurar, pasa a regresión y se renueva la evaluación independiente.
- [ ] Anotar significado esperado, relación entre pares, fenómenos, contexto necesario y abstención permitida.
- [ ] Incluir dos anotadores independientes en una muestra crítica y adjudicar desacuerdos.
- [ ] Añadir pares mínimos de agente, paciente, polaridad, modalidad, cantidad, condición, tiempo y referencia.
- [ ] Añadir transformaciones válidas: sinónimos, activa/pasiva equivalente, cambios de orden permitidos y renombrado de entidades.
- [ ] Evaluar tanto traducciones buenas como malas; no construir un benchmark solo de errores fáciles.
- [ ] Comparar con baselines reproducibles: igualdad superficial, parser actual y un traductor externo congelado cuando exista acceso autorizado.
- [ ] Reportar por idioma, par de idiomas, dominio y fenómeno, además de agregado.

**Escala propuesta:** primer conjunto independiente de 200 pares en inglés/español, de los cuales al menos 100 cambian significado; siguiente conjunto de 1.000 pares repartidos por fenómenos. El tamaño no reemplaza diversidad ni revisión de etiquetas. Un milestone puede ajustar esta escala con un ADR que explique recursos y diseño estadístico.

**Gate:** cero errores aceptados en la regresión crítica; tasas y cobertura publicadas en holdout sin atribuirles garantías universales. El objetivo inicial de producto es un dominio delimitado donde el coste de abstenerse sea aceptable. La tasa máxima admisible de falsos positivos debe elegirse por uso: una recomendación editorial y una acción destructiva no tienen el mismo umbral.

## 11. R5 — Gramática composicional para un mundo pequeño pero real

**Resultado:** interpretar entidades y combinaciones nuevas sin añadir una plantilla completa por cada frase.

**Punto de partida:** eventos simples inglés/español; japonés/chino conservan su soporte experimental hasta pasar sus propios gates. Elegir el par inicial reduce la superficie de validación, no invalida el objetivo multilingüe.

- [ ] Declarar una gramática de dominio con patrones de oración, roles y rasgos soportados.
- [ ] Separar segmentación, análisis sintáctico, resolución léxica y construcción de IR.
- [ ] Mantener múltiples sentidos cuando el contexto no elige uno; el primer synset no es una prueba.
- [ ] Aceptar nombres y objetos nuevos mediante entidades parametrizadas, sin convertirlos automáticamente en Alice/conejo/puerta.
- [ ] Soportar activa/pasiva, negación y cuantificación dentro de ese dominio.
- [ ] Representar oraciones coordinadas como varios eventos; rechazar subordinación fuera de alcance.
- [ ] Medir generalización con combinaciones y entidades ausentes de train/dev.
- [ ] Decidir si usar parser externo mediante un ADR: licencia, versiones, tamaño, calidad por idioma y comportamiento sin red.

**Gate:** los nuevos ejemplos no requieren editar una tabla de frases completas; los contraejemplos de R1 siguen pasando; texto fuera de gramática conserva residuo y se abstiene. No prometer semántica abierta porque se añadió una librería de parsing.

## 12. R6 — Contexto, ambigüedad y preguntas útiles

**Resultado:** preservar incertidumbre y aclarar lo necesario en vez de inventar referentes o permisos.

**Contexto propuesto:** entidades mencionadas, dominio, glosario, hablante, destinatario, referentes, restricciones de estilo y política de ejecución. Contexto ausente se declara ausente; no se rellena con supuestos invisibles.

- [ ] Distinguir orden, afirmación, pregunta, cita, hipótesis y prohibición.
- [ ] Resolver pronombres con alternativas cuando haya varios referentes compatibles.
- [ ] Representar posesión, correferencia y alcance de negación/cuantiﬁcación.
- [ ] Mantener alternativas para palabras polisémicas y estructuras ambiguas.
- [ ] Generar una pregunta cuando su respuesta cambie significado, traducción o efectos previstos.
- [ ] Guardar qué aclaración humana resolvió qué alternativa y con qué alcance temporal.
- [ ] Invalidar decisiones si cambia el contexto del que dependían.

**Casos obligatorios:** «él la vio» sin referente; dos conejos y «su reloj»; «no todos» frente a «ninguno»; «puede» como capacidad frente a permiso; una orden dentro de una cita; «copia ese archivo» con dos archivos compatibles.

**Gate:** ninguna resolución de referente sin evidencia; una aclaración resuelve solo las alternativas pertinentes. El mismo texto con contextos distintos puede producir significados distintos, y ambos resultados deben explicar por qué.

## 13. R7 — Búsqueda de traducciones: la parte más parecida al motor de ajedrez

**Resultado:** explorar realizaciones candidatas y justificar la selección bajo un presupuesto.

**Archivos propuestos:** `translation_engine/search.py`, `candidate_generation.py`, `candidate_evaluation.py`; reportes de búsqueda separados de los verdicts.

- [ ] Generar varias realizaciones a partir de un significado sustentado, con paráfrasis y restricciones de estilo.
- [ ] Separar generación de candidatos de su aceptación; un generador nunca se verifica a sí mismo por decreto.
- [ ] Aplicar restricciones semánticas duras antes de ordenar por naturalidad o coste.
- [ ] Mantener un frente de alternativas cuando distintas candidatas tengan ventajas incomparables.
- [ ] Definir presupuestos `max_candidates`, `max_depth`, `timeout_ms`, `max_model_calls` y límites de memoria.
- [ ] Registrar motivo de parada: solución acreditada, presupuesto, timeout, incertidumbre o ausencia de candidatos.
- [ ] Añadir deduplicación y caché por significado, idioma, contexto, versiones y política.
- [ ] Medir si beam search o best-first mejoran frente a generación de un solo candidato; elegir por evidencia.
- [ ] Permitir salida «no encontré una traducción acreditada dentro del presupuesto».

**Evaluación separada:** equivalencia/cobertura, fluidez, terminología, estilo y recursos consumidos. La fluidez no puede compensar una negación invertida mediante una media ponderada.

**Gate:** comparar búsqueda y baseline con el mismo corpus y presupuesto declarado. La búsqueda debe mejorar una métrica útil sin aumentar falsos positivos críticos. Agotar el presupuesto no cambia `UNDETERMINED` a `EQUIVALENT`.

## 14. R8 — Evaluación independiente y LLM como testigo falible

**Resultado:** combinar evidencias que no dependan todas del mismo error del parser.

**Archivos:** `src/intentlang/llm_oracle.py`, tests de oráculo y sanitización; propuesta `translation_engine/evidence.py`.

- [ ] Añadir evaluadores independientes por función: roles, negación, números, términos y contenido pendiente.
- [ ] Mantener la back-translation como evidencia auxiliar; registrar errores compartidos y desacuerdos.
- [ ] Versionar prompts, proveedor, modelo, respuesta, política y parseo del veredicto.
- [ ] Tratar texto origen y candidato como datos no confiables; probar instrucciones incrustadas que intenten manipular al juez.
- [ ] Restringir salida del oráculo a un esquema; manejar respuesta incompleta, errores, timeout y JSON inválido.
- [ ] Evitar que la confianza declarada por un modelo se presente como probabilidad calibrada.
- [ ] Evaluar utilidad marginal: cuánto error detecta el oráculo que los checks locales no detectan, y cuánto añade.
- [ ] Mantener ejecución offline sin oráculo y escribir explícitamente la degradación.
- [ ] Usar credenciales y acceso externo solo cuando estén configurados; jamás grabar claves en fixtures, prompts o reportes.

**Gate:** un PASS del LLM no puede anular una contradicción estructural conocida. Desacuerdo o fallo de un requisito producen revisión/abstención. Dos evaluadores basados en el mismo modelo no se consideran automáticamente independientes.

## 15. R9 — Humano→máquina como compilación con contrato de efectos

**Resultado:** de una petición sustentada se obtiene un programa revisable; solo se ejecuta con autorización y límites propios.

**Archivos:** `lowering.py`, `program.py`, `complex_program.py`, `executor.py`, `capabilities.py`, `transaction.py`, `portable_codegen.py`; tests de efectos y aislamiento.

- [ ] Definir entidades de dominio para archivos, rutas, destinos y recursos; un concepto léxico FILE no identifica un archivo real.
- [ ] Conservar literales de rutas, nombres y argumentos; no usar su lema como sustituto del recurso solicitado.
- [ ] Representar condiciones, orden de pasos, repetición y fallos esperados en Program IR.
- [ ] Generar un plan de efectos: lectura, escritura, borrado, proceso, red y alcance exacto.
- [ ] Separar `can_interpret`, `can_compile` y `may_execute`; revisar usos actuales de `can_act()`.
- [ ] Exigir parámetros completos y recursos no ambiguos antes de compilar una capability.
- [ ] Aplicar permisos al ejecutor, aunque el caller entregue directamente una Program IR o invoque una capability.
- [ ] Mostrar dry-run sin efectos y confirmar acciones según la política del producto.
- [ ] Validar rollback y señalar efectos irreversibles; una transacción local no deshace arbitrariamente una llamada externa.
- [ ] Verificar codegen contra trazas de ejecución equivalentes en recursos temporales aislados.

**Gate:** prohibiciones, hipótesis, citas y condiciones no representadas nunca autorizan acciones. El programa preserva operandos, destinos y guardas. Los tests deben inspeccionar efectos reales en fixtures temporales; un string de código bien formado no acredita equivalencia de ejecución.

**Alcance inicial recomendado:** operaciones sobre archivos temporales dentro de un directorio explícito. Añadir procesos, red o credenciales como dominios distintos con gates propios.

## 16. R10 — Idiomas nuevos y relaciones semánticas que no siempre son equivalencia

**Resultado:** expandir cobertura sin ocultar asimetrías entre idiomas y léxicos.

- [ ] Publicar matriz por idioma/par: recursos, tokenizador, gramática, fenómenos, corpus y limitaciones.
- [ ] Resolver los casos conocidos de japonés/hebreo con anotación lingüística; no cambiar gold para hacerlos pasar.
- [ ] Mantener turco fuera de soporte acreditado mientras su WordNet sea un placeholder, o adoptar una fuente alternativa mediante ADR y pruebas.
- [ ] Revisar ILI y vocabulario de dominio donde los sustantivos no convergen entre WordNets.
- [ ] Modelar información opcional u obligatoria según idioma: género, evidencialidad, aspecto, sujetos omitidos y clasificadores.
- [ ] Distinguir pérdida de información, implicación, equivalencia y adición de información.
- [ ] Pedir contexto cuando el destino obliga a decidir un rasgo que el origen no especifica.
- [ ] Incorporar revisión humana por hablantes competentes en pares críticos.

**Gate:** cada idioma añadido presenta sus resultados propios; no hereda la precisión de inglés/español. Una traducción puede ser válida bajo supuestos declarados y seguir sin ser equivalencia estricta.

## 17. R11 — Documentos y consola de análisis semántico

**Resultado:** revisar textos largos sin perder referencias o esconder segmentos pendientes.

- [ ] Segmentar preservando posiciones, formato, IDs de párrafo y vínculos al documento original.
- [ ] Mantener entidades, correferencias, cronología y terminología entre segmentos.
- [ ] Detectar contradicciones o cambios acumulados que no aparecen al comprobar cada oración aislada.
- [ ] Mostrar original, candidato, interpretación, diferencias y cobertura pendiente.
- [ ] Presentar alternativas de análisis y la pregunta que resolvería cada ambigüedad.
- [ ] Permitir adjudicación humana con registro versionado, sin reescribir evidencia anterior.
- [ ] Exportar reportes JSON/Markdown con supuestos, versiones y estado por segmento.
- [ ] Dar a «parcialmente revisado» y «completamente acreditado dentro del dominio» estados visuales distintos.

**Gate:** un documento no obtiene resultado global verde si una cláusula crítica quedó sin revisar. El agregado debe conservar conteos de abstenciones y fallos; no promediar un cambio de negación hasta hacerlo desaparecer.

## 18. R12 — Robustez, rendimiento y entrega reproducible

**Resultado:** un motor usable con límites operativos y evidencia que otra máquina pueda repetir.

- [ ] Perfilar antes de optimizar: análisis, WordNet, canonicalización, búsqueda y oráculo por separado.
- [ ] Definir fixtures de rendimiento por tamaño y complejidad; reportar p50/p95, throughput y memoria pico.
- [ ] Fijar determinismo del modo local entre procesos con semillas, orden canónico y versiones de recursos.
- [ ] Invalidar cachés cuando cambian reglas, léxico, modelo, contexto o políticas.
- [ ] Probar concurrencia, cancelación, timeout y entradas que disparan explosión combinatoria.
- [ ] Hacer fuzzing de Unicode, puntuación, números, texto truncado, JSON/IR malformadas y profundidades excesivas.
- [ ] Preservar integridad, TLS, hashes y licencias de recursos descargados.
- [ ] Reproducir instalación y benchmark en un entorno limpio; comprobar que fallan claramente con recursos ausentes.
- [ ] Publicar un manifiesto por release: commit, IR, gramática, corpus, recursos, métricas y límites.

**Gate:** presupuestos cumplidos o interrupción explícita sin falso PASS. Ninguna omisión por falta de compilador se presenta como test aprobado. La versión debe declarar qué resultados se reprodujeron y cuáles dependen de proveedores externos.

## 19. Ruta T — Hacer crecer el motor que traduce texto humano→humano

Esta ruta es un objetivo de producto de primera clase. IntentLang debe **traducir texto**, además de analizarlo y comprobar candidatos. No requiere completar la compilación humano→máquina de R9.

### Motores existentes que vamos a aprovechar

| Pieza actual | Función | Límite que debe quedar visible |
|---|---|---|
| `meaning_realizer.py` | Meaning IR → superficie en inglés/español/japonés/chino | Construcciones y entidades controladas; algunos rasgos se pierden |
| `translation_engine/materializer.py` | Materialización de mensajes y locales UI | Diccionario corto; frases de hasta tres palabras por sustitución; textos largos quedan NEEDS_REVIEW |
| `translation_engine/context_resolver.py` | Enriquecimiento contextual de inventarios | Debe comprobarse que el materializador consume realmente ese enriquecimiento |
| `translation_engine/semantic_phrase/proposer.py` | Adaptador de propuestas y back-translation | Propuesta del modelo y prueba de fidelidad son resultados diferentes |
| `translation_engine/harness.py` y `cli.py` | Flujo de inventario, materialización y reporte | Un reporte verde no debe acreditar semántica que no se comprobó |

No eliminar estas piezas por ser pequeñas. Darles contratos claros, probar su comportamiento y conectarlas por interfaces explícitas. La traducción palabra por palabra puede servir para etiquetas aisladas; no debe presentarse como realización gramatical general.

### Contrato propuesto del traductor

```text
TranslationRequest
  text o document
  source_language explícito, o detección con incertidumbre
  target_language
  context + glossary + style
  budget + policy

TranslationResult
  source_text + source_analysis
  segments + candidate_text + alternatives
  status por segmento y estado global
  semantic_differences + protected_content_checks
  assumptions + unresolved_content
  generation_provenance + verification_provenance
  timing + costs + stop_reason
```

API propuesta: `translate_text(request: TranslationRequest) -> TranslationResult`. Se definirán los dataclasses concretos en el plan de T1; no están implementados por este roadmap.

Estados propuestos, separados del `status` actual de Meaning IR:

- `VERIFIED_TRANSLATION`: equivalencia acreditada dentro del dominio declarado.
- `PROPOSED_TRANSLATION`: existe un candidato, pero su equivalencia no está acreditada.
- `NEEDS_CONTEXT`: una decisión lingüística requiere aclaración.
- `PARTIAL_TRANSLATION`: algunos segmentos tienen salida y otros quedan pendientes.
- `UNSUPPORTED`: falta cobertura lingüística o de construcción.
- `FAILED`: un requisito técnico impide obtener un resultado.

El producto puede mostrar propuestas no verificadas cuando la política lo permita, siempre identificadas como tales. **No ejecutar, publicar automáticamente ni presentar como certificada una propuesta porque el texto resulte fluido.** La política de publicación corresponde a la aplicación consumidora; la biblioteca devuelve evidencia y estado.

### Milestones T y orden de integración

| Milestone | Entrega traductora | Dependencias y gate |
|---|---|---|
| T0 | Inventario verificable de capacidades del traductor actual | Puede empezar en R0; medir traducciones reales y fallbacks |
| T1 | API/CLI de traducción de oraciones | R1–R3, T0; candidato y veredicto separados |
| T2 | Realización composicional inglés↔español | R4–R6, T1; entidades y combinaciones nuevas |
| T3 | Glosarios, formato y localización UI | R3, T1; estructura y significado comprobados separadamente |
| T4 | Traducción con candidatos y búsqueda | R7–R8, T2; mejora bajo presupuesto igual |
| T5 | Párrafos y documentos con contexto | R6, R11, T3–T4; continuidad referencial y cobertura por segmento |
| T6 | Idiomas adicionales y evaluación externa | R10, T2–T5; evidencia por par y revisión humana |

Los T son entregas del traductor sobre los fundamentos R, no un segundo trabajo duplicado. Una tarea del realizer puede cerrar parte de R3 y de T2 a la vez si cumple ambos gates.

### T0 — Medir qué traduce hoy y qué deja pendiente

**Archivos:** `materializer.py`, `meaning_realizer.py`, `harness.py`, `tests/test_translation_engine.py`; propuesta `tests/test_translation_capabilities.py` y `docs/translation-support.md`.

- [ ] Construir fixtures de palabra aislada, frase breve, oración, lista de mensajes y párrafo.
- [ ] Registrar idiomas origen y destino; no dar por hecho que un diccionario inglés→destino es un traductor bidireccional.
- [ ] Medir si el parámetro `dictionary` se usa efectivamente y si el contexto cambia la elección de términos.
- [ ] Seguir el inventario enriquecido desde context resolver hasta materialización y verificación; una etapa declarada en el harness debe tener efecto comprobable.
- [ ] Diferenciar traducción completa, mezcla de idiomas, passthrough deliberado y texto sin traducir.
- [ ] No contar cualquier string diferente del origen como traducción exitosa.
- [ ] Etiquetar propuestas y `[NEEDS_REVIEW]` como pendientes; un prefijo no constituye traducción.

**Gate:** matriz reproducible de rutas y capacidades; un párrafo en inglés devuelto en inglés con prefijo no incrementa el conteo de traducciones completas. Toda afirmación de soporte incluye ejemplos reales y su verificación.

### T1 — Una entrada pública para traducir oraciones

**Archivos propuestos:** `translation_engine/translator.py`, `translation_engine/translation_result.py`, `tests/test_translate_text.py`. Modificar la CLI existente o añadir un subcomando documentado tras revisar compatibilidad.

- [ ] Definir request/result, estados y errores de la interfaz pública.
- [ ] Conectar análisis origen → generación → análisis destino → comparación; conservar los resultados intermedios.
- [ ] Traducir las construcciones sustentadas y abstenerse explícitamente de las demás.
- [ ] Ofrecer salida JSON y salida humana con candidato, diferencias y estado.
- [ ] Mantener separados errores de idioma, datos, recursos y falta de cobertura.
- [ ] Probar idioma origen explícito y rechazo de una selección incoherente; detección automática es una capacidad aparte.

**Gate:** una oración soportada se traduce realmente y obtiene evidencia; una no soportada devuelve estado informativo, sin una oración inventada marcada VERIFIED. Se comprueba la misma interfaz que usarán los consumidores, no solo helpers internos.

### T2 — Traducción composicional y bidireccional

- [ ] Desacoplar el realizer de IDs como `alice` o `rabbit`; consumir conceptos, rasgos y roles.
- [ ] Realizar concordancia, determinantes, conjugación, orden y preposiciones en cada idioma soportado.
- [ ] Conservar negación, cantidad, modalidad, agentes y objetos; no dejar que estilo sobrescriba significado.
- [ ] Comprobar inglés→español y español→inglés por separado. No inferir la segunda dirección a partir de la primera.
- [ ] Reconocer sinónimos y paráfrasis válidas mediante relaciones sustentadas, sin exigir una sola frase gold.
- [ ] Evaluar ejemplos nuevos con nombres, objetos y tiempos que no aparezcan juntos en train/dev.

**Gate:** holdout bilingüe anotado sin cambios críticos de significado, cobertura medida y revisión de naturalidad. Se publican abstenciones. Un round-trip correcto del mismo parser no basta: incorporar referencias y revisión independientes de R4/R8.

### T3 — Traducción que respeta el contenido y el archivo

- [ ] Dar al glosario precedencia explícita, sensible a dominio/sentido y con reporte de conflictos.
- [ ] Preservar placeholders con nombre, tipo, multiplicidad y relación semántica, no solo existencia.
- [ ] Conservar números, unidades, fechas, nombres propios, URLs y código según políticas por formato.
- [ ] Mantener estructura JSON, listas, whitespace significativo y Markdown; probar reensamblaje y escape.
- [ ] Elegir traducción distinta para homógrafos según contexto sustentado: por ejemplo, `file` sustantivo o verbo.
- [ ] Separar localización cultural o conversión de unidades de traducción estricta; requieren política explícita.
- [ ] Evitar que datos parcialmente traducidos se exporten como locales listos sin un estado/report separado.

**Gate:** equivalencia estructural del formato y fidelidad semántica son dos checks distintos que deben reportarse. Un `{user}` conservado no salva una instrucción de borrado invertida. El resultado no sobrescribe el archivo fuente por defecto.

### T4 — Elegir entre traducciones, no aceptar la primera

- [ ] Comparar realización determinista, generación de paráfrasis y proveedor externo opcional con presupuestos declarados.
- [ ] Mantener múltiples propuestas cuando el origen es ambiguo; traducir esa ambigüedad o solicitar contexto.
- [ ] Ordenar candidatas que satisfacen restricciones por naturalidad, terminología, estilo y coste.
- [ ] Mostrar alternativas y por qué se descartó cada candidata con cambio crítico.
- [ ] Evaluar si la búsqueda mejora calidad humana frente a un candidato, además de métricas del motor.

**Gate:** T4 demuestra una mejora sobre T2/T3 con evaluación congelada y presupuesto comparable. No fabricar una puntuación estilo Elo sin diseño de comparaciones, evaluadores y denominadores.

### T5 — Párrafos y documentos completos

- [ ] Traducir segmentos manteniendo nombres, referentes, terminología, tono y cronología del documento.
- [ ] Preservar alineación origen/destino incluso cuando un idioma divide o une oraciones.
- [ ] Detectar que un pronombre cambió de referente entre párrafos.
- [ ] Permitir reanudar una traducción sin perder versión de recursos o decisiones ya revisadas.
- [ ] Exportar texto legible más un reporte por segmento; los pendientes no desaparecen dentro de un porcentaje.
- [ ] Empezar por textos de instrucciones y documentación; narrativa larga y diálogo añaden fenómenos y necesitan gates posteriores.

**Gate:** documento bilingüe revisado con trazabilidad completa y límites explícitos; estado global parcial cuando queden segmentos pendientes. Comprobar contenido del principio, del medio y del final, no solo que existe el archivo exportado.

### T6 — Calidad externa y expansión lingüística

- [ ] Medir adecuación, fluidez, terminología y cambios críticos con revisores competentes, preferentemente sin identificar el sistema que produjo cada candidato.
- [ ] Adoptar una taxonomía explícita de errores, por ejemplo compatible con MQM, con severidades y protocolo de adjudicación.
- [ ] Comparar traducciones contra baselines externos sobre el mismo conjunto, dirección y contexto.
- [ ] Usar BLEU/chrF/COMET solo como señales auxiliares cuando sea técnicamente viable y con versiones declaradas; ninguna acredita por sí sola roles o negación.
- [ ] Publicar cobertura, errores aceptados, coste y limitaciones por dirección y dominio.

**Gate:** mejora demostrada en una tarea delimitada y repetible. Una buena evaluación de interfaces no demuestra traducción literaria; un buen resultado inglés→español no demuestra español→japonés.

### Primera entrega recomendada del traductor

Un comando que traduzca **oraciones e instrucciones sencillas inglés↔español**, conserve referentes, cantidades, negaciones y condiciones soportadas, y entregue candidato más diagnóstico. Se puede ofrecer una propuesta para texto fuera de cobertura con estado no verificado cuando la política lo permita.

Esta entrega es más concreta y evaluable que prometer libros completos. El objetivo de documento largo sigue en T5; no se elimina ni se declara cumplido por traducir etiquetas.

## 20. Métricas que sí ayudan a decidir

| Métrica | Definición | Qué evita |
|---|---|---|
| Tasa de falso positivo semántico | Pares no equivalentes aceptados / pares no equivalentes evaluados | Confundir aceptación con corrección |
| Tasa de rechazo de equivalentes | Equivalentes rechazados / equivalentes evaluados | Un motor conservador pero inútil |
| Cobertura acreditada | Casos con decisión sustentada / casos evaluables | Ocultar abstenciones |
| Riesgo selectivo | Errores entre decisiones emitidas / decisiones emitidas | Reportar precisión sin política de abstención |
| Exactitud de roles | Roles correctos / roles gold evaluables | Bag-of-words disfrazada de semántica |
| Conservación por rasgo | Checks correctos de un rasgo / checks gold de ese rasgo | Un agregado que oculta negación o cantidades |
| Cobertura de contenido | Unidades relevantes interpretadas / unidades gold relevantes | Ignorar cláusulas sobrantes |
| Aclaraciones útiles | Ambigüedades resueltas correctamente / aclaraciones respondidas | Preguntas que no mejoran decisiones |
| Fidelidad de ejecución | Programas con trazas gold equivalentes / programas evaluados | Validar solo sintaxis del código |
| Coste de búsqueda | Tiempo, memoria, candidatos y llamadas por solicitud | Mejora aparente comprada con recursos ilimitados |

Cada resultado debe separar fallos de infraestructura, datos inválidos y casos fuera de dominio. Explicar exclusiones y mantener también un conteo sobre el total recibido. No comparar modelos con denominadores diferentes.

**Incertidumbre estadística:** cero errores observados no significa riesgo cero. Como orientación, con cero falsos positivos en `n` negativos independientes, el límite superior unilateral aproximado del 95% es `3/n`; el exacto es `1 - 0.05**(1/n)`. Con 300 negativos independientes, eso ronda el 1%. Variantes de una misma plantilla no son observaciones independientes: reportar agrupación por fuente/construcción y usar intervalos adecuados. No usar esta cuenta para certificar seguridad de ejecución.

## 21. Cómo dividir el trabajo sin perder el rumbo

### Primera etapa: confianza en los veredictos

Completar R0, el bloqueo inicial de R1, R2 y R3. R4 empieza temprano para que el benchmark no nazca después de la solución. La entrega es un motor de dominio pequeño con límites honestos y contraejemplos críticos cerrados.

### Segunda etapa: generalización controlada

Completar R5 y R6. Evaluar R8 en paralelo lógico con el diseño de R7, pero integrar búsqueda solo cuando los gates de verificación estén estables. La entrega es análisis de oraciones nuevas, alternativas y traducciones candidatas explicadas.

### Tercera etapa: producto y dominios

Elegir una primera aplicación: revisión de traducción de instrucciones, localización de interfaces o compilación de órdenes sobre archivos temporales. R9 no es requisito para vender revisión editorial; sí lo es para cualquier producto que ejecute intenciones. Expandir con R10 y R11 según evidencia y demanda. R12 se trabaja desde el principio y se cierra para cada release.

**No fijar fechas antes de medir velocidad.** Después de tres entregas pequeñas, estimar esfuerzo con datos del equipo y revisar el alcance. Un sprint termina por su gate y su capacidad disponible; no por prometer «comprensión universal» para una fecha.

## 22. Primer backlog: diez issues que desbloquean el resto

1. **R0 — Runner adversarial:** contraejemplos, controles y exit codes verificables.
2. **R1 — Prohibición y condición:** negar lowering de órdenes no sustentadas.
3. **R1 — Agentes reales:** eliminar Alice/door inferidos por fragmentos verbales.
4. **R1 — Cobertura completa:** detectar cláusulas y modificadores no representados.
5. **R2 — Colisiones de entidades:** distinguir roles de entidades del mismo concepto.
6. **R2 — Validación de grafo:** referencias, IDs y rasgos tipados.
7. **R3 — Contrato de verificación:** equivalencia y desconocidos consistentes.
8. **R3 — UI verifier real:** analizar destino y rechazar contradicciones.
9. **R3 — Realizador fiel:** negativos y rasgos no soportados no se pierden.
10. **R4 — Holdout independiente:** split por construcciones y reporte de cobertura/riesgo.

Cada issue debe enlazar un milestone y contener: contraejemplo, resultado esperado, archivos, tests, gate, alcance excluido y evidencia del commit. Un issue de investigación debe terminar en decisión documentada y experimento repetible; «investigar más» sin salida definida no es un entregable.

## 23. Definition of Done de cada milestone

- [ ] Su dominio y contratos están escritos, incluyendo abstenciones y límites.
- [ ] Los tests fallaron antes de la corrección cuando se trata de un bug reproducido.
- [ ] Existen casos positivos, negativos y fuera de dominio.
- [ ] Los checks adecuados pasaron con conteos, comandos y revisión identificados.
- [ ] Los reportes y exit codes coinciden; no hay verde con cero checks requeridos.
- [ ] Las migraciones de IR/caché/corpus están documentadas cuando aplican.
- [ ] La evaluación independiente se conservó independiente o se renovó tras depurar.
- [ ] README y matriz de soporte reflejan lo que efectivamente se demostró.
- [ ] Una revisión técnica comprobó el límite de la garantía, además del happy path.
- [ ] La entrega incluye una decisión explícita: pasar, ampliar evidencia o reducir alcance.

## 24. Qué dejar fuera por ahora

- Promesas de traducción universal, libros completos o comprensión de cualquier idioma.
- Minimax, redes de evaluación entrenadas o grandes búsquedas antes de asegurar los veredictos básicos.
- Un rediseño completo de frontend mientras la semántica central acepta contradicciones.
- Agregar todos los idiomas a la vez o reemplazar WordNet sin una comparación controlada.
- Un número único de «confianza» que mezcle fluidez, equivalencia y permiso de ejecución.
- Aprendizaje automático a partir de cada aceptación humana sin adjudicación ni control de calidad.
- Dar prioridad al porcentaje del README sobre la detección de errores nuevos.

## 25. Qué significaría acercarnos de verdad

La primera victoria es que el motor diga: «esa traducción invierte quién actuó», «esa cláusula quedó sin representar» o «necesito saber a qué archivo te refieres», y podamos comprobar por qué.

La siguiente es que encuentre varias traducciones nuevas, descarte las que cambian significado y explique las restantes dentro de un presupuesto.

La victoria humano→máquina es que una instrucción se compile con sus condiciones, referentes y efectos intactos, y que su ejecución dependa de permisos explícitos.

Ese recorrido convierte la metáfora de Stockfish en decisiones de ingeniería: representación, reglas, búsqueda, evaluación y evidencia. El motor gana fuerza cuando mejora su cobertura manteniendo visibles sus errores y sus límites.
