"""
M3 — Materializer: translates IR messages to target locales.

This adapter sits on top of IntentLang's infrastructure but does NOT
force UI strings into IntentLang's verb-operand primitives. Instead it:

  1. Preserves placeholders, accelerators, technical tokens, brands
  2. Uses a dictionary-based approach for known UI terms
  3. Falls back to IntentLang's cross-lingual concept mapping for unknowns
  4. Respects context hints from M2 for homograph disambiguation

Usage:
    from materializer import materialize_locale, materialize_single
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from intentlang.translation_engine.ui_message_ir import UIMessageIR, build_ir_from_inventory


# ── Placeholder preservation ────────────────────────────────────────
PLACEHOLDER_RE = re.compile(
    r"\{\{[^}]+\}\}"
    r"|\{[^}]+\}"
    r"|%[sd]"
    r"|%\\(\\w+\\)s"
)


def _extract_placeholders(text: str) -> list[tuple[str, str]]:
    """Extract placeholders with their positions for reinsertion."""
    return [(m.group(), str(m.start())) for m in PLACEHOLDER_RE.finditer(text)]


def _protect_placeholders(text: str) -> tuple[str, dict[str, str]]:
    """Replace placeholders with tokens for safe translation."""
    tokens = {}
    counter = 0

    def replacer(m):
        nonlocal counter
        token = f"__PH{counter}__"
        tokens[token] = m.group()
        counter += 1
        return token

    protected = PLACEHOLDER_RE.sub(replacer, text)
    return protected, tokens


def _restore_placeholders(text: str, tokens: dict[str, str]) -> str:
    """Restore placeholders from tokens."""
    for token, original in tokens.items():
        text = text.replace(token, original)
    return text


# ── Accelerator preservation ────────────────────────────────────────
ACCELERATOR_RE = re.compile(r"&(\\w)")


def _protect_accelerators(text: str) -> tuple[str, dict[str, str]]:
    """Protect keyboard accelerators like &S, _S."""
    tokens = {}
    counter = 0

    def replacer(m):
        nonlocal counter
        token = f"__ACC{counter}__"
        tokens[token] = m.group()
        counter += 1
        return token

    protected = ACCELERATOR_RE.sub(replacer, text)
    return protected, tokens


# ── Technical token preservation ────────────────────────────────────
TECHNICAL_PATTERNS = [
    re.compile(r"\\b(?:MCP|OAuth|API|SDK|CLI|SSH|HTTP|HTTPS|URL|JSON|YAML|XML|HTML|CSS|JS|TS)\\b"),
    re.compile(r"\\b(?:React|Electron|Node|TypeScript|JavaScript|Python|Rust|Go)\\b"),
    re.compile(r"\\b(?:Git|GitHub|GitLab|npm|npx|yarn|pnpm)\\b"),
    re.compile(r"\\b(?:OpenAI|Anthropic|Claude|GPT|Gemini|Llama)\\b"),
    re.compile(r"\\b(?:Docker|Kubernetes|AWS|GCP|Azure)\\b"),
    re.compile(r"\\b(?:VSCode|VS Code|Cursor|Windsurf)\\b"),
    re.compile(r"\\b(?:Ada|Munder Difflin|munder-difflin)\\b"),
    re.compile(r"/[a-z]+"),  # slash commands
    re.compile(r"\\bV\\d+\\.\\d+\\.\\d+"),  # version strings
]


def _protect_technical(text: str) -> tuple[str, dict[str, str]]:
    """Protect technical tokens from translation."""
    tokens = {}
    counter = 0

    def replacer(m):
        nonlocal counter
        token = f"__TECH{counter}__"
        tokens[token] = m.group()
        counter += 1
        return token

    protected = text
    for pattern in TECHNICAL_PATTERNS:
        protected = pattern.sub(replacer, protected)

    return protected, tokens


# ── Dictionary-based translation ────────────────────────────────────
# Minimal dictionary for common UI terms. In production this would be
# a full locale file; here we demonstrate the mechanism.

UI_DICTIONARY: dict[str, dict[str, str]] = {
    "save": {"es": "guardar", "fr": "enregistrer", "de": "speichern", "ja": "保存", "zh": "保存"},
    "cancel": {"es": "cancelar", "fr": "annuler", "de": "abbrechen", "ja": "キャンセル", "zh": "取消"},
    "delete": {"es": "eliminar", "fr": "supprimer", "de": "löschen", "ja": "削除", "zh": "删除"},
    "close": {"es": "cerrar", "fr": "fermer", "de": "schließen", "ja": "閉じる", "zh": "关闭"},
    "open": {"es": "abrir", "fr": "ouvrir", "de": "öffnen", "ja": "開く", "zh": "打开"},
    "copy": {"es": "copiar", "fr": "copier", "de": "kopieren", "ja": "コピー", "zh": "复制"},
    "paste": {"es": "pegar", "fr": "coller", "de": "einfügen", "ja": "貼り付け", "zh": "粘贴"},
    "cut": {"es": "cortar", "fr": "couper", "de": "ausschneiden", "ja": "切り取り", "zh": "剪切"},
    "undo": {"es": "deshacer", "fr": "annuler", "de": "rückgängig", "ja": "元に戻す", "zh": "撤销"},
    "redo": {"es": "rehacer", "fr": "rétablir", "de": "wiederholen", "ja": "やり直す", "zh": "重做"},
    "back": {"es": "atrás", "fr": "retour", "de": "zurück", "ja": "戻る", "zh": "返回"},
    "next": {"es": "siguiente", "fr": "suivant", "de": "weiter", "ja": "次へ", "zh": "下一步"},
    "finish": {"es": "finalizar", "fr": "terminer", "de": "fertigstellen", "ja": "完了", "zh": "完成"},
    "on": {"es": "activado", "fr": "activé", "de": "ein", "ja": "オン", "zh": "开"},
    "off": {"es": "desactivado", "fr": "désactivé", "de": "aus", "ja": "オフ", "zh": "关"},
    "yes": {"es": "sí", "fr": "oui", "de": "ja", "ja": "はい", "zh": "是"},
    "no": {"es": "no", "fr": "non", "de": "nein", "ja": "いいえ", "zh": "否"},
    "ok": {"es": "aceptar", "fr": "ok", "de": "ok", "ja": "OK", "zh": "确定"},
    "search": {"es": "buscar", "fr": "rechercher", "de": "suchen", "ja": "検索", "zh": "搜索"},
    "settings": {"es": "configuración", "fr": "paramètres", "de": "einstellungen", "ja": "設定", "zh": "设置"},
    "loading": {"es": "cargando", "fr": "chargement", "de": "laden", "ja": "読み込み中", "zh": "加载中"},
    "error": {"es": "error", "fr": "erreur", "de": "fehler", "ja": "エラー", "zh": "错误"},
    "warning": {"es": "advertencia", "fr": "avertissement", "de": "warnung", "ja": "警告", "zh": "警告"},
    "success": {"es": "éxito", "fr": "succès", "de": "erfolg", "ja": "成功", "zh": "成功"},
    "file": {"es": "archivo", "fr": "fichier", "de": "datei", "ja": "ファイル", "zh": "文件"},
    "files": {"es": "archivos", "fr": "fichiers", "de": "dateien", "ja": "ファイル", "zh": "文件"},
    "folder": {"es": "carpeta", "fr": "dossier", "de": "ordner", "ja": "フォルダ", "zh": "文件夹"},
    "name": {"es": "nombre", "fr": "nom", "de": "name", "ja": "名前", "zh": "名称"},
    "description": {"es": "descripción", "fr": "description", "de": "beschreibung", "ja": "説明", "zh": "描述"},
    "type": {"es": "tipo", "fr": "type", "de": "typ", "ja": "タイプ", "zh": "类型"},
    "status": {"es": "estado", "fr": "état", "de": "status", "ja": "ステータス", "zh": "状态"},
    "enabled": {"es": "habilitado", "fr": "activé", "de": "aktiviert", "ja": "有効", "zh": "已启用"},
    "disabled": {"es": "deshabilitado", "fr": "désactivé", "de": "deaktiviert", "ja": "無効", "zh": "已禁用"},
    "add": {"es": "agregar", "fr": "ajouter", "de": "hinzufügen", "ja": "追加", "zh": "添加"},
    "remove": {"es": "quitar", "fr": "supprimer", "de": "entfernen", "ja": "削除", "zh": "移除"},
    "edit": {"es": "editar", "fr": "modifier", "de": "bearbeiten", "ja": "編集", "zh": "编辑"},
    "view": {"es": "ver", "fr": "voir", "de": "anzeigen", "ja": "表示", "zh": "查看"},
    "help": {"es": "ayuda", "fr": "aide", "de": "hilfe", "ja": "ヘルプ", "zh": "帮助"},
    "about": {"es": "acerca de", "fr": "à propos", "de": "über", "ja": "バージョン情報", "zh": "关于"},
    "version": {"es": "versión", "fr": "version", "de": "version", "ja": "バージョン", "zh": "版本"},
    "tokens": {"es": "tokens", "fr": "jetons", "de": "token", "ja": "トークン", "zh": "令牌"},
    "agent": {"es": "agente", "fr": "agent", "de": "agent", "ja": "エージェント", "zh": "代理"},
    "command": {"es": "comando", "fr": "commande", "de": "befehl", "ja": "コマンド", "zh": "命令"},
    "skill": {"es": "habilidad", "fr": "compétence", "de": "fähigkeit", "ja": "スキル", "zh": "技能"},
    "thread": {"es": "hilo", "fr": "fil", "de": "thread", "ja": "スレッド", "zh": "线程"},
    "memory": {"es": "memoria", "fr": "mémoire", "de": "speicher", "ja": "メモリ", "zh": "内存"},
    "webhook": {"es": "webhook", "fr": "webhook", "de": "webhook", "ja": "Webhook", "zh": "Webhook"},
    "schedule": {"es": "horario", "fr": "planification", "de": "zeitplan", "ja": "スケジュール", "zh": "计划"},
    "queue": {"es": "cola", "fr": "file", "de": "warteschlange", "ja": "キュー", "zh": "队列"},
    "integration": {"es": "integración", "fr": "intégration", "de": "integration", "ja": "統合", "zh": "集成"},
    "worker": {"es": "trabajador", "fr": "worker", "de": "worker", "ja": "ワーカー", "zh": "工作器"},
    "git": {"es": "git", "fr": "git", "de": "git", "ja": "Git", "zh": "Git"},
    "badge": {"es": "insignia", "fr": "badge", "de": "abzeichen", "ja": "バッジ", "zh": "徽章"},
    "office": {"es": "oficina", "fr": "bureau", "de": "büro", "ja": "オフィス", "zh": "办公"},
    "kanban": {"es": "kanban", "fr": "kanban", "de": "kanban", "ja": "カンバン", "zh": "看板"},
    "send": {"es": "enviar", "fr": "envoyer", "de": "senden", "ja": "送信", "zh": "发送"},
    "submit": {"es": "enviar", "fr": "soumettre", "de": "absenden", "ja": "送信", "zh": "提交"},
    "confirm": {"es": "confirmar", "fr": "confirmer", "de": "bestätigen", "ja": "確認", "zh": "确认"},
    "approve": {"es": "aprobar", "fr": "approuver", "de": "genehmigen", "ja": "承認", "zh": "批准"},
    "reject": {"es": "rechazar", "fr": "rejeter", "de": "ablehnen", "ja": "却下", "zh": "拒绝"},
    "connect": {"es": "conectar", "fr": "connecter", "de": "verbinden", "ja": "接続", "zh": "连接"},
    "disconnect": {"es": "desconectar", "fr": "déconnecter", "de": "trennen", "ja": "切断", "zh": "断开"},
    "enable": {"es": "habilitar", "fr": "activer", "de": "aktivieren", "ja": "有効にする", "zh": "启用"},
    "disable": {"es": "deshabilitar", "fr": "désactiver", "de": "deaktivieren", "ja": "無効にする", "zh": "禁用"},
    "start": {"es": "iniciar", "fr": "démarrer", "de": "starten", "ja": "開始", "zh": "开始"},
    "stop": {"es": "detener", "fr": "arrêter", "de": "stoppen", "ja": "停止", "zh": "停止"},
    "pause": {"es": "pausar", "fr": "pause", "de": "pausieren", "ja": "一時停止", "zh": "暂停"},
    "resume": {"es": "reanudar", "fr": "reprendre", "de": "fortsetzen", "ja": "再開", "zh": "继续"},
    "retry": {"es": "reintentar", "fr": "réessayer", "de": "erneut versuchen", "ja": "再試行", "zh": "重试"},
    "upload": {"es": "subir", "fr": "téléverser", "de": "hochladen", "ja": "アップロード", "zh": "上传"},
    "download": {"es": "descargar", "fr": "télécharger", "de": "herunterladen", "ja": "ダウンロード", "zh": "下载"},
    "export": {"es": "exportar", "fr": "exporter", "de": "exportieren", "ja": "エクスポート", "zh": "导出"},
    "import": {"es": "importar", "fr": "importer", "de": "importieren", "ja": "インポート", "zh": "导入"},
    "share": {"es": "compartir", "fr": "partager", "de": "teilen", "ja": "共有", "zh": "分享"},
    "filter": {"es": "filtrar", "fr": "filtrer", "de": "filtern", "ja": "フィルター", "zh": "筛选"},
    "refresh": {"es": "actualizar", "fr": "actualiser", "de": "aktualisieren", "ja": "更新", "zh": "刷新"},
    "reset": {"es": "restablecer", "fr": "réinitialiser", "de": "zurücksetzen", "ja": "リセット", "zh": "重置"},
    "apply": {"es": "aplicar", "fr": "appliquer", "de": "anwenden", "ja": "適用", "zh": "应用"},
    "update": {"es": "actualizar", "fr": "mettre à jour", "de": "aktualisieren", "ja": "更新", "zh": "更新"},
    "install": {"es": "instalar", "fr": "installer", "de": "installieren", "ja": "インストール", "zh": "安装"},
    "uninstall": {"es": "desinstalar", "fr": "désinstaller", "de": "deinstallieren", "ja": "アンインストール", "zh": "卸载"},
    "create": {"es": "crear", "fr": "créer", "de": "erstellen", "ja": "作成", "zh": "创建"},
    "rename": {"es": "renombrar", "fr": "renommer", "de": "umbenennen", "ja": "名前変更", "zh": "重命名"},
    "move": {"es": "mover", "fr": "déplacer", "de": "verschieben", "ja": "移動", "zh": "移动"},
    "left": {"es": "izquierda", "fr": "gauche", "de": "links", "ja": "左", "zh": "左"},
    "right": {"es": "derecha", "fr": "droite", "de": "rechts", "ja": "右", "zh": "右"},
    "top": {"es": "arriba", "fr": "haut", "de": "oben", "ja": "上", "zh": "上"},
    "bottom": {"es": "abajo", "fr": "bas", "de": "unten", "ja": "下", "zh": "下"},
    "center": {"es": "centro", "fr": "centre", "de": "mitte", "ja": "中央", "zh": "居中"},
    "now": {"es": "ahora", "fr": "maintenant", "de": "jetzt", "ja": "今", "zh": "现在"},
    "later": {"es": "después", "fr": "plus tard", "de": "später", "ja": "後で", "zh": "稍后"},
    "always": {"es": "siempre", "fr": "toujours", "de": "immer", "ja": "常に", "zh": "始终"},
    "never": {"es": "nunca", "fr": "jamais", "de": "niemals", "ja": "決して", "zh": "从不"},
    "auto": {"es": "automático", "fr": "automatique", "de": "automatisch", "ja": "自動", "zh": "自动"},
    "manual": {"es": "manual", "fr": "manuel", "de": "manuell", "ja": "手動", "zh": "手动"},
    "all": {"es": "todos", "fr": "tous", "de": "alle", "ja": "すべて", "zh": "全部"},
    "none": {"es": "ninguno", "fr": "aucun", "de": "keine", "ja": "なし", "zh": "无"},
    "some": {"es": "algunos", "fr": "quelques", "de": "einige", "ja": "一部", "zh": "部分"},
    "more": {"es": "más", "fr": "plus", "de": "mehr", "ja": "もっと", "zh": "更多"},
    "less": {"es": "menos", "fr": "moins", "de": "weniger", "ja": "少なく", "zh": "更少"},
    "new": {"es": "nuevo", "fr": "nouveau", "de": "neu", "ja": "新しい", "zh": "新建"},
    "old": {"es": "antiguo", "fr": "ancien", "de": "alt", "ja": "古い", "zh": "旧"},
    "first": {"es": "primero", "fr": "premier", "de": "erste", "ja": "最初", "zh": "第一"},
    "last": {"es": "último", "fr": "dernier", "de": "letzte", "ja": "最後", "zh": "最后"},
    "previous": {"es": "anterior", "fr": "précédent", "de": "vorherige", "ja": "前", "zh": "上一个"},
    "required": {"es": "requerido", "fr": "requis", "de": "erforderlich", "ja": "必須", "zh": "必填"},
    "optional": {"es": "opcional", "fr": "optionnel", "de": "optional", "ja": "オプション", "zh": "可选"},
    "advanced": {"es": "avanzado", "fr": "avancé", "de": "erweitert", "ja": "詳細", "zh": "高级"},
    "basic": {"es": "básico", "fr": "basique", "de": "einfach", "ja": "基本", "zh": "基本"},
    "custom": {"es": "personalizado", "fr": "personnalisé", "de": "benutzerdefiniert", "ja": "カスタム", "zh": "自定义"},
    "default": {"es": "predeterminado", "fr": "par défaut", "de": "standard", "ja": "デフォルト", "zh": "默认"},
    "global": {"es": "global", "fr": "global", "de": "global", "ja": "グローバル", "zh": "全局"},
    "local": {"es": "local", "fr": "local", "de": "lokal", "ja": "ローカル", "zh": "本地"},
    "remote": {"es": "remoto", "fr": "distant", "de": "extern", "ja": "リモート", "zh": "远程"},
    "internal": {"es": "interno", "fr": "interne", "de": "intern", "ja": "内部", "zh": "内部"},
    "external": {"es": "externo", "fr": "externe", "de": "extern", "ja": "外部", "zh": "外部"},
    "public": {"es": "público", "fr": "public", "de": "öffentlich", "ja": "公開", "zh": "公开"},
    "private": {"es": "privado", "fr": "privé", "de": "privat", "ja": "非公開", "zh": "私有"},
}


def _translate_word(word: str, target_lang: str, context: Optional[str] = None) -> str:
    """Translate a single word using dictionary + context."""
    word_lower = word.lower()

    # Check dictionary
    if word_lower in UI_DICTIONARY:
        translations = UI_DICTIONARY[word_lower]
        if target_lang in translations:
            return translations[target_lang]

    # No translation found — return original
    return word


def materialize_single(
    msg: UIMessageIR,
    target_lang: str,
    dictionary: Optional[dict] = None,
) -> str:
    """Translate a single IR message to a target language.

    Strategy:
      - Passthrough: return as-is
      - Single-word: dictionary lookup
      - Short phrase (<=3 words): dictionary lookup per word
      - Longer: mark with [NEEDS_REVIEW] prefix, return original
      - Placeholders, accelerators, technical tokens always preserved
    """
    if msg.passthrough:
        return msg.value

    text = msg.value
    words = text.strip().split()
    word_count = len(words)

    # Phase 1: protect special tokens
    protected, ph_tokens = _protect_placeholders(text)
    protected, acc_tokens = _protect_accelerators(protected)
    protected, tech_tokens = _protect_technical(protected)

    # Phase 2: decide strategy by length
    if word_count == 1:
        # Single word — dictionary lookup
        result = _translate_word(words[0].lower(), target_lang, msg.section)
    elif word_count <= 3:
        # Short phrase — word-by-word with dictionary
        result = _translate_phrase(protected, target_lang, msg.section)
    else:
        # Long phrase — needs human/LLM review
        result = "[NEEDS_REVIEW] " + text

    # Phase 3: restore tokens
    result = _restore_placeholders(result, ph_tokens)
    result = _restore_placeholders(result, acc_tokens)
    result = _restore_placeholders(result, tech_tokens)

    return result


def _translate_phrase(text: str, target_lang: str, section: str) -> str:
    """Translate a short phrase word-by-word with dictionary."""
    words = text.split()
    translated_words = []

    for word in words:
        # Skip protected tokens
        if word.startswith("__PH") or word.startswith("__ACC") or word.startswith("__TECH"):
            translated_words.append(word)
            continue

        # Skip pure punctuation / whitespace
        stripped = word.strip(".,;:!?()[]{}'\"-")
        if not stripped:
            translated_words.append(word)
            continue

        # Translate
        translated = _translate_word(stripped, target_lang, section)
        translated_words.append(translated)

    return " ".join(translated_words)


def materialize_locale(
    inventory_path: str,
    target_lang: str,
    output_path: str,
    dictionary: Optional[dict] = None,
) -> dict:
    """Materialize a complete locale file from IR messages.

    Returns stats dict.
    """
    messages = build_ir_from_inventory(inventory_path)
    locale = {}
    translated = 0
    passthrough_count = 0
    untranslated = 0

    for msg in messages:
        if msg.passthrough:
            locale[msg.key] = msg.value
            passthrough_count += 1
        else:
            result = materialize_single(msg, target_lang, dictionary)
            locale[msg.key] = result
            if result != msg.value:
                translated += 1
            else:
                untranslated += 1

    # Write output
    # Rebuild nested structure from flat keys
    nested = _rebuild_nested(locale)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(nested, f, indent=2, ensure_ascii=False)

    return {
        "total": len(messages),
        "translated": translated,
        "untranslated": untranslated,
        "passthrough": passthrough_count,
        "target_lang": target_lang,
        "output": str(out_path),
    }


def _rebuild_nested(flat: dict) -> dict:
    """Rebuild nested dict from flat dotted keys."""
    nested = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = nested
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return nested
