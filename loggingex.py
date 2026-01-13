#! python3
"""loggingの拡張."""
import atexit
import json
import os
import sys
from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Formatter,
    Handler,
    Logger,
    StreamHandler,
    getLogger,
)
from logging.handlers import RotatingFileHandler

from pathlibex import get_data_dir

DEFAULT_CONFIG_PATH = "loggingex_config.json"

LOG_LEVELS = {
    "DEBUG": DEBUG,
    "INFO": INFO,
    "WARNING": WARNING,
    "ERROR": ERROR,
    "CRITICAL": CRITICAL,
}

# ログ出力先ディレクトリ（デフォルトはデータディレクトリ配下のlog）
_log_dir = get_data_dir() / "log"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_config = {"log_dir": _log_dir}


def set_log_directory() -> None:
    """
    ログ出力先ディレクトリを設定.

    データディレクトリ配下のlogディレクトリに設定します。

    Returns
    -------
    None.
    """
    _log_config["log_dir"] = get_data_dir() / "log"
    # ディレクトリが存在しない場合は作成
    _log_config["log_dir"].mkdir(parents=True, exist_ok=True)


def cleanup_logger(logger: Logger) -> None:
    """
    loggerハンドラのクリーンアップ.

    Parameters
    ----------
    logger : Logger
        ロガー.

    Returns
    -------
    None.

    """
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)


def generate_log_formatter() -> Formatter:
    """
    Formatter生成.

    Returns
    -------
    Formatter
        Formatterのインスタンス.

    """
    return Formatter(" - ".join([
        " %(asctime)s",
        "%(filename)s:%(lineno)d",
        "%(funcName)s",
        "%(levelname)s",
        "%(message)s",
    ]))


def generate_log_filepath(filepath: str) -> str:
    """
    ログファイルパス生成.

    Parameters
    ----------
    filepath : str
        スクリプトのファイルパス.

    Returns
    -------
    str
        ログファイルのパス.

    """
    log_filename = ".".join(
        [os.path.splitext(os.path.basename(filepath))[0], "log"])
    return str(_log_config["log_dir"] / log_filename)


def generate_logger(
    name: str,
    debug: bool,
    filepath: str,
    config_path: str = DEFAULT_CONFIG_PATH,
) -> Logger:
    """
    Logger生成.

    Parameters
    ----------
    name : str
        呼び出し元の __name__ .
    debug : bool
        呼び出し元の __debug__ .
    filepath : str
        呼び出し元の __file__.
    config_path : str, optional
        ログ設定ファイルのパス, by default DEFAULT_CONFIG_PATH.

    Returns
    -------
    Logger
        Loggerのインスタンス.
    """
    ret = getLogger(name)
    fmt = generate_log_formatter()

    # 設定ファイルからログレベルと有効状態を取得
    try:
        config = load_logging_config(config_path)
        module_config = config.get(name, {})
        log_level_str = module_config.get("level", "INFO").upper()
        log_level = LOG_LEVELS.get(log_level_str, INFO)
        enabled = module_config.get("enabled", True)
        enabled_filehandler = module_config.get("enabled_filehandler", True)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log_level = INFO
        enabled = True
        enabled_filehandler = module_config.get("enabled_filehandler", True)
        print(f"ログ設定の読み込みに失敗しました: {e}")

    # ログが無効化されている場合、ダミーハンドラーを設定して無効化
    if not enabled:
        ret.disabled = True
        return ret

    # ログレベルを設定
    ret.setLevel(DEBUG if debug else log_level)

    if enabled_filehandler:
        # ファイルハンドラー
        filehandler = RotatingFileHandler(
            filename=generate_log_filepath(filepath),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8")
        filehandler.setFormatter(fmt)
        filehandler.setLevel(log_level)
        ret.addHandler(filehandler)

    # ストリームハンドラー
    streamhandler = StreamHandler()
    streamhandler.setFormatter(fmt)
    streamhandler.setStream(stream=sys.stdout)
    streamhandler.setLevel(log_level)
    ret.addHandler(streamhandler)

    atexit.register(cleanup_logger, ret)
    return ret


def set_init_logfile(config_path: str = DEFAULT_CONFIG_PATH) -> None:
    """
    初期化ログファイル設定.

    Parameters
    ----------
    config_path : str, optional
        ログ設定ファイルのパス, by default DEFAULT_CONFIG_PATH.

    Returns
    -------
    None
        なし.

    """
    config = load_logging_config(config_path)
    for key, value in config.items():
        logfilename = generate_log_filepath(key)
        # 有効であればファイルを作成
        if (value.get("enabled", False)
                and value.get("enabled_filehandler", False)
                and os.path.exists(logfilename)):
            with open(logfilename, "w", encoding="utf-8") as f:
                f.write("")
            continue
        # 無効であればファイルを削除
        if (not value.get("enabled", False) or not value.get(
                "enabled_filehandler", False)) and os.path.exists(logfilename):
            os.remove(logfilename)
            continue


def set_logger_handler(name: str, handler: Handler = None) -> None:
    """
    ログハンドラー設定.

    Parameters
    ----------
    name : str
        対象のファイル名.
    handler : Handler, optional
        出力先ハンドラ. The default is None.

    Returns
    -------
    None
        なし.

    """
    logger = getLogger(name)
    if handler:
        logger.addHandler(handler)


def set_logger_level(name: str, log_level: int = ERROR) -> None:
    """
    ログレベル設定.

    Parameters
    ----------
    name : str
        対象のファイル名.
    log_level : int, optional
        ログレベル. The default is ERROR.

    Returns
    -------
    None
        なし.

    """
    logger = getLogger(name)
    logger.setLevel(log_level)


def load_logging_config(config_path: str) -> dict:
    """
    ログ設定をJSONファイルから読み込む。

    Parameters
    ----------
    config_path : str
        設定ファイルのパス。

    Returns
    -------
    dict
        ログ設定の辞書。
    """
    if not os.path.exists(config_path):
        # 設定ファイルが存在しない場合は空の辞書を返す
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
