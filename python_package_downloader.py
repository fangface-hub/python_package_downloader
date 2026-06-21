"""Pythonパッケージを指定された条件でダウンロードするGUIアプリケーション."""

# -*- coding: utf-8 -*-
# このスクリプトは、指定されたOS、Pythonバージョン、
# ABIに基づいてPythonパッケージをダウンロードする
# GUIアプリケーションです。
# ユーザーは、OS、Pythonバージョン、パッケージリスト
# ファイルを指定し、ダウンロードを開始できます。

# アプリケーション用モジュールをインポート
import datetime
import multiprocessing
import platform
import sys
import traceback
from pathlib import Path

import loggingex
import pathlibex


def _write_bootstrap_error(error: BaseException) -> None:
    """ロガー初期化前の例外を最低限ファイルに残す。"""
    try:
        if platform.system() == "Windows":
            data_dir = Path.home() / "Documents" / "PythonPackageDownloader"
        else:
            data_dir = pathlibex.get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        log_path = data_dir / "bootstrap_error.log"
        timestamp = datetime.datetime.now().isoformat(timespec="seconds")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {type(error).__name__}: {error}\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except (OSError, RuntimeError, ValueError):
        # 最後の砦なので、ここでは再送出しない。
        return


def _bootstrap_excepthook(exc_type, exc_value, exc_traceback) -> None:
    """未捕捉例外を必ずブートストラップログに残す。"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    try:
        formatted = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback))
        _write_bootstrap_error(RuntimeError(formatted))
    except (OSError, RuntimeError, ValueError, TypeError):
        return


sys.excepthook = _bootstrap_excepthook

# ログディレクトリ設定（他のモジュールのインポート後に実行）
loggingex.set_log_directory()

# PyInstallerビルド時のパス解決
SCRIPT_DIR = pathlibex.get_app_dir()

# データディレクトリ（プラットフォームごとに適切な場所を使用）
DATA_DIR = pathlibex.get_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ログ初期化
loggingex.set_init_logfile()
logger = loggingex.generate_logger(name=__name__,
                                   debug=__debug__,
                                   filepath=__file__)

if __name__ == "__main__":
    multiprocessing.freeze_support()  # 追加
    from main_window import MainWindow

    app = MainWindow()
    app.mainloop()
