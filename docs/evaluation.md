# Evaluación de IntentLang: evidencia antes que porcentajes

R0 convierte la auditoría del roadmap en una regresión reproducible. El runner
no corrige el parser, no genera traducciones ni ejecuta capabilities: evalúa
pares de significado y la posibilidad de compilar superficies de intención.

## Tres recorridos diferentes

| Recorrido | Entrada | Qué comprueba | Qué no demuestra |
|---|---|---|---|
| M0, `ci/run_semantic_benchmark.py` | Cuatro controles de intención/prosa | Resolución léxica y comportamiento del materializador | Traducción narrativa general; su CLI siempre devuelve 0 |
| Gates de Meaning IR, `run_m2_gate` / `run_m3_gate` | Corpus controlado `meaning_m1.jsonl` | Parser y realizador sobre 100 registros / 400 variantes | Generalización independiente ni ausencia de errores compartidos |
| R0, `ci/run_adversarial_benchmark.py` | Pares contrastivos y órdenes con gold explícito | Falsos positivos, rechazos, abstenciones e infraestructura | Precisión general, calidad de generación o permiso real de ejecución |

El corpus controlado tiene 100 registros y 400 variantes. En la revisión base
auditada sus variantes inglesas produjeron 20 claves semánticas distintas,
incluyendo UNKNOWN. Una variante adicional no es necesariamente un significado
nuevo ni una observación independiente.

## Ejecutar R0

Desde la raíz del checkout, con dependencias instaladas y WordNets locales:

```bash
export WN_DATA_DIR=/workspace/.cache/intentlang-wn
.venv/bin/python ci/run_adversarial_benchmark.py \
  --corpus corpus/semantic/adversarial_regressions.jsonl \
  --output-dir /tmp/intentlang-adversarial
```

En otro entorno, usar el intérprete del virtualenv y su directorio WordNet.
El runner no descarga recursos automáticamente. Una instalación sin WordNet
produce un error de infraestructura para los casos que lo necesitan; no lo
convierte en un UNKNOWN lingüístico ni en un resultado aprobado.

Archivos del mismo run:

- `adversarial_report.json`: fixtures, expectativas, resultados, IR, claves,
  diferencias del comparador, rechazos de lowering y diagnósticos.
- `adversarial_report.md`: tabla legible de cada caso y resumen de resultados.

Los reportes incluyen revisión Git, estado dirty, hash SHA-256 del corpus,
comando CLI, fecha, duración, CPU del proceso, plataforma y versiones de
dependencias. Si el árbol está dirty, la revisión por sí sola no reproduce las
ediciones locales: repetir desde un commit limpio antes de usarlo como evidencia
de release. El tiempo de CPU no incluye procesos secundarios y no es un perfil
completo de memoria o rendimiento.

El código de salida es parte del resultado:

| Código | Significado |
|---|---|
| 0 | Todas las expectativas fueron cumplidas, incluyendo rechazos seguros previstos |
| 1 | Hubo al menos una expectativa semántica/de intención incumplida |
| 2 | Corpus inválido, recurso/error técnico, o imposibilidad de guardar evidencia |

El código 2 prevalece sobre el 1. Una sola dependencia rota no cancela los otros
casos independientes; el reporte conserva ambos tipos de fallo. Si una fixture
es inválida, se valida todo el corpus y no se evalúa ninguna fila. Corpus vacío
nunca acredita el flujo. Si no se puede escribir el destino, se informa el
error en stderr y no se debe tratar un reporte antiguo de ese directorio como
evidencia del intento fallido.

Al capturar logs, preservar el exit code del runner. No añadir `|| true` y
después llamar al resultado «aprobado».

## Corpus versionado

Cada línea de `corpus/semantic/adversarial_regressions.jsonl` es un objeto JSON.
IDs duplicados, campos requeridos inválidos y expectativas no reconocidas se
rechazan. Los metadatos adicionales de una fixture pueden ampliarse, pero el
objeto `expected` es cerrado: el runner no ignora garantías desconocidas.

Para una comparación de significado:

```json
{
  "case_id": "roles-inverted",
  "kind": "meaning_pair",
  "phenomenon": "roles",
  "language": "en",
  "source": "Alice saw the rabbit",
  "candidate": "The rabbit saw Alice",
  "expected": {"relation": "different"}
}
```

`relation` admite `equivalent` o `different`. `target_language` es opcional y
hereda `language`; permite evaluar candidatos bilingües reales. Este runner
limita Meaning IR a los cuatro idiomas que soporta actualmente su parser:
inglés, español, japonés y chino. Un idioma no soportado es un problema de la
fixture y no una abstención que pueda mejorar artificialmente las métricas.

Para una superficie de intención:

```json
{
  "case_id": "prohibition-remove",
  "kind": "intent_surface",
  "phenomenon": "prohibition",
  "language": "es",
  "source": "no borres el archivo",
  "expected": {"can_act": false}
}
```

Los positivos requieren `expected.primitive`, por ejemplo
`{"can_act": true, "primitive": "COPY"}`. Se comprueban `can_act()` y lowering
de forma independiente: un estado no accionable con lowering permitido sigue
siendo un falso positivo. No se invoca el ejecutor ni una capability. Para
intenciones se admiten los idiomas declarados por los packs del checkout;
tener un pack no implica tener disponible su recurso WordNet.

## Abstención, aprobado y denominadores

Los outcomes son disjuntos y suman `counts.total`:

- `passed`: una comparación decidida coincide con el gold, o una intención
  positiva coincide con su primitiva y permite lowering.
- `false_accept`: un candidato diferente se acepta, o una superficie que no
  debe habilitar acciones permite actuar o compilar.
- `false_reject`: una comparación decidida rechaza un equivalente, o una
  intención positiva no cumple su contrato pese a una decisión accionable.
- `abstain`: el parser/resolutor no sustenta una decisión completa.
- `infrastructure_error`: la operación falla técnicamente; el tipo de excepción
  y el caso se mantienen en `infrastructure_errors`.

`case.passed` representa **expectativa cumplida**, no «se demostró equivalencia».
Una intención prohibida que no actúa ni compila cumple su expectativa mediante
abstención. Un candidato gold negativo no resuelto puede ser un rechazo seguro,
si el origen sí se resolvió: se mantiene en `abstain`, no en `passed`. Un origen
no resuelto no permite acreditar la comparación; incumple la expectativa. Un
equivalente no resuelto también incumple su expectativa.

Por eso `statistics.expectations_met` puede ser mayor que `counts.passed`.
No calcular precisión general dividiendo uno de esos números por 20.

`statistics` separa registros parseados y evaluados, apariciones de textos,
textos únicos por idioma, claves fuente RESOLVED únicas, predicados fuente,
familias de fenómenos, tipos de caso, idiomas y expectativas positivas/negativas.
Las etiquetas `phenomenon` son familias anotadas, no un conteo automático de
gramáticas distintas. Las claves proceden del parser auditado: una colisión
puede reducir su número; no son una medida independiente de diversidad gold.

## Línea base dirigida de R0

El corpus inicial tiene **20 registros**: 13 pares Meaning y 7 superficies de
intención. Los pares incluyen 9 negativos y 4 equivalentes, tres de ellos con
candidatos en español. Las intenciones incluyen 2 órdenes positivas y 5
superficies que no deben habilitar una acción.

La primera ejecución sobre el motor de la revisión `761c06e` observó:

| Outcome | Casos |
|---|---:|
| passed | 8 |
| false_accept | 11 |
| false_reject | 0 |
| abstain | 1 |
| infrastructure_error | 0 |

Se cumplieron 9 expectativas de 20, incluyendo una abstención segura. El runner
salió con **1**. Este es un conjunto dirigido a fallos ya encontrados, no un
holdout ni una estimación de error sobre lenguaje humano general.

Los 11 falsos positivos se reparten en 7 comparaciones que pierden roles,
negación, modalidad o contenido y 4 superficies de intención que pierden
prohibición, condición o discurso referido. Los controles positivos evitan que
«todo UNKNOWN» se presente como corrección. Los fallos de colisión de entidades,
realización y los otros verificadores de la auditoría siguen registrados en
el roadmap y requieren nuevos tipos de caso en sus milestones: estos 20 casos
no cubren toda la auditoría ni traducen documentos completos.

## CI y próximos gates

El job `Adversarial Evidence (R0)` conserva reportes aunque el benchmark falle.
Es informativo mediante `continue-on-error` **a nivel de job**, mientras existan
los bugs documentados: la ejecución del benchmark no borra su código de salida
y el resumen muestra el outcome del step. Que el resto del workflow esté verde
no significa que R0 esté verde. Fallos de instalación y recursos también quedan
visibles y nunca se reclasifican como diferencias semánticas.

Promover el job a gate obligatorio al cerrar las regresiones R1–R3, o dividirlo
en gates por milestone con IDs y cobertura declarados. No eliminar las filas
rojas ni cambiar gold para que coincida con la salida actual.

Las pruebas de `tests/test_adversarial_benchmark.py` verifican el detector, su
validación, denominadores, respuestas ante recursos ausentes y exit codes.
No exigen que un bug del motor siga existiendo. Cuando un fix de producción
mejora la semántica, el benchmark mejora sin romper las pruebas del detector.

La evaluación independiente de R4 y la evaluación del generador/traductor de
T0–T6 son entregas posteriores y separadas. Comparar candidatos existentes no
equivale a medir cómo los genera el motor.
