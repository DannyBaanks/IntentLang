# intent-lang

> Un lenguaje donde el lenguaje natural es una **representación superficial** de la intención, no la intención misma.

```
"agrega cuerpo"    "add body"    "添加身体"    "ajoute le corps"
```

No son cuatro instrucciones. Son cuatro formas de expresar la misma intención canónica.

**Estado: núcleo implementado** — 8 language packs locales y 44 primitivas de runtime. Este README es el tour; [`DESIGN.md`](DESIGN.md) es la especificación.

```powershell
py -m intentlang resolve "agrégale cuerpo" --lang es
py -m intentlang judge "agrégale cuerpo" --lang es  # -> judgments.jsonl
py -m intentlang execute "copia el archivo" --lang es   # resolve + lower -> Program IR
```

## Interfaz web

La consola web muestra la entrada humana y el `Intent IR` en dos paneles. La
publicación de GitHub Pages y Docker es una demo estática; no ejecuta
capabilities ni resuelve texto arbitrario sin el servidor Python local.

```powershell
py web/server.py
```

Abre `http://127.0.0.1:8765`.

Para levantar la demo estática con Docker:

```powershell
docker compose up -d
```

Abre `http://127.0.0.1:8080`.

La demo publicada por GitHub Pages estará en
`https://dannybaanks.github.io/intent-lang/` después de ejecutar el workflow de
publicación.

## La Idea

Es más fácil pensar en el idioma que ya dominas que en uno aprendido. Casi todos los lenguajes de programación tienen keywords en inglés, y esa es una capa de fricción entre humano y máquina que nadie eligió.

La propuesta no es "programa en tu idioma" — eso ya existe (Scratch lo hace en 70+ idiomas) y cualquier LLM traduce intención a código. La propuesta es más estrecha y por eso más interesante:

> **Lenguaje natural como método de entrada a un núcleo diminuto y verificable, donde la ambigüedad no se adivina y el round-trip te muestra lo que se entendió.**

Si el núcleo es pequeño, la traducción deja de ser un problema abierto y se vuelve verificable.

## Qué Lo Hace Distinto

**El diccionario no basta, y el diseño lo asume.** Para "agrega cuerpo", un diccionario confirma que `agregar` significa add. No puede decir si `cuerpo` es un cuerpo físico o un campo `body`. Por eso hay **dos autoridades**: el léxico autoriza que una palabra existe y en qué sentido; una tabla finita y auditable autoriza qué intenciones existen.

**El modelo propone, el léxico decide.** Cuando el léxico falla, un LLM propone lemas candidatos — y esos candidatos vuelven al léxico para validación. Una propuesta que no existe en el diccionario se rechaza sin apelación. "Significado no inventado" es estructural, no una promesa.

**La ambigüedad es un estado, no un error.** Cuatro estados, solo uno actúa:

```
RESOLVED     verbo y operando únicos             → único que puede actuar
AMBIGUOUS    >1 candidato sobrevivió validación   → preguntar
UNKNOWN      no está en léxico, o no mapea       → no actúa
INCOMPLETE   verbo sí, operando requerido falta  → pedir lo que falta
```

**El round-trip es un test, no decoración.** El sistema devuelve lo que entendió usando una palabra **distinta** del mismo synset:

```
escribes   "agrégale cuerpo"
sistema    "Entendí: AÑADIR (cuerpo). ¿Correcto?"
                      └── otra palabra del MISMO synset
```

Si devuelve tu palabra exacta, la capa semántica no corrió y estás viendo un passthrough de strings. Hay un test que verifica esto.

## Sobre la RAE

La primera versión de esta idea pedía "cumplimiento estricto RAE". No funciona: el DLE es un diccionario de definiciones en prosa para humanos, sin identificadores de sentido estables ni API.

Lo que el diseño necesitaba — equivalencia de **conceptos**, no palabras — ya existe con otro nombre: un **índice interlingual**. WordNet + Open Multilingual WordNet enlazan sentidos entre docenas de idiomas al mismo ID de concepto.

```
es "agregar" ──┐
en "add"     ──┼──►  mismo ID ILI, sin idioma
zh "添加"     ──┘
```

Y da una propiedad gratis: los synsets **ya son clases de paráfrasis**. `agregar / añadir / sumar / incorporar` comparten synset, así que convergen sin que intervenga ningún modelo.

## Cómo Sabemos Que Funciona

```
separación      AUTOMÁTICA, debe ser 100%    dos intenciones distintas
                                               nunca comparten representación
convergencia    MEDIDA, reportada              no re-test
round-trip      HUMANO                         la barra de éxito
```

La convergencia sola es métrica trampa: un sistema que mapea todo a `ADD` converge perfecto e inútil. El fallo peligroso no es que dos paráfrasis no converjan — es que dos intenciones **distintas** colapsen a la misma representación. Por eso separación es la única que puede romper el build.

### Alcance actual

El núcleo conserva las 8 primitivas semánticas de la primera versión y ahora
incluye 8 packs locales (`es`, `en`, `zh`, `ja`, `ar`, `fi`, `he`, `tr`), 44
primitivas de runtime, Program IR, capabilities y tabla de dominio. Chino,
japonés, árabe, finés y hebreo sirven como pruebas de cobertura
interlingüística; sus gaps se reportan, no se rellenan con adivinanzas. Turco
es todavía un placeholder porque `omw-tr:1.4` no está disponible en OMW.

## Engine-lang (framework de extensibilidad)

Los idiomas son **plugins de datos YAML** para **estrategias de normalización soportadas** (simplemma, jieba, fugashi, kiwi, pymorphy3, regex). Nueva morfología = cambio en core.

```
engine_lang/
  languages/*.yaml       # 8 packs (es, en, zh, ja, ar, fi, he, tr)
  contracts/language.v1.json
  verifier.py            # wordnet + tokenizer + check semántico corpus
  installer.py           # remote registry download + validate
  cli.py                 # engine-lang install/verify/list/validate/remote
```

```powershell
engine-lang list              # idiomas instalados + estado
engine-lang verify            # exit 1 en cualquier FAIL
engine-lang install he        # download + validate + wordnet check
```

## Intent Program IR

3 familias de primitivas composables (44 primitivas de runtime):

```
EFECTOS (side effects):     COPY MOVE REMOVE RUN QUERY CHANGE ADD CONNECT
                            DOWNLOAD COMPILE RENDER SIGN WRITE READ DELETE ...

DATOS (transformación):     VALUE BIND LOAD STORE COMPARE MAP FILTER
                            COLLECT REDUCE PROJECT JOIN SORT GROUP

CONTROL (flujo):            SEQUENCE IF LOOP CALL RETURN MATCH ASSERT TRY
                            PARALLEL FOREACH
```

Para composición compleja existe una capa estructurada JSON separada del
lenguaje natural. Convierte pasos y referencias en Program IR, comprueba
entradas requeridas y tipos escalares, genera un plan de efectos y exige
confirmación antes de ejecutar efectos:

```python
from intentlang import plan_program, parse_structured, run_structured

source = '{"steps":[{"call":"cap.fs.write","inputs":{"path":"out.txt","content":"ok"}}]}'
plan = plan_program(parse_structured(source))
# plan.requires_confirmation is True
plan, result = run_structured(source, confirmed=True)
```

La capa estructurada admite `sequence`, `let`, `if/else`, `foreach` y
`compare`, además de referencias a bindings. El mismo Program IR genera un
programa completo para C y Java, con helpers reales para `WRITE`, `COPY`,
`MOVE`, `DELETE` y `RUN`; los smoke tests los compilan cuando sus toolchains
están disponibles. Los templates individuales también cubren `READ`.

Pipeline:
```
texto natural
      ↓ resolve (lexicon)
Intent IR (RESOLVED)
      ↓ lowering (primitive -> capability)
Program IR (árbol de primitivas)
      ↓ execute (capability registry)
EJECUCIÓN + EVIDENCIA
```

## Capability Registry

21 capabilities con contrato (JSON Schema + pre/postconditions + side effects declarados):

```powershell
cap.fs.copy     cap.fs.move    cap.fs.delete   cap.fs.write
cap.fs.read     cap.process.run  cap.net.connect  cap.net.download
```

```python
execute_capability("cap.fs.copy", {"src": "a.txt", "dst": "b.txt"})
# {"copied": True, "src": "a.txt", "dst": "b.txt"}
```

## Discovery Engine

```text
UNKNOWN surface
      ↓
enumerate_candidates (lexicon + verb_candidates)
      ↓
verify_candidate (test cases -> execute_capability)
      ↓
register_primitive (registro en memoria)
```

```python
discover(surface, lang, test_cases)
# -> Candidate(...) si un candidato existe y pasa sus casos de prueba
```

## COBOL

El backend COBOL genera fuente compatible con GnuCOBOL para `WRITE`, `READ`,
`RUN`, `COPY`, `MOVE` y `DELETE`. También cubre secuencias, `IF/ELSE`,
`FOREACH` sobre listas literales, `TRY`, `RETURN`, funciones estructuradas y
transacciones con rutas explícitas. Las capabilities fuera de esta lista se
mantienen como hooks no habilitados. La compilación requiere `cobc` instalado.

`verify_cobol_round_trip` recupera capabilities e inputs literales de programas
lineales generados y los compara con el `Program IR` original. Antes de aceptar
el resultado valida los inputs contra los contratos registrados. Si encuentra
una mutación, una sentencia extra o una construcción que no reconoce, devuelve
rechazo o `NOT_SUPPORTED`.

En `READ`, el renderer declara un registro variable con un buffer máximo de
`8192` bytes y obtiene la longitud mediante `WS-INPUT-SIZE`. El límite de la
capability es `4096` bytes. El test correspondiente usa un registro de `4097`
bytes y comprueba que el ejecutable termina con código `99` sin procesarlo.
Esta comprobación corresponde a ese layout; otros layouts COBOL necesitan
pruebas específicas.

## Instalación autónoma

Requisito: Python 3.12 o posterior.

### Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cobc --version
.\.venv\Scripts\python.exe -m pytest -q
ruff check src/ tests/
mypy src/intentlang --ignore-missing-imports
```

Instala GnuCOBOL mediante una distribución pública de MSYS2 y añade su
directorio `bin` al `PATH` antes de ejecutar `cobc --version`. Intent Lang no
descarga ni contiene el compilador.

### Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
sudo apt update
sudo apt install gnucobol
cobc --version
.venv/bin/python -m pytest -q
ruff check src/ tests/
mypy src/intentlang --ignore-missing-imports
```

En Fedora usa `sudo dnf install gnucobol`; en Arch usa `sudo pacman -S
gnucobol`. Intent Lang no descarga ni contiene el compilador.

Para validar generación COBOL, crea un `Program IR`, genera la fuente con
`generate_program_source(program, "cobol")`, compílala con `cobc -x` y ejecuta
el binario resultante. Las capabilities que siguen siendo hooks no deben
describirse como verificadas.

## Estado medido (2026-08-28; oráculo 2026-08-30)

| métrica | valor | nota |
|---|---|---|
| separación | **100%** | invariante que rompe el build, cero colisiones entre casos RESOLVED etiquetados |
| determinismo (strict) | igualdad de objeto mismo-proceso | byte-idéntico cross-process **NOT_DEMONSTRATED** |
| convergencia (por ILI) | **0/3 grupos (0%)** | medido por la suite actual, reportado, no disfrazado — ver abajo |
| paridad (oráculo ejecutivo) | **3/3 grupos (100%)** | misma huella SHA-256 en oráculo simbólico Y en fs real; controles de granularidad OK |
| domain table con evidencia | 5 VERIFIED / 1 REJECTED / 12 NOT_DEMONSTRATED | `prove` sha256 `9787d5a7…`; ver sección del oráculo |
| fix cobertura verbo | `duplicar` → COPY | i34961/i30414 verificado contra omw-es+en |
| round-trip idioma objetivo completo | **NOT_DEMONSTRATED** | mensajes de envoltorio (Entendí/¿Correcto?) siguen en español; relexicalización de concepto funciona |
| caché firmado asistido | **IMPLEMENTED (API)** | caché persistente local con `evidence_sha256` y firma SHA-256; `get_or_compute` conserva una IR mínima de la propuesta |

**Por qué 0% convergencia es honesto:** en omw-*:1.4, `archivo`(es), `file`(en) y `文件`(zh) no comparten **ningún** ILI (es tiene i50132/i71104 = sentidos *archive*; el ILI de archivo-informático i70665 existe solo en en/zh). La suite documenta esto como gap léxico conocido — arreglarlo requiere un wordnet español mejor o una tabla de dominio explícita, no adivinanza silenciosa.

## Oráculo de paridad semántica

La convergencia por ILI mide la salud del lexicón. La paridad por oráculo
mide lo que el sistema **demuestra ejecutando**: cada superficie pasa por dos
oráculos — la máquina simbólica de `oracle.py` y el filesystem real
(`cap.fs.*` en tmpdir) — y la paridad exige que **ambas** huellas SHA-256 del
estado resultante coincidan. La DOMAIN_TABLE es la hipótesis bajo prueba, no
una verdad afirmada: sin hipótesis no hay instanciación, y los gaps se
reportan, no se rellenan.

```powershell
py -m intentlang.parity corpus   # paridad del corpus: 3/3 grupos VERIFIED
py -m intentlang.parity prove    # evidencia de la tabla -> data/domain_oracle_proofs.json + sha256
```

Lo primero que el oráculo encontró al medir la tabla: la fila `move`
afirmaba ar `نقل` como equivalente, pero su ejecución resuelve a COPY por
ILI (huella distinta) → la fila queda REJECTED y, con el archivo de pruebas
presente, `resolve_with_domain` no aplica override para `move` hasta que la
tabla se corrija. Afirmar a mano ya no basta.

Controles obligatorios: las huellas de ADD/COPY/MOVE/REMOVE sobre el mismo
símbolo deben ser todas distintas (granularidad); si colapsasen, la medición
entera sería trampa y el test lo grita. Superficies no resolubles o sin
hipótesis quedan `NOT_RESOLVED`/`NOT_INSTANTIABLE` y se listan como gaps.

## Licencia

MIT.

## Genealogía

Viene de [JAJAJA](https://github.com/DannyBaanks/JAJAJA), un esolang cuyo alfabeto son repeticiones de `ja`.

```
JAJAJA       representación absurda   →  mismo contrato
intent-lang  representación humana    →  mismo contrato
```

Uno pregunta *"¿puedo ejecutar aunque la representación sea ridícula?"*. El otro pregunta *"¿puedo ejecutar sin obligar al humano a aprender una representación artificial?"*. Mismo experimento, extremos opuestos.

*(The repo name is in English and the design in Spanish. Consistent with the thesis: the surface is not the semantics.)*
