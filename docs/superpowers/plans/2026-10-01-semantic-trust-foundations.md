# Semantic Trust Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** convertir los contraejemplos auditados en evidencia reproducible y bloquear las prohibiciones, condiciones y citas conocidas antes de que habiliten lowering.

**Architecture:** primero un runner adversarial que mide comportamiento externo y conserva sus fallos; después un gate conservador sobre la superficie original de las órdenes. El runner no ejecuta capabilities. Este sprint entrega R0 y una parte delimitada de R1; canonicalización, gramática completa y verificador uniforme requieren sus propios planes posteriores.

**Tech Stack:** Python >=3.12; pytest; dataclasses y JSON de la biblioteca estándar; dependencias existentes de IntentLang y WordNet local. No añadir servicios o modelos externos para estas tareas.

**Spec:** [ROADMAP.md](../../../ROADMAP.md), especialmente R0, R1, reglas globales y Definition of Done.

## Global Constraints

- **Desconocido no significa equivalente.** Falta de evidencia produce abstención o revisión.
- **No perder contenido silenciosamente.** Lo no interpretado se conserva como cobertura pendiente.
- **No convertir descripción en autorización.** Una oración narrativa, citada o hipotética no es una orden.
- Python >=3.12 según `pyproject.toml`; usar el entorno y los recursos existentes.
- Ninguna prueba de este sprint ejecuta capabilities ni toca archivos del usuario fuera de fixtures temporales.
- No reducir controles positivos, cambiar gold para aceptar un bug o esconder fallos críticos con xfail permanente.
- El modo assisted debe comprobar la superficie original antes de habilitar una acción.
- Los umbrales del roadmap son objetivos propuestos, no resultados ya obtenidos.

## Review Focus

1. Prohibición con flexión distinta: `no copies el archivo` no habilita COPY.
2. Condicional con acción léxicamente válida: `si falla, borra el archivo` no habilita REMOVE incondicional.
3. Cita o instrucción descrita: `el manual dice: borra el archivo` no habilita una acción directa.
4. Assisted propone un verbo válido para una superficie prohibida: no salta el gate.
5. Runner con fixtures vacías, inválidas o recursos ausentes: falla explícitamente y conserva el diagnóstico.

---

## Task 1: runner adversarial y fixtures versionadas

**Files:**

- Create: `ci/run_adversarial_benchmark.py`.
- Create: `corpus/semantic/adversarial_regressions.jsonl`.
- Create: `tests/test_adversarial_benchmark.py`.

**Interfaces propuestas:**

- `run_adversarial_benchmark(corpus_path: str) -> dict`: valida todas las filas antes de ejecutar; devuelve `schema`, `cases`, `counts`, `infrastructure_errors`, `invalid_fixtures`.
- `main() -> int`: acepta `--corpus` y `--output-dir`; escribe `adversarial_report.json`; retorna 0 si no hay fallos requeridos, 1 para diferencias de comportamiento y 2 para datos/infraestructura inválidos. Si concurren categorías, prevalece 2.
- Una fila contiene `case_id`, `kind`, `language`, `source`, `candidate` opcional y `expected`. `kind` es `meaning_pair` o `intent_surface`.
- Para `meaning_pair`, `expected.relation` es `equivalent` o `different`; un caso `different` exige `compare_candidates(...)["semantic_passes"] == 0`.
- Para `intent_surface`, `expected.can_act` es bool y `expected.primitive` se usa en controles positivos. Los negativos comprueban también rechazo de `lower_intent_to_program`, sin llamar al ejecutor.
- `counts` incluye `total`, `passed`, `false_accept`, `false_reject` y `abstain`. Clasificar abstención como resultado esperado o fallo según la expectativa de la fila; no afirmar que UNKNOWN acredita una traducción equivalente.

- [ ] **Step 1:** escribir `test_runner_detects_a_known_false_accept`: una fixture con `Alice saw the rabbit` y `Alice never saw the rabbit`, relación `different`, debe reportar `false_accept == 1` en la revisión auditada. Es una prueba del detector, no un test que declara correcto el bug; al arreglar el parser, sustituir su entrada por un comparador controlado que acepta una contradicción y conservar el caso real en el corpus.
- [ ] **Step 2:** escribir `test_runner_rejects_empty_duplicate_or_invalid_fixtures`: corpus vacío, IDs duplicados, kind desconocido y relación no soportada producen `invalid_fixtures`, nunca un gate verde.
- [ ] **Step 3:** escribir `test_runner_classifies_missing_wordnet_as_infrastructure`: simular `LexiconUnavailable` en la operación usada por el runner; `infrastructure_errors == 1` y resultado no aprobado.
- [ ] **Step 4:** ejecutar `.venv/bin/python -m pytest tests/test_adversarial_benchmark.py -q`; debe fallar antes de crear el runner.
- [ ] **Step 5:** implementar las interfaces y clasificación; usar las funciones reales de producción para casos reales y dobles solo para tests del propio runner.
- [ ] **Step 6:** cargar las siete parejas de Meaning de la tabla del roadmap, seis superficies de intención auditadas y controles positivos equivalentes. Asignar IDs descriptivos, estables y únicos. Cada expectativa debe revisarse independientemente de la salida actual.
- [ ] **Step 7:** ejecutar los tests del runner; deben pasar. Ejecutar el runner real con `WN_DATA_DIR` configurado; se espera exit 1 mientras los bugs de Meaning y de intención sigan abiertos. El reporte debe mostrar cuáles, sin xfail permanente.
- [ ] **Step 8:** commit `test: capture semantic false accepts in adversarial benchmark`, añadiendo solo los tres archivos de esta tarea.

## Task 2: bloquear las superficies ejecutables conocidas que no representan una orden sustentada

**Files:**

- Modify: `src/intentlang/resolve.py`.
- Modify: `src/intentlang/normalize.py` solo si necesita compartir segmentación ya existente.
- Test: `tests/test_resolve.py`.
- Create: `tests/test_intent_surface_safety.py`.

**Interfaces:**

- Consume: `resolve(text, lang, mode="strict", propose_fn=None) -> Intent` existente.
- Produce: la misma interfaz; para las superficies negativas de esta tarea, `status == Status.UNKNOWN`, `can_act() is False` y texto original preservado en provenance.
- Consume: `lower_intent_to_program(intent) -> Program`; ya rechaza estados no RESOLVED con `ValueError`. No cambiar esa excepción para estos casos.
- La comprobación corre antes de las ramas strict/assisted. No añadir una alternativa pública de «ignorar gate».
- La implementación conservadora inicial cubre negación/prohibición, condición y cita explícitas en español/inglés. Debe documentar su alcance; la gramática estructural de R5 sustituirá las heurísticas. No atribuir protección general a otros idiomas ni degradarlos todos por accidente.

- [ ] **Step 1:** añadir el test parametrizado siguiente en `tests/test_intent_surface_safety.py`:

```python
import pytest
from intentlang.ir import Status
from intentlang.resolve import resolve
from intentlang.lowering import lower_intent_to_program

@pytest.mark.parametrize("text", [
    "no borres el archivo",
    "no copies el archivo",
    "si falla, borra el archivo",
    "el manual dice: borra el archivo",
])
def test_unsupported_order_surface_cannot_lower(text):
    intent = resolve(text, "es")
    assert intent.status is Status.UNKNOWN
    assert not intent.can_act()
    assert intent.provenance.surface == text
    with pytest.raises(ValueError):
        lower_intent_to_program(intent)
```

- [ ] **Step 2:** añadir `test_positive_copy_control_still_resolves` con `copia el archivo`: RESOLVED, COPY, `can_act()` verdadero y lowering disponible. No ejecutar el programa.
- [ ] **Step 3:** añadir `test_assisted_cannot_override_prohibition`: `resolve("no copies el archivo", "es", mode="assisted", propose_fn=lambda *_: ["copiar"])` debe ser UNKNOWN y no poder actuar. Usar un spy adicional para verificar que el proponente no se invoca.
- [ ] **Step 4:** añadir `test_english_prohibition_condition_and_quote_cannot_lower` con `do not copy the file`, `if it fails, delete the file` y `the manual says: copy the file`; aplicar las mismas assertions de Step 1. Control positivo: `copy the file` sigue RESOLVED/COPY.
- [ ] **Step 5:** ejecutar `WN_DATA_DIR=/workspace/.cache/intentlang-wn .venv/bin/python -m pytest tests/test_intent_surface_safety.py -q`; confirmar fallos que muestran aceptación indebida, no fallos por imports o recursos ausentes.
- [ ] **Step 6:** implementar el gate inicial y su alcance explícito en `resolve.py`, preservando procedencia y comportamiento de controles positivos. Revisar puntuación, mayúsculas y límites de tokens: no bloquear una palabra porque contiene incidentalmente letras de un marcador.
- [ ] **Step 7:** ampliar el test parametrizado con mayúsculas y puntuación de los mismos casos; verificar control positivo con puntuación final. Registrar patrones no soportados como deuda, sin prometer detección completa de discurso indirecto.
- [ ] **Step 8:** ejecutar tests de superficie y `tests/test_resolve.py`; revisar que assisted, los idiomas ya probados y provenance conservan su contrato.
- [ ] **Step 9:** ejecutar el runner de Task 1. Los negativos de intención deben dejar de fallar; los de Meaning siguen fallando y deben permanecer visibles. Este sprint no acredita R1 completo.
- [ ] **Step 10:** commit `fix: block unsupported order surfaces before intent resolution`, incluyendo implementación y tests de esta tarea.

## Task 3: integrar evidencia sin publicar una garantía que todavía no existe

**Files:**

- Modify: `README.md`.
- Create: `docs/evaluation.md`.
- Modify: `.github/workflows/ci.yml` solo para el reporte adversarial con política explícita.
- Test: `tests/test_adversarial_benchmark.py`.

**Interfaces:**

- Consume: runner y reporte de Task 1.
- Produce: documentación que distingue la suite existente, el corpus controlado y la regresión adversarial pendiente.
- CI publica el reporte y conserva su exit status; mientras queden bugs registrados, puede ser un job informativo explícito, sin afirmar que pasó. No alterar el estado de los jobs existentes para aparentar éxito.
- Antes de promocionarlo a gate obligatorio, cerrar R1–R3 o dividir el corpus en gates definidos por milestone. Nunca excluir silenciosamente los casos rojos.

- [ ] **Step 1:** añadir tests de CLI del runner con fixtures controladas: exit 0 para controles aprobados, 1 para falso positivo y 2 para datos/infraestructura inválidos; verificar reporte del mismo run.
- [ ] **Step 2:** ejecutar los tests y corregir cualquier discrepancia entre exit code y reporte.
- [ ] **Step 3:** documentar comandos, esquema, denominadores, límites y diferencias entre benchmarks. Aclarar que la cifra actual del README pertenece a un corpus controlado, no a traducción general.
- [ ] **Step 4:** añadir el job informativo con resultado fallido visible y artifact, si la política del repositorio permite jobs informativos. No usar `|| true` para borrar el resultado; si usa `continue-on-error`, escribir su motivo y plan de promoción a gate en el workflow y documentación.
- [ ] **Step 5:** ejecutar suite completa, lint y type check según CI; informar tests aprobados, omitidos y cualquier fallo nuevo. Los bugs adversariales todavía abiertos deben constar separadamente.
- [ ] **Step 6:** revisar que ningún texto diga «verificación completa», «fail-closed universal» o «Stockfish logrado» por completar este sprint.
- [ ] **Step 7:** commit `docs: document adversarial evaluation and current guarantees`.

## Comandos de validación del sprint

Desde la raíz del checkout, inicializar el virtualenv y `WN_DATA_DIR` según el entorno disponible. En el entorno cloud auditado:

```bash
cd /workspace/IntentLang
export WN_DATA_DIR=/workspace/.cache/intentlang-wn
.venv/bin/python -m pytest -q --tb=short -ra -p no:cacheprovider
.venv/bin/ruff check src/ tests/ --no-cache
.venv/bin/mypy src/intentlang --ignore-missing-imports
.venv/bin/python ci/run_adversarial_benchmark.py \
  --corpus corpus/semantic/adversarial_regressions.jsonl \
  --output-dir /tmp/intentlang-adversarial
```

El último comando **no existe hasta Task 1** y se espera que siga fallando por los bugs de Meaning aún abiertos. No describir todos los checks como aprobados al final de este sprint si ese reporte continúa rojo.

## Handoff y frontera del sprint

Este documento es un plan futuro, no una ejecución. La publicación del roadmap no instala estas APIs, no crea fixtures ni corrige producción. El siguiente plan detallado debe cubrir R2 y el cierre de R1/R3 usando la evidencia congelada; no arrancar búsqueda R7 para esquivar esos defectos.
