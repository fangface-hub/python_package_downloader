"""Path utilities for application and data directories."""

import json
import os
import platform
import sys
from pathlib import Path

APP_NAME = "PythonPackageDownloader"
SETTING_FILENAME = "setting.json"
SETTING_DATA_DIR_KEY = "data_dir"


def get_app_dir() -> Path:
    """アプリケーションのルートディレクトリを取得.

    Get application root directory.

    PyInstallerでビルドされた場合は実行ファイルのディレクトリ、
    開発環境ではスクリプトのディレクトリを返します。

    Returns
    -------
    Path
        アプリケーションのルートディレクトリ
    """
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた場合
        return Path(sys.executable).parent
    else:
        # 通常のPythonスクリプトとして実行される場合
        return Path(__file__).parent


def get_data_dir() -> Path:
    """データディレクトリを取得 / Get data directory.

    プラットフォームごとに適切な場所を返します。
    Returns appropriate location for each platform:
    - Windows: %USERPROFILE%\\Documents\\PythonPackageDownloader
    - macOS: ~/Library/Application Support/PythonPackageDownloader
    - Linux: ~/.local/share/PythonPackageDownloader (XDG Base Directory)

    Returns
    -------
    Path
        データディレクトリ / Data directory path
    """
    if platform.system() == "Windows":
        return _get_windows_data_dir()

    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    # Linux and other Unix-like systems
    return Path(os.getenv("XDG_DATA_HOME",
                          Path.home() / ".local" / "share")) / APP_NAME


def _get_windows_data_dir() -> Path:
    """Windows向けデータディレクトリを取得する。"""
    default_dir = Path.home() / "Documents" / APP_NAME
    # ログ初期化前でも利用できるよう、まず既定ディレクトリを作成する。
    default_dir.mkdir(parents=True, exist_ok=True)

    setting_file = _get_windows_setting_file()
    saved_dir = _load_saved_data_dir(setting_file)
    if saved_dir is not None:
        return saved_dir

    selected_dir = _ask_user_for_data_dir(default_dir)
    if selected_dir is None:
        selected_dir = default_dir

    selected_dir.mkdir(parents=True, exist_ok=True)
    _save_data_dir(setting_file, selected_dir)
    return selected_dir


def _get_windows_setting_file() -> Path:
    """データディレクトリ設定ファイルのパスを返す。"""
    local_app_data = Path(os.getenv("LOCALAPPDATA", os.path.expanduser("~")))
    return local_app_data / SETTING_FILENAME


def _load_saved_data_dir(setting_file: Path) -> Path | None:
    """保存済みデータディレクトリを読み込む。"""
    if not setting_file.exists():
        return None
    try:
        with open(setting_file, "r", encoding="utf-8") as f:
            settings = json.load(f)
        data_dir_value = settings.get(SETTING_DATA_DIR_KEY)
        if isinstance(data_dir_value, str) and data_dir_value.strip():
            resolved = Path(data_dir_value).expanduser()
            resolved.mkdir(parents=True, exist_ok=True)
            return resolved
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return None


def _save_data_dir(setting_file: Path, data_dir: Path) -> None:
    """データディレクトリ設定を保存する。"""
    setting_file.parent.mkdir(parents=True, exist_ok=True)
    with open(setting_file, "w", encoding="utf-8") as f:
        json.dump(
            {SETTING_DATA_DIR_KEY: str(data_dir)},
            f,
            ensure_ascii=False,
            indent=4,
        )


def _ask_user_for_data_dir(default_dir: Path) -> Path | None:
    """初回起動時にデータディレクトリを確認する。"""
    root = None
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        use_default = messagebox.askyesno(
            title="PythonPackageDownloader",
            message=("データ保存先を設定します。\n\n"
                     f"既定の保存先:\n{default_dir}\n\n"
                     "このまま使用しますか？"),
            parent=root,
        )

        selected: Path | None = None
        if use_default:
            selected = default_dir
        else:
            chosen = filedialog.askdirectory(
                title="データ保存先フォルダを選択",
                initialdir=str(default_dir.parent),
                parent=root,
            )
            if chosen:
                selected = Path(chosen)

        return selected
    except (ImportError, OSError, RuntimeError) as e:
        _write_data_dir_prompt_error(default_dir, e)
        return default_dir
    except tk.TclError as e:
        _write_data_dir_prompt_error(default_dir, e)
        return default_dir
    finally:
        if root is not None:
            root.destroy()


def _write_data_dir_prompt_error(default_dir: Path,
                                 error: BaseException) -> None:
    """データディレクトリ確認ダイアログ失敗時の情報を書き出す。"""
    try:
        default_dir.mkdir(parents=True, exist_ok=True)
        log_path = default_dir / "data_dir_prompt_error.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{type(error).__name__}: {error}\n")
    except (OSError, RuntimeError, ValueError):
        return


def get_initial_dir_and_file(current_path: str,
                             fallback_dir: str = "") -> tuple[str, str]:
    """current_pathからinitial_dirとinitial_fileを判定.

    Parameters
    ----------
    current_path : str
        現在のパス（ファイルまたはディレクトリ）
    fallback_dir : str, optional
        パスが存在しない場合のフォールバックディレクトリ, by default ""

    Returns
    -------
    tuple[str, str]
        (initial_dir, initial_file) のタプル
    """
    if os.path.isfile(current_path):
        initial_dir = os.path.dirname(current_path)
        initial_file = os.path.basename(current_path)
    elif os.path.isdir(current_path):
        initial_dir = current_path
        initial_file = ""
    else:
        # パスが存在しない場合はフォールバックディレクトリを使用
        initial_dir = fallback_dir
        initial_file = ""

    return initial_dir, initial_file
