# IntentLang

## Traduce lo que significa, no solamente lo que dice

IntentLang es un motor de traducción semántica. Su objetivo es que una idea
conserve el mismo significado aunque cambie el idioma, la redacción o el
formato del texto.

> Si una traducción cambia quién hizo algo, qué ocurrió, cuándo ocurrió o si
> ocurrió, IntentLang debe detectarlo.

```text
Alice saw the rabbit
        ↓
   mismo significado
        ↓
Alicia vio al conejo
アリスはウサギを見た
爱丽丝看见了兔子
```

No se trata de sustituir palabras una por una. Primero se representa el
significado de la frase y después se genera la forma adecuada para cada idioma.

## ¿Para quién es?

Para personas que necesitan traducir contenido importante sin tener que
confiar ciegamente en que una frase “suena bien”:

- libros y textos narrativos;
- documentación y manuales;
- interfaces de aplicaciones;
- instrucciones y procedimientos;
- textos donde la negación, el tiempo o los participantes importan.

También sirve para equipos técnicos que quieran una traducción auditable, pero
no necesitas saber programar para entender la idea o usar las herramientas
básicas.

## El problema que intenta resolver

Una traducción puede parecer correcta y aun así cambiar el significado:

```text
Alice pushed the rabbit
Alice was pushed by the rabbit
```

Las dos frases hablan de Alice y del conejo, pero intercambian quién empujó a
quién. Un traductor basado únicamente en palabras puede pasar por alto ese
cambio.

IntentLang comprueba, entre otras cosas:

- quién realiza la acción;
- quién o qué recibe la acción;
- negación y afirmación;
- tiempo verbal;
- aspecto: acción terminada, progresiva o iniciada;
- modalidad: obligación, posibilidad o imperativo;
- cantidades y cuantificadores;
- lugares, objetos y relaciones entre entidades.

Cuando no sabe algo, debe decirlo. `UNKNOWN` es un resultado válido; inventar
un significado no lo es.

## Cómo funciona

```text
Texto original
      ↓
Significado independiente del idioma
      ↓
Traducción al idioma destino
      ↓
Volver a analizar la traducción
      ↓
¿Sigue siendo el mismo significado?
```

La pieza central se llama `Meaning IR`: una representación del significado que
no depende de si el texto viene de un libro, un PDF, una interfaz o una base de
datos.

El formato original solo importa para extraer el texto. La traducción se juzga
por el significado.

## Resultado actual

El experimento inicial usa un corpus multilingüe basado en frases de *Alice's
Adventures in Wonderland* y casos sintéticos diseñados para probar fenómenos
concretos.

| Medición | Resultado |
|---|---:|
| Frases evaluadas | 100 |
| Idiomas | 4 |
| Variantes comprobadas | 400 |
| Variantes semánticamente correctas | 396 |
| Casos correctamente rechazados como desconocidos | 4 |
| Exactitud bruta | **99%** |
| Exactitud en casos que debían resolverse | **100%** |

Los idiomas actuales del experimento son inglés, español, japonés y chino.

Las cuatro variantes desconocidas contienen un verbo inventado —“blorps”,
“blorpea” y equivalentes—. IntentLang no intentó adivinar qué significan. Eso
es una victoria de seguridad, no un fallo de traducción.

Importante: este resultado todavía corresponde a un corpus controlado, no a la
traducción completa de un libro. El siguiente reto es ampliar el corpus con
capítulos, diálogos, referencias largas y ambigüedad narrativa.

## ¿Usa inteligencia artificial?

Puede hacerlo, pero no es obligatorio.

El camino principal intenta resolver y verificar de forma determinista. Un LLM
puede funcionar como un oráculo externo para revisar casos difíciles, pero no
es la autoridad final ni puede inventar el significado del sistema.

```text
IntentLang decide el significado
             ↓
LLM revisa una traducción difícil
             ↓
IntentLang compara la respuesta contra Meaning IR
```

El LLM debe devolver un veredicto mínimo, por ejemplo:

```json
{
  "verdict": "PASS",
  "changed_features": [],
  "reason": null,
  "confidence": 0.96
}
```

Se pueden usar Gemini y proveedores compatibles con la API de OpenAI. La
configuración intenta detectar el proveedor automáticamente y usa sus
endpoints conocidos sin pedirle al usuario que configure URLs técnicas.

## Privacidad de las API keys

La clave se guarda por defecto en el almacén seguro del sistema operativo:

- Windows: Credential Manager;
- macOS: Keychain;
- Linux: Secret Service/keyring.

IntentLang no guarda la clave en el repositorio, `.env`, el virtualenv, los
logs ni los reportes. También elimina patrones conocidos de claves antes de
enviar prompts o errores fuera del proceso.

Configurar el oráculo:

```bash
python -m pip install -e '.[security]'
intentlang oracle-config
intentlang oracle-status
```

Para CI o automatizaciones se puede usar `INTENTLANG_ORACLE_API_KEY`. Los
proveedores OpenAI-compatible poco comunes pueden necesitar un preset o una
URL específica; no existe una forma fiable de deducir cualquier endpoint solo
a partir de una clave.

## Cómo probarlo

### Linux y macOS

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
```

### Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

El virtualenv solo aísla las dependencias. No es un almacén de secretos.

El experimento semántico reproducible necesita los datos locales de WordNet:

```bash
python3 ci/download_wordnets.py --data-dir /tmp/intentlang-wn-data
WN_DATA_DIR=/tmp/intentlang-wn-data PYTHONPATH=src \
  python3 ci/run_semantic_benchmark.py \
  --output-dir /tmp/intentlang-benchmark
```

La suite completa se ejecuta así:

```bash
WN_DATA_DIR=/tmp/intentlang-wn-data \
PYTHONPATH=/tmp/intentlang-deps:src \
pytest -q -p no:cacheprovider
```

## Demo visual

IntentLang incluye una consola web local para ver la entrada y el significado
que el sistema entendió:

```bash
python web/server.py
```

Después abre <http://127.0.0.1:8765>.

La demo no ejecuta acciones peligrosas ni resuelve texto arbitrario sin el
servidor local de Python.

## Qué significa cada resultado

```text
RESOLVED   → el sistema encontró un significado único
AMBIGUOUS  → hay varias interpretaciones posibles
UNKNOWN    → no hay suficiente evidencia para interpretar
INCOMPLETE → falta información necesaria
```

Solo un significado `RESOLVED` puede continuar hacia una operación ejecutable.
Los demás estados se conservan como evidencia para que una persona decida o
para que el sistema amplíe su cobertura más adelante.

## Estado del proyecto

### Cerrado

- Meaning IR versionado e independiente del formato de entrada.
- Parser determinista para el corpus inicial.
- Realizador multilingüe con back-translation.
- Comparador semántico que ignora diferencias superficiales de redacción.
- Oráculo LLM opcional y proveedor-neutral.
- Almacenamiento de credenciales mediante keyring del sistema.
- Redacción centralizada de secretos.

### En expansión

- corpus de capítulos completos y textos largos;
- más idiomas y familias lingüísticas;
- diálogos, pronombres y referencias entre frases;
- conectores temporales y causalidad;
- comparación reproducible contra varios traductores externos;
- métricas por fenómeno semántico, no solo una puntuación global.

## Para desarrolladores

La arquitectura interna está organizada alrededor de estas piezas:

```text
Meaning IR
├── meaning_parser.py       interpreta texto conocido
├── meaning_realizer.py     genera una superficie destino
├── semantic_comparator.py  compara candidatos por significado
├── llm_oracle.py           consulta un juez externo opcional
└── sanitize.py             elimina secretos antes de salir
```

El proyecto mantiene separado el motor de traducción semántica del antiguo
Intent IR ejecutable. Una frase narrativa no se convierte automáticamente en
una acción del sistema.

## Licencia

MIT.

## De dónde viene

IntentLang nació como la continuación conceptual de
[JAJAJA](https://github.com/DannyBaanks/JAJAJA), un esolang cuyo alfabeto son
repeticiones de `ja`.

JAJAJA pregunta si una representación absurda puede conservar un contrato.
IntentLang pregunta si una representación humana puede conservar significado
sin obligarnos a aprender una representación artificial.
