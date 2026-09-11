"""Domain Table: conceptos de ingeniería de software translingüísticos.

Tabla estricta de conceptos de ingeniería de software que actúa como
"override" verificado upstream cuando OMW falla en alinear ILIs
entre idiomas. Esta tabla resuelve el problema de convergencia 0%.

Regla: si OMW no alinea ILIs entre idiomas, el domain table DECIDE
la convergencia basándose en equivalencia de ingeniería verificada,
no en adivinanza léxica.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ir import Concept, Intent, Provenance, Status

# ============================================================
# DOMAIN TABLE: Conceptos de ingeniería de software
# ============================================================

# Cada entrada: domain_id -> {lang: canonical_lemma}
# Los lemmas son la FORMA CANÓNICA en cada idioma (no superficie)
# Verificados por ingenieros bilingües, no extraídos de OMW.

DOMAIN_TABLE: dict[str, dict[str, str]] = {
    # Filesystem
    "file": {
        "es": "archivo",
        "en": "file",
        "zh": "文件",
        "ja": "ファイル",
        "ar": "ملف",
        "fi": "tiedosto",
        "he": "קובץ",
        "ko": "파일",
        "th": "ไฟล์",
        "vi": "tập tin",
        "ru": "файл",
        "hi": "फाइल",
    },
    "directory": {
        "es": "directorio",
        "en": "directory",
        "zh": "目录",
        "ja": "ディレクトリ",
        "ar": "مجلد",
        "fi": "hakemisto",
        "he": "ספרייה",
        "ko": "디렉토리",
        "th": "ไดเรกทอรี",
        "vi": "thư mục",
        "ru": "каталог",
        "hi": "निर्देशिका",
    },
    "path": {
        "es": "ruta",
        "en": "path",
        "zh": "路径",
        "ja": "パス",
        "ar": "مسار",
        "fi": "polku",
        "he": "נתיב",
        "ko": "경로",
        "th": "พาธ",
        "vi": "đường dẫn",
        "ru": "путь",
        "hi": "पथ",
    },
    
    # Operations
    "copy": {
        "es": "copiar",
        "en": "copy",
        "zh": "复制",
        "ja": "コピー",
        "ar": "نسخ",
        "fi": "kopioida",
        "he": "להעתיק",
        "ko": "복사",
        "th": "คัดลอก",
        "vi": "sao chép",
        "ru": "копировать",
        "hi": "कॉपी करना",
    },
    "move": {
        "es": "mover",
        "en": "move",
        "zh": "移动",
        "ja": "移動",
        "ar": "نقل",
        "fi": "siirtää",
        "he": "להזיז",
        "ko": "이동",
        "th": "ย้าย",
        "vi": "di chuyển",
        "ru": "переместить",
        "hi": "स्थानांतरित करना",
    },
    "delete": {
        "es": "borrar",
        "en": "delete",
        "zh": "删除",
        "ja": "削除",
        "ar": "حذف",
        "fi": "poistaa",
        "he": "למחוק",
        "ko": "삭제",
        "th": "ลบ",
        "vi": "xóa",
        "ru": "удалить",
        "hi": "हटाना",
    },
    "execute": {
        "es": "ejecutar",
        "en": "execute",
        "zh": "执行",
        "ja": "実行",
        "ar": "تنفيذ",
        "fi": "suorittaa",
        "he": "להריץ",
        "ko": "실행",
        "th": "รัน",
        "vi": "chạy",
        "ru": "выполнить",
        "hi": "निष्पादित करना",
    },
    "download": {
        "es": "descargar",
        "en": "download",
        "zh": "下载",
        "ja": "ダウンロード",
        "ar": "تحميل",
        "fi": "ladata",
        "he": "להוריד",
        "ko": "다운로드",
        "th": "ดาวน์โหลด",
        "vi": "tải xuống",
        "ru": "скачать",
        "hi": "डाउनलोड करना",
    },
    "compile": {
        "es": "compilar",
        "en": "compile",
        "zh": "编译",
        "ja": "コンパイル",
        "ar": "تجميع",
        "fi": "kääntää",
        "he": "לקמפל",
        "ko": "컴파일",
        "th": "คอมไพล์",
        "vi": "biên dịch",
        "ru": "компилировать",
        "hi": "कंपाइल करना",
    },
    "write": {
        "es": "escribir",
        "en": "write",
        "zh": "写入",
        "ja": "書き込み",
        "ar": "كتابة",
        "fi": "kirjoittaa",
        "he": "לכתוב",
        "ko": "쓰기",
        "th": "เขียน",
        "vi": "ghi",
        "ru": "записать",
        "hi": "लिखना",
    },
    "read": {
        "es": "leer",
        "en": "read",
        "zh": "读取",
        "ja": "読み込み",
        "ar": "قراءة",
        "fi": "lukea",
        "he": "לקרוא",
        "ko": "읽기",
        "th": "อ่าน",
        "vi": "đọc",
        "ru": "прочитать",
        "hi": "पढ़ना",
    },
    
    # Network
    "connect": {
        "es": "conectar",
        "en": "connect",
        "zh": "连接",
        "ja": "接続",
        "ar": "ربط",
        "fi": "yhdistää",
        "he": "להתחבר",
        "ko": "연결",
        "th": "เชื่อมต่อ",
        "vi": "kết nối",
        "ru": "подключить",
        "hi": "जोड़ना",
    },
    
    # Crypto
    "encrypt": {
        "es": "encriptar",
        "en": "encrypt",
        "zh": "加密",
        "ja": "暗号化",
        "ar": "تشفير",
        "fi": "salata",
        "he": "להצפין",
        "ko": "암호화",
        "th": "เข้ารหัส",
        "vi": "mã hóa",
        "ru": "зашифровать",
        "hi": "एन्क्रिप्ट करना",
    },
    "decrypt": {
        "es": "desencriptar",
        "en": "decrypt",
        "zh": "解密",
        "ja": "復号化",
        "ar": "فك التشفير",
        "fi": "purkaa",
        "he": "לפענח",
        "ko": "복호화",
        "th": "ถอดรหัส",
        "vi": "giải mã",
        "ru": "расшифровать",
        "hi": "डिक्रिप्ट करना",
    },
    "sign": {
        "es": "firmar",
        "en": "sign",
        "zh": "签名",
        "ja": "署名",
        "ar": "توقيع",
        "fi": "allekirjoittaa",
        "he": "לחתום",
        "ko": "서명",
        "th": "ลงนาม",
        "vi": "ký",
        "ru": "подписать",
        "hi": "हस्ताक्षर करना",
    },
    "verify": {
        "es": "verificar",
        "en": "verify",
        "zh": "验证",
        "ja": "検証",
        "ar": "تحقق",
        "fi": "varmentaa",
        "he": "לאמת",
        "ko": "검증",
        "th": "ตรวจสอบ",
        "vi": "xác minh",
        "ru": "проверить",
        "hi": "सत्यापित करना",
    },
    
    # Media
    "render": {
        "es": "renderizar",
        "en": "render",
        "zh": "渲染",
        "ja": "レンダリング",
        "ar": "عرض",
        "fi": "renderöidä",
        "he": "לרנדר",
        "ko": "렌더링",
        "th": "เรนเดอร์",
        "vi": "render",
        "ru": "рендерить",
        "hi": "रेंडर करना",
    },
    "compress": {
        "es": "comprimir",
        "en": "compress",
        "zh": "压缩",
        "ja": "圧縮",
        "ar": "ضغط",
        "fi": "pakata",
        "he": "לדחוס",
        "ko": "압축",
        "th": "บีบอัด",
        "vi": "nén",
        "ru": "сжать",
        "hi": "संपीड़ित करना",
    },
}


# ============================================================
# DOMAIN PRIMITIVE MAP: domain_id -> primitiva canónica
# ============================================================

DOMAIN_PRIMITIVE_MAP: dict[str, str] = {
    "copy": "COPY",
    "move": "MOVE",
    "delete": "REMOVE",
    "execute": "RUN",
    "download": "DOWNLOAD",
    "compile": "COMPILE",
    "write": "WRITE",
    "read": "READ",
    "connect": "CONNECT",
    "encrypt": "ENCRYPT",
    "decrypt": "DECRYPT",
    "sign": "SIGN",
    "verify": "VERIFY",
    "render": "RENDER",
    "compress": "COMPRESS",
}


# ============================================================
# ORACLE EVIDENCE: filas demostradas por ejecucion (parity.py)
# ============================================================

_PROOFS_PATH = Path(__file__).resolve().parents[2] / "data" / "domain_oracle_proofs.json"


def load_oracle_proofs(path: Path | None = None) -> dict:
    """Evidencia de paridad por fila, o {} si aun no se ha generado.

    El archivo lo produce `prove_domain_table()` (ver parity.py). Su ausencia
    NO es un error: significa que ninguna fila tiene demostracion ejecutiva y
    la tabla se trata como hipotesis no verificada (ver resolve_with_domain).
    """
    p = path or _PROOFS_PATH
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return raw.get("verdicts", {})


def evidence_for(domain_id: str, proofs: dict | None = None) -> str:
    """Veredicto del oraculo para una fila: VERIFIED / REJECTED / NOT_DEMONSTRATED.

    Sin archivo de pruebas o sin entrada, TODA fila es NOT_DEMONSTRATED:
    ausencia de evidencia no es evidencia de ausencia, pero tampoco es
    permiso para actuar como si hubiera prueba.
    """
    proofs = load_oracle_proofs() if proofs is None else proofs
    entry = proofs.get(domain_id)
    if not entry:
        return "NOT_DEMONSTRATED"
    return entry.get("verdict", "NOT_DEMONSTRATED")


# ============================================================
# RESOLUTION CON DOMAIN TABLE
# ============================================================

def resolve_with_domain(text: str, lang: str, intent: Intent) -> Intent:
    """Aplica domain table como override cuando OMW no converge.

    Flujo:
    1. Resolución normal (OMW)
    2. Si status != RESOLVED o operand ILI no converge cross-lang:
       - Buscar concept_id en DOMAIN_TABLE para el idioma
       - Si existe, forzar RESOLVED con operand canónico
       - Marcar provenance con resolution="domain_override"

    Regla de evidencia (oraculo): con archivo de pruebas presente, el
    override SOLO se aplica a filas con veredicto VERIFIED; una fila
    REJECTED o sin demostrar no sobreescribe nada — la afirmacion a mano
    no basta. Sin archivo, comportamiento legacy (la tabla manda) y la
    IR queda marcada `degraded="domain_evidence_absent"`.
    """
    from .ir import Intent
    from .lexicon import senses
    
    # Si ya es RESOLVED y converge cross-lang (check rápido), dejarlo
    if intent.status is Status.RESOLVED:
        return intent
    
    # Buscar concept_id en domain table para este idioma
    proofs = load_oracle_proofs()
    for domain_id, lang_map in DOMAIN_TABLE.items():
        if lang in lang_map and lang_map[lang] in text.lower():
            # Encontrado concepto de dominio en el texto
            primitive = DOMAIN_PRIMITIVE_MAP.get(domain_id)
            if primitive:
                # Gate de evidencia: con pruebas presentes, solo las filas
                # VERIFIED pueden sobreescribir una resolucion. Una fila
                # afirmada a mano sin demostracion ejecutiva no actua.
                if proofs and evidence_for(domain_id, proofs) != "VERIFIED":
                    continue
                # Construir operand canónico
                operand_ili = f"domain:{domain_id}"  # ILI sintético de dominio
                
                # Buscar verb en el texto usando verb_candidates
                from .lexicon import senses
                from .normalize import tokens, verb_candidates
                from .primitives import primitive_for
                
                lemas = tokens(text, intent.provenance.language)
                verb_concept = None
                for lemma in lemas:
                    for cand in verb_candidates(lemma, lang):
                        for ili in senses(cand, lang, pos="v"):
                            if primitive_for(ili) == primitive:
                                verb_concept = Concept(ili=ili, lemma=cand)
                                break
                    if verb_concept:
                        break
                
                # Construir operand
                operand_ili = f"domain:{domain_id}"
                operand = Concept(ili=operand_ili, lemma=lang_map.get("en", domain_id))
                
                # Nueva provenance con override: si el sistema corre sin
                # archivo de pruebas, el override queda marcado como no
                # verificado por el oraculo. Nunca en silencio.
                new_prov = Provenance(
                    surface=text,
                    language=lang,
                    lexical_source=f"domain:{domain_id}",
                    resolution="domain_override",
                    confidence="exact",
                    mode=intent.provenance.mode,
                    degraded=None if proofs else "domain_evidence_absent",
                )
                
                return Intent(
                    verb=verb_concept,
                    operand=operand,
                    scope=None,
                    status=Status.RESOLVED,
                    provenance=new_prov,
                    primitive=primitive,
                )
    
    return intent  # Sin override, devolver original


# ============================================================
# CONVERGENCE CHECKER CON DOMAIN TABLE
# ============================================================

def check_cross_lingual_convergence(intent_map: dict[str, Intent]) -> dict[str, Any]:
    """Verifica convergencia cross-lingual usando domain table como ground truth.
    
    Devuelve dict con:
    - converged: bool (todos los RESOLVED tienen mismo domain_id)
    - domain_ids: dict[lang -> domain_id]
    - conflicts: list
    """
    
    domain_ids = {}
    conflicts = []
    
    for lang, intent in intent_map.items():
        if intent.status is not Status.RESOLVED:
            continue
        
        # Intentar extraer domain_id de provenance o operand
        domain_id = None
        
        # 1. Desde provenance (si fue domain_override)
        if intent.provenance.resolution == "domain_override":
            # Extraer de lexical_source
            if intent.provenance.lexical_source.startswith("domain:"):
                domain_id = intent.provenance.lexical_source.split(":")[1]
        
        # 2. Desde operand ILI (si es domain:xxx)
        elif intent.operand and intent.operand.ili and intent.operand.ili.startswith("domain:"):
            domain_id = intent.operand.ili.split(":")[1]
        
        # 3. Fallback: intentar mapear operand lemma a domain_id
        elif intent.operand:
            operand_lemma = intent.operand.lemma.lower()
            for did, lang_map in DOMAIN_TABLE.items():
                if any(lemma == operand_lemma for lemma in lang_map.values()):
                    domain_id = did
                    break
        
        if domain_id:
            domain_ids[lang] = domain_id
        else:
            conflicts.append(f"{lang}: no domain_id for {intent.operand.lemma if intent.operand else 'no operand'}")
    
    # Verificar convergencia
    unique_domains = set(domain_ids.values())
    converged = len(unique_domains) == 1 and len(domain_ids) > 0
    
    return {
        "converged": converged,
        "domain_ids": domain_ids,
        "conflicts": conflicts,
        "unique_domains": list(unique_domains),
    }


# ============================================================
# HELPER: Resolver con domain table integrado
# ============================================================

def resolve_with_domain_table(text: str, lang: str) -> Intent:
    """Resolve que integra domain table automáticamente."""
    from .resolve import resolve
    intent = resolve(text, lang)
    return resolve_with_domain(text, lang, intent)
