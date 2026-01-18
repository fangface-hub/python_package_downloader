"""Pythonパッケージを指定された条件でダウンロードするGUIアプリケーション."""

# -*- coding: utf-8 -*-
# このスクリプトは、指定されたOS、Pythonバージョン、
# ABIに基づいてPythonパッケージをダウンロードする
# GUIアプリケーションです。
# ユーザーは、OS、Pythonバージョン、パッケージリスト
# ファイルを指定し、ダウンロードを開始できます。

# アプリケーション用モジュールをインポート
import multiprocessing

import loggingex
import pathlibex
from main_window import MainWindow

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
    app = MainWindow()
    app.mainloop()
