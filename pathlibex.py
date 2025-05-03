"""Path utilities for application and data directories."""

import os
import platform
import sys
from pathlib import Path


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
    - Windows: %LOCALAPPDATA%\\PythonPackageDownloader
    - macOS: ~/Library/Application Support/PythonPackageDownloader
    - Linux: ~/.local/share/PythonPackageDownloader (XDG Base Directory)

    Returns
    -------
    Path
        データディレクトリ / Data directory path
    """
    if platform.system() == "Windows":
        return Path(
            os.getenv("LOCALAPPDATA",
                      os.path.expanduser("~"))) / "PythonPackageDownloader"

    if platform.system() == "Darwin":
        return Path.home(
        ) / "Library" / "Application Support" / "PythonPackageDownloader"

    # Linux and other Unix-like systems
    return Path(os.getenv(
        "XDG_DATA_HOME",
        Path.home() / ".local" / "share")) / "PythonPackageDownloader"


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
