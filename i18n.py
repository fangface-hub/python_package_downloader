"""国際化（i18n）サポートモジュール - JSON based."""

import json
import locale
from pathlib import Path

# localeディレクトリのパス
LOCALE_DIR = Path(__file__).parent / "locales"

# 翻訳データのキャッシュ
_translations = {}
_current_lang = None


def load_translations(lang):
    """指定された言語の翻訳データを読み込む.

    Parameters
    ----------
    lang : str
        言語コード（例: 'ja', 'en'）

    Returns
    -------
    dict
        翻訳辞書
    """
    json_file = LOCALE_DIR / f"{lang}.json"
    if json_file.exists():
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def setup_translation(lang=None):
    """翻訳を設定する.

    Parameters
    ----------
    lang : str, optional
        言語コード（例: 'ja', 'en'）。Noneの場合はシステムのロケールを使用。

    Returns
    -------
    str
        使用する言語コード
    """
    global _translations, _current_lang

    if lang is None:
        # システムのロケールを取得
        try:
            system_lang, encoding = locale.getlocale()
            if system_lang is None:
                system_lang = locale.getdefaultlocale()[0]
        except (ValueError, TypeError):
            system_lang = "en"

        # 言語コードを正規化（例: ja_JP -> ja）
        if system_lang:
            lang = system_lang.split("_")[0]
        else:
            lang = "en"

    # 翻訳データを読み込む
    _translations = load_translations(lang)
    _current_lang = lang

    # 翻訳データが空の場合は英語をフォールバック
    if not _translations and lang != "en":
        _translations = load_translations("en")
        _current_lang = "en"

    return _current_lang


def _(key, **kwargs):
    """翻訳関数.

    Parameters
    ----------
    key : str
        翻訳キー（英語）
    **kwargs : dict
        フォーマット用の引数

    Returns
    -------
    str
        翻訳された文字列
    """
    text = _translations.get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def get_available_languages():
    """利用可能な言語のリストを取得する.

    Returns
    -------
    list[str]
        利用可能な言語コードのリスト
    """
    languages = []

    if not LOCALE_DIR.exists():
        return languages

    for json_file in LOCALE_DIR.glob("*.json"):
        languages.append(json_file.stem)

    return languages


def set_language(lang):
    """言語を変更する.

    Parameters
    ----------
    lang : str
        言語コード（例: 'ja', 'en'）

    Returns
    -------
    str
        設定された言語コード
    """
    return setup_translation(lang)


def get_current_language():
    """現在の言語コードを取得する.

    Returns
    -------
    str
        現在の言語コード
    """
    return _current_lang


def get_language_name(lang_code: str) -> str:
    """指定された言語コードの言語名を取得する.

    Parameters
    ----------
    lang_code : str
        言語コード（例: 'ja', 'en'）

    Returns
    -------
    str
        言語名（例: '日本語 (Japanese)', 'English'）
    """
    global _translations, _current_language

    # 指定された言語の翻訳データを読み込む
    locale_dir = Path(__file__).parent / "locales"
    locale_file = locale_dir / f"{lang_code}.json"

    if locale_file.exists():
        with open(locale_file, "r", encoding="utf-8") as f:
            translations = json.load(f)
            return translations.get("language_name", lang_code)

    return lang_code


# 初期化
setup_translation()
