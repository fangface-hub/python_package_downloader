"""Pythonパッケージのダウンロードに関するユーティリティモジュール."""

# -*- coding: utf-8 -*-
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, parse

import pathlibex
from i18n import _
from signalex import run_command

try:
    from cryptography.fernet import Fernet

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

try:
    import requests
    from pypi_simple import PyPISimple

    PYPISIMPLE_AVAILABLE = True
except ImportError:
    PYPISIMPLE_AVAILABLE = False
from loggingex import generate_logger

logger = generate_logger(name=__name__, debug=__debug__, filepath=__file__)

# データディレクトリ
DATA_DIR = pathlibex.get_data_dir()

# 設定ファイルのパス
CONFIG_FILE = Path(__file__).parent / "config.json"


# 設定を読み込む
def load_config() -> dict:
    """設定ファイルから設定を読み込む."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # デフォルト設定
    return {
        "python_version_to_abi": {},
        "python_version_to_pattern": {},
        "os_to_platforms": {},
    }


_config = load_config()
PYTHON_VERSION_TO_ABI = _config.get("python_version_to_abi", {})
PYTHON_VERSION_TO_PATTERN = _config.get("python_version_to_pattern", {})
OS_TO_PLATFORMS = _config.get("os_to_platforms", {})

@dataclass
class DownloadConfig:
    """
    パッケージダウンロードの設定を保持するデータクラス.

    Attributes
    ----------
    os_name : str
        対象のOS名.
    python_version : str
        対象のPythonバージョン.
    package_list_file : str
        パッケージリストファイルのパス.
    dest_folder : str
        ダウンロード先フォルダのパス.
    include_source : bool, optional
        ソース形式を含めるかどうか (デフォルトはFalse).
    proxy : str, optional
        プロキシ設定 (例: "http://user:password@proxyserver:port").
    use_pip : bool, optional
        pipを使用するかどうか (デフォルトはTrue).
    pip_path : str, optional
        pipのパス (use_pipがTrueの場合に使用).
    """

    os_list: list[str] = field(default_factory=list)
    python_versions: list[str] = field(default_factory=list)
    package_list_file: str = None
    dest_folder: str = None
    include_source: bool = False
    include_deps: bool = False
    proxy: str = (
        None  # プロキシ設定（例: "http://user:password@proxyserver:port"）
    )
    use_pip: bool = True  # pipを使用するかどうか
    use_uv: bool = False  # uvを使用するかどうか
    pip_path: str = ""  # pipのパス（use_pipがTrueの場合に使用）
    progress_queue: object = None  # 進捗情報を送信するキュー
    dependency_level: int = 0  # 依存関係の階層レベル（0=メインパッケージ）
    # ダウンロード済み要件の履歴(依存関係の入れ子config間で共有される)
    history: list = field(default_factory=list)


@dataclass
class PackageInfo:
    """
    パッケージ情報を保持するデータクラス.

    Attributes
    ----------
    name : str
        パッケージ名.
    version : str
        バージョン.
    python_version : str
        Pythonバージョン.
    abi : str
        ABI.
    platform : str
        プラットフォーム.
    """

    name: str
    version: str
    python_version: str
    abi: str
    platform: str


@dataclass(frozen=True, eq=True)
class PackageRequirements:
    """
    パッケージの依存関係を保持するデータクラス.

    Attributes
    ----------
    package_name : str
        パッケージ名.
    version_condition : str
        バージョン条件 (例: ">=1.0.0").
    """

    package_name: str
    version_condition: str

    @property
    def requirement(self) -> str:
        """パッケージ名とバージョン条件を結合した文字列を返す."""
        return f"{self.package_name}{self.version_condition}"


def is_version_satisfied_in_history(package_requirements: PackageRequirements,
                                    history: list[PackageRequirements]) -> bool:
    """履歴の中に要件のバージョン条件を満たすものがあるかチェック.

    Parameters
    ----------
    package_requirements : PackageRequirements
        チェック対象のパッケージ要件.
    history : list[PackageRequirements]
        過去にダウンロードしたパッケージ要件のリスト.

    Returns
    -------
    bool
        バージョン条件を満たすものが履歴にある場合True.
    """
    if not package_requirements.version_condition:
        # バージョン条件がない場合は、同じパッケージ名があればTrue
        return any(hist.package_name == package_requirements.package_name
                   for hist in history)

    # バージョン条件がある場合
    for hist in history:
        if hist.package_name != package_requirements.package_name:
            continue

        if not hist.version_condition:
            # 履歴にバージョン条件がない場合はスキップ
            continue

        # 履歴のバージョンを抽出
        # version_condition は ">=1.0.0" や "==2.0.0" などの形式を想定
        hist_version_str = re.sub(r'[<>=!]+', '', hist.version_condition)
        if not hist_version_str:
            continue

        try:
            hist_version = parse(hist_version_str)
            # 要件のバージョン条件を SpecifierSet で解析
            specifier = SpecifierSet(package_requirements.version_condition)

            # 履歴のバージョンが要件の条件を満たすかチェック
            if hist_version in specifier:
                return True
        except (ValueError, TypeError) as e:
            # バージョン解析に失敗した場合はログに記録してスキップ
            logger.debug(
                "バージョン比較エラー: %s vs %s: %s",
                package_requirements.requirement,
                hist.requirement,
                e,
            )
            continue

    return False



def parse_package_condition(requirement: str) -> PackageRequirements | None:
    """パッケージ名とバージョン条件を抽出する.

    Parameters
    ----------
    text : str
        パッケージ名とバージョン条件の文字列.

    Returns
    -------
    PackageRequirements | None
        パッケージとバージョン条件.
    """
    text = re.sub(r"\(([^)]*)\)", r"\1", requirement.strip())
    if not text or text.startswith("#"):
        return None
    try:
        parsed = Requirement(text)
    except InvalidRequirement:
        return None
    return PackageRequirements(parsed.name, str(parsed.specifier))


def find_whl_package_info_list(folder: str,
                               package_name: str) -> list[PackageInfo]:
    """指定フォルダ内の .whl ファイルから指定パッケージの情報を取得"""
    package_info_list = []
    target = canonicalize_name(package_name)

    for file in os.listdir(folder):
        if not file.endswith(".whl"):
            continue
        package_info = get_package_info_from_whl(file)
        if canonicalize_name(package_info.name) == target:
            package_info_list.append(package_info)

    return package_info_list


def find_targz_package_info_list(folder: str,
                                 package_name: str) -> list[PackageInfo]:
    """指定フォルダ内の .tar.gz ファイルから指定パッケージの情報を取得"""
    package_info_list = []
    target = canonicalize_name(package_name)

    for file in os.listdir(folder):
        if not file.endswith(".tar.gz"):
            continue
        name, sep, version = file[:-len(".tar.gz")].rpartition("-")
        if not sep or canonicalize_name(name) != target:
            continue
        package_info_list.append(
            PackageInfo(
                name=package_name,
                version=version,
                python_version="none",
                abi="none",
                platform="none",
            ))

    return package_info_list


def version_satisfies(version: str, condition: str) -> bool:
    """バージョンがPEP 440の条件を満たすか判定する(条件なしはTrue)."""
    if not condition:
        return True
    try:
        return SpecifierSet(condition).contains(version, prereleases=True)
    except (InvalidSpecifier, InvalidVersion):
        return False


def check_whl_version(
    folder: str,
    requirement: PackageRequirements,
    platform: str,
    python_version: str,
) -> bool:
    """指定フォルダ内の .whl のバージョンを取得し、条件と比較する.

    Parameters
    ----------
    folder : str
        フォルダのパス.
    requirement : PackageRequirements
        パッケージの要件.
    platform : str
        プラットフォーム.
    python_version : str
        Pythonのバージョン.

    Returns
    -------
    bool
        条件に合致するバージョンが存在するかどうか.
    """
    ret = False
    package_info_list = find_whl_package_info_list(folder,
                                                   requirement.package_name)

    python_version_pattern = PYTHON_VERSION_TO_PATTERN.get(
        python_version, "none")

    for package_info in package_info_list:
        if (package_info.platform != "any"
                and platform not in package_info.platform):
            continue
        if not re.search(python_version_pattern, package_info.python_version):
            continue
        if version_satisfies(package_info.version,
                             requirement.version_condition):
            ret = True
            break
    logger.debug(
        "return=%s,folder=%s,requirement=%s,platform=%s,python_version=%s",
        ret,
        folder,
        requirement,
        platform,
        python_version,
    )
    logger.debug("package_info_list=%s", package_info_list)
    return ret


def check_targz(
    folder: str,
    requirement: PackageRequirements,
) -> bool:
    """指定フォルダ内の .tar.gz のバージョンを取得し、条件と比較する.

    Parameters
    ----------
    folder : str
        フォルダのパス.
    requirement : PackageRequirements
        パッケージの要件.

    Returns
    -------
    bool
        条件に合致するバージョンが存在するかどうか.
    """
    ret = False
    package_info_list = find_targz_package_info_list(folder,
                                                     requirement.package_name)
    for pachage_info in package_info_list:
        # バージョン番号が適用外はスキップ
        if version_satisfies(pachage_info.version,
                             requirement.version_condition):
            ret = True
            break
    logger.debug("return=%s,folder=%s,requirement=%s", ret, folder, requirement)
    return ret


def get_dependencies_from_whl(
        whl_file: str,
        history: list[PackageRequirements] | None = None
) -> list[PackageRequirements]:
    """.whlファイルから依存関係を取得する.

    Parameters
    ----------
    whl_file : str
        .whlファイルのパス.
    history : list[PackageRequirements], optional
        ダウンロード済みの要件。満たされている依存は除外する.

    Returns
    -------
    list[PackageRequirements]
        依存関係のリスト.
    """
    dependencies = []
    try:
        with zipfile.ZipFile(whl_file, "r") as z:
            metadata_files = [
                f for f in z.namelist()
                if f.endswith(".dist-info/METADATA")
            ]
            if not metadata_files:
                logger.info(
                    _("log_metadata_file_not_found", file=whl_file))
                return dependencies
            with z.open(metadata_files[0]) as metadata:
                lines = metadata.read().decode("utf-8", errors="replace").split("\n")
                for line in lines:
                    if not line.startswith("Requires-Dist:"):
                        continue
                    # extraのパッケージは無視する（正規表現をre.searchに修正）
                    if re.search(r"extra\s*==", line):
                        continue
                    dep_package = re.sub(r"(Requires-Dist:)([^;]*).*$", r"\2",
                                         line)
                    requirement = parse_package_condition("".join(
                        dep_package.split()))
                    if requirement is None:
                        continue
                    if is_version_satisfied_in_history(
                            requirement, history or []):
                        continue
                    dependencies.append(requirement)
    except (zipfile.BadZipFile, OSError, IOError) as e:
        logger.error(
            _("log_dependency_resolution_error",
              file=whl_file,
              error=e))
        return []
    logger.debug("whl_file=%s,dependencies=%s", whl_file, dependencies)
    return dependencies


def get_dependencies_from_targz(
        targz_file: str,
        history: list[PackageRequirements] | None = None
) -> list[PackageRequirements]:
    """.tar.gzファイルから依存関係を取得する.

    Parameters
    ----------
    targz_file : str
        .tar.gzファイルのパス.
    history : list[PackageRequirements], optional
        ダウンロード済みの要件。満たされている依存は除外する.

    Returns
    -------
    list[PackageRequirements]
        依存関係のリスト.
    """
    dependencies = []
    try:
        with tarfile.open(targz_file, "r:gz") as tar:
            pkg_info_files = [
                f for f in tar.getnames() if f.endswith("PKG-INFO")
            ]
            if not pkg_info_files:
                logger.info(
                    _("log_pkg_info_file_not_found", file=targz_file))
                return dependencies

            pkg_info = tar.extractfile(pkg_info_files[0]).read().decode(
                "utf-8", errors="replace")
            for line in pkg_info.split("\n"):
                if not line.startswith("Requires-Dist:"):
                    continue
                # extraのパッケージは無視する（正規表現をre.searchに修正）
                if re.search(r"extra\s*==", line):
                    continue
                dep_package = re.sub(r"(Requires-Dist:)([^;]*).*$", r"\2", line)
                requirement = parse_package_condition("".join(
                    dep_package.split()))
                if requirement is None:
                    continue
                if is_version_satisfied_in_history(
                        requirement, history or []):
                    continue
                dependencies.append(requirement)
    except (tarfile.TarError, OSError, IOError) as e:
        logger.error(
            _("log_dependency_resolution_error",
              file=targz_file,
              error=e))
        return []
    logger.debug("targz_file=%s,dependencies=%s", targz_file, dependencies)
    return dependencies


def get_package_info_from_whl(filename: str) -> PackageInfo:
    """ファイル名から情報を取得する.

    Parameters
    ----------
    filename : str
        ファイル名.

    Returns
    -------
    PackageInfo
        パッケージ情報.
    """
    package_name = "unknown"
    package_version = "unknown"
    python_version = "unknown"
    abi = "unknown"
    platform = "unknown"
    match = re.search(r"([^-]+)-([^-]+)-([^-]+)-([^-]+)-([^-]+)\.whl", filename)
    if match:
        package_name = match.group(1)
        package_version = match.group(2)
        python_version = match.group(3)
        abi = match.group(4)
        platform = match.group(5)
    return PackageInfo(
        name=package_name,
        version=package_version,
        python_version=python_version,
        abi=abi,
        platform=platform,
    )


def get_package_info_from_targz(filename: str) -> PackageInfo:
    """ファイル名から情報を取得する.

    Parameters
    ----------
    filename : str
        ファイル名.

    Returns
    -------
    PackageInfo
        パッケージ情報.
    """
    package_name = "unknown"
    package_version = "unknown"
    match = re.search(r"([^-]+)-([^-]+)\.tar\.gz", filename)
    if match:
        package_name = match.group(1)
        package_version = match.group(2)
    return PackageInfo(
        name=package_name,
        version=package_version,
        python_version="none",
        abi="none",
        platform="none",
    )


def _collect_new_files(before_files: set[str], config: DownloadConfig,
                       stop_event) -> bool:
    """新規ファイルがあればログ出力し、依存関係を取得してTrueを返す."""
    new_files = set(os.listdir(config.dest_folder)) - before_files
    if not new_files:
        return False
    logger.info(_("log_downloaded_successfully", files=new_files))
    if config.include_deps:
        download_dep_package(config=config,
                             filelist=new_files,
                             stop_event=stop_event)
    return True


def _download_with_cli(package_requirements: PackageRequirements,
                       config: DownloadConfig, stop_event, tool: str) -> None:
    """pipまたはuv(pip互換)でパッケージをダウンロードする.

    tool には "pip" または "uv" を指定する.
    """
    if stop_event and stop_event.is_set():
        return

    before_files = set(os.listdir(config.dest_folder))
    base_command: list[str] | None = None
    try:
        if tool == "uv":
            prefix = _resolve_uv_command_prefix(config.pip_path)
            subcommand = ["pip", "download"]
        else:
            prefix = _resolve_pip_command_prefix(config.pip_path)
            subcommand = ["download"]
        if not prefix:
            raise FileNotFoundError(f"利用可能な{tool}コマンドが見つかりません。"
                                    "設定またはPython環境を確認してください。")

        if tool == "uv" and not _supports_uv_pip_download(prefix):
            logger.warning(
                _("log_uv_pip_download_unsupported",
                  requirement=package_requirements))
            download_package_pip(package_requirements, config, stop_event)
            return

        base_command = prefix + subcommand + [package_requirements.requirement]
        if config.proxy:
            base_command.append(f"--proxy={config.proxy}")

        for os_name in config.os_list:
            platforms = OS_TO_PLATFORMS.get(os_name, [])
            if not platforms:
                logger.warning(
                    _("log_skipping_unsupported_os", os_name=os_name))
                continue
            for platform in platforms:
                for python_version in config.python_versions:
                    if stop_event and stop_event.is_set():
                        return
                    if check_whl_version(
                            folder=config.dest_folder,
                            requirement=package_requirements,
                            platform=platform,
                            python_version=python_version,
                    ):
                        continue
                    run_command(
                        base_command + [
                            "--only-binary=:all:",
                            f"--platform={platform}",
                            f"--python-version={python_version.replace('.', '')}",
                            f"--dest={config.dest_folder}",
                        ],
                        stderr_as_error=not config.include_source,
                    )
        if _collect_new_files(before_files, config, stop_event):
            return
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError) as e:
        # コマンド自体が実行できない場合は、ソース取得へフォールバックできない。
        if isinstance(e, (FileNotFoundError, OSError)) or base_command is None:
            logger.error(
                _("log_download_error",
                  requirement=package_requirements,
                  error=e))
            if PYPISIMPLE_AVAILABLE:
                logger.warning(
                    _("log_tool_unavailable_fallback",
                      tool=tool,
                      requirement=package_requirements))
                download_package_no_pip(package_requirements, config,
                                        stop_event)
            return
        if not config.include_source:
            logger.error(
                _("log_download_error",
                  requirement=package_requirements,
                  error=e))
            return

    if not config.include_source:
        logger.warning(
            _("log_download_failed_with_tool",
              tool=tool,
              requirement=package_requirements))
        return
    if check_targz(folder=config.dest_folder, requirement=package_requirements):
        logger.info(
            _("log_source_distribution_already_downloaded",
              requirement=package_requirements))
        return
    # ソース形式は依存解決なしで取得し、ビルド依存関係解決の失敗ログを抑える。
    try:
        run_command(
            base_command + [
                "--no-binary=:all:",
                "--no-deps",
                f"--dest={config.dest_folder}",
            ],
            stderr_as_error=False,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError):
        pass
    _collect_new_files(before_files, config, stop_event)


def download_package_pip(package_requirements: PackageRequirements,
                         config: DownloadConfig,
                         stop_event=None) -> None:
    """指定された条件でpipでパッケージをダウンロードする."""
    _download_with_cli(package_requirements, config, stop_event, "pip")


def download_package_uv(package_requirements: PackageRequirements,
                        config: DownloadConfig,
                        stop_event=None) -> None:
    """指定された条件でuv(pip互換)でパッケージをダウンロードする."""
    _download_with_cli(package_requirements, config, stop_event, "uv")


def _resolve_pip_command_prefix(configured_pip_path: str) -> list[str] | None:
    """利用可能なpip実行コマンドを解決する。"""
    candidates: list[list[str]] = []
    configured = configured_pip_path.strip() if configured_pip_path else ""
    if configured:
        candidates.append([configured])

        configured_path = Path(configured.strip('"'))
        configured_name = configured_path.name.lower()
        if configured_name.startswith("python"):
            candidates.append([str(configured_path), "-m", "pip"])
        elif configured_name.startswith("pip"):
            # 例: .../Scripts/pip.exe が指定された場合、
            # 対応する python.exe -m pip も候補に追加する。
            inferred_candidates = [
                configured_path.parent / "python.exe",
                configured_path.parent.parent / "python.exe",
            ]
            for inferred_python in inferred_candidates:
                if inferred_python.exists():
                    candidates.append([str(inferred_python), "-m", "pip"])

    # 開発実行時は現在のPython環境を最優先にする。
    if not getattr(sys, "frozen", False):
        candidates.append([sys.executable, "-m", "pip"])

    py_path = shutil.which("py")
    if py_path:
        candidates.append([py_path, "-m", "pip"])

    python_path = shutil.which("python")
    if python_path:
        candidates.append([python_path, "-m", "pip"])

    pip_path = shutil.which("pip")
    if pip_path:
        candidates.append([pip_path])

    pip3_path = shutil.which("pip3")
    if pip3_path:
        candidates.append([pip3_path])

    for candidate in candidates:
        if _is_working_command(candidate):
            return candidate

    return None


def _resolve_uv_command_prefix(configured_uv_path: str) -> list[str] | None:
    """利用可能なuv実行コマンドを解決する。"""
    candidates: list[list[str]] = []
    configured = configured_uv_path.strip() if configured_uv_path else ""
    if configured:
        configured_path = Path(configured.strip('"'))
        configured_name = configured_path.name.lower()
        if configured_name.startswith("uv"):
            candidates.append([str(configured_path)])
        elif configured_name.startswith("python"):
            candidates.append([str(configured_path), "-m", "uv"])
        elif configured_name.startswith("pip"):
            # 設定にpip実行ファイルが指定されている場合は、
            # 同じ環境のuv/python -m uvを候補として推測する。
            inferred_uv_candidates = [
                configured_path.parent / "uv.exe",
                configured_path.parent / "uv",
                configured_path.parent.parent / "uv.exe",
                configured_path.parent.parent / "uv",
            ]
            for inferred_uv in inferred_uv_candidates:
                if inferred_uv.exists():
                    candidates.append([str(inferred_uv)])

            inferred_python_candidates = [
                configured_path.parent / "python.exe",
                configured_path.parent.parent / "python.exe",
                configured_path.parent / "python",
                configured_path.parent.parent / "python",
            ]
            for inferred_python in inferred_python_candidates:
                if inferred_python.exists():
                    candidates.append([str(inferred_python), "-m", "uv"])

    if not getattr(sys, "frozen", False):
        candidates.append([sys.executable, "-m", "uv"])

    uv_path = shutil.which("uv")
    if uv_path:
        candidates.append([uv_path])

    for candidate in candidates:
        if _is_working_command(candidate):
            return candidate

    return None


def _supports_uv_pip_download(uv_command_prefix: list[str]) -> bool:
    """uvが`uv pip download`サブコマンドをサポートしているか判定する。"""
    try:
        probe = uv_command_prefix + ["pip", "download", "--help"]
        result = _run_subprocess_no_window(
            probe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _is_working_command(command_prefix: list[str]) -> bool:
    """コマンドが実行可能かを判定する。"""
    try:
        probe = command_prefix + ["--version"]
        result = _run_subprocess_no_window(
            probe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _run_subprocess_no_window(command: list[str],
                              **kwargs) -> subprocess.CompletedProcess:
    """Windowsではコンソールウィンドウを表示せずにsubprocess.runを実行する。"""
    if sys.platform == "win32":
        creationflags = kwargs.pop("creationflags", 0)
        kwargs["creationflags"] = (creationflags
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))

        startupinfo = kwargs.pop("startupinfo", None)
        if startupinfo is None:
            startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo

    check = kwargs.pop("check", False)
    return subprocess.run(command, check=check, **kwargs)


def _download_file(url: str, dest_folder: str) -> bool:
    """URLのファイルを保存する。既に存在する場合は何もせずFalseを返す."""
    filename = os.path.join(dest_folder, os.path.basename(url))
    if os.path.exists(filename):
        return False
    response = requests.get(url, stream=True, timeout=10)
    response.raise_for_status()
    with open(filename, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return True


def _select_latest_package(packages, requirement: PackageRequirements,
                           platform: str | None = None,
                           python_version: str | None = None):
    """条件に合う最新のwheel(platform指定なしの場合はsdist)を返す."""
    best, best_version = None, None
    pattern = PYTHON_VERSION_TO_PATTERN.get(python_version, "none")
    for package in packages:
        if getattr(package, "is_yanked", False):
            continue
        if platform is None:
            if not package.filename.endswith(".tar.gz"):
                continue
            info = get_package_info_from_targz(package.filename)
        else:
            if not package.filename.endswith(".whl"):
                continue
            info = get_package_info_from_whl(package.filename)
            if info.platform != "any" and platform not in info.platform:
                continue
            if not re.search(pattern, info.python_version):
                continue
        if not version_satisfies(info.version, requirement.version_condition):
            continue
        try:
            version = parse(info.version)
        except InvalidVersion:
            continue
        if best_version is None or version > best_version:
            best, best_version = package, version
    return best


def download_package_no_pip(package_requirements: PackageRequirements,
                            config: DownloadConfig,
                            stop_event=None) -> None:
    """PyPISimpleとrequestsを使用して1つのパッケージをダウンロードする.

    選択したOS×Pythonバージョンの組み合わせごとに、
    条件に合う最新のwheelを取得する.

    Parameters
    ----------
    package_requirements: PackageRequirements
        ダウンロードするパッケージの要件.
    config : DownloadConfig
        ダウンロード設定.
    stop_event : multiprocessing.Event, optional
        中止イベント.
    """
    if stop_event and stop_event.is_set():
        return

    logger.info(
        _("log_starting_download_for_package",
          package=package_requirements.package_name))
    before_files = set(os.listdir(config.dest_folder))
    try:
        pypi = PyPISimple()
        packages_info = pypi.get_project_page(package_requirements.package_name)
        if not packages_info:
            logger.warning(
                _("log_package_information_not_found",
                  requirement=package_requirements))
            return

        found = False
        for os_name in config.os_list:
            for platform in OS_TO_PLATFORMS.get(os_name, []):
                for python_version in config.python_versions:
                    if stop_event and stop_event.is_set():
                        return
                    package = _select_latest_package(packages_info.packages,
                                                     package_requirements,
                                                     platform, python_version)
                    if package is None:
                        continue
                    found = True
                    _download_file(package.url, config.dest_folder)

        if config.include_source and not found:
            if check_targz(folder=config.dest_folder,
                           requirement=package_requirements):
                logger.info(
                    _("log_source_distribution_already_downloaded",
                      requirement=package_requirements))
                return
            package = _select_latest_package(packages_info.packages,
                                             package_requirements)
            if package is not None:
                found = True
                _download_file(package.url, config.dest_folder)

        if not found:
            logger.warning(
                _("log_download_url_not_found",
                  requirement=package_requirements))
            return
        new_files = set(os.listdir(config.dest_folder)) - before_files
        if new_files:
            logger.info(_("log_download_completed", files=new_files))
            if config.include_deps:
                download_dep_package(config=config,
                                     filelist=new_files,
                                     stop_event=stop_event)
    except requests.exceptions.RequestException as e:
        logger.error(
            _("log_download_error",
              requirement=package_requirements,
              error=e))


def download_packages(config: DownloadConfig,
                      package_requirements_list: list[PackageRequirements],
                      stop_event=None) -> None:
    """パッケージをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    package_requirements_list: list[PackageRequirements]
        ダウンロードするパッケージのリスト.
    stop_event : multiprocessing.Event, optional
        中止イベント.
    """
    for i, package_requirements in enumerate(package_requirements_list, 1):
        if stop_event and stop_event.is_set():
            return

        if is_version_satisfied_in_history(package_requirements,
                                           config.history):
            continue
        config.history.append(package_requirements)
        logger.info(
            _("log_starting_download_for_package", package=package_requirements))

        # 依存関係パッケージのダウンロード進捗を通知
        if config.progress_queue:
            config.progress_queue.put({
                "status": "downloading_dependency",
                "current": i,
                "total": len(package_requirements_list),
                "package": package_requirements.package_name,
                "level": config.dependency_level
            })

        if config.use_uv:
            download_package_uv(package_requirements=package_requirements,
                                config=config,
                                stop_event=stop_event)
            continue
        if config.use_pip:
            download_package_pip(package_requirements=package_requirements,
                                 config=config,
                                 stop_event=stop_event)
            continue
        download_package_no_pip(package_requirements=package_requirements,
                                config=config,
                                stop_event=stop_event)


def download_dep_package(config: DownloadConfig,
                         filelist: list[str],
                         stop_event=None):
    """依存ファイルをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    filelist : list[str]
        ファイルリスト.
    stop_event : multiprocessing.Event, optional
        中止イベント.
    """
    if stop_event and stop_event.is_set():
        return

    package_requirements_list = []
    for file_ in filelist:
        if stop_event and stop_event.is_set():
            return

        file_path = os.path.join(config.dest_folder, file_)
        if file_.endswith(".tar.gz"):
            dependencies = get_dependencies_from_targz(
                targz_file=file_path, history=config.history)
            package_requirements_list.extend(dependencies)
            continue
        if file_.endswith(".whl"):
            dependencies = get_dependencies_from_whl(
                whl_file=file_path, history=config.history)
            package_requirements_list.extend(dependencies)
            continue

    # 依存関係のダウンロード開始を通知
    if package_requirements_list and config.progress_queue:
        config.progress_queue.put({
            "status": "downloading_dependencies",
            "count": len(package_requirements_list),
            "level": config.dependency_level
        })

    # 依存関係のダウンロード時に階層を進める
    nested_config = replace(config,
                            dependency_level=config.dependency_level + 1)

    download_packages(config=nested_config,
                      package_requirements_list=package_requirements_list,
                      stop_event=stop_event)

    # 依存関係のダウンロード完了を通知
    if package_requirements_list and config.progress_queue:
        config.progress_queue.put({
            "status": "dependency_complete",
            "level": config.dependency_level
        })


def extract_license_from_package(package_file: str, licenses_dir: str) -> None:
    """パッケージファイルからライセンスファイルを抽出する.

    Parameters
    ----------
    package_file : str
        パッケージファイルのパス (.whl または .tar.gz)
    licenses_dir : str
        ライセンスファイルの保存先ディレクトリ
    """
    package_path = Path(package_file)
    package_name = package_path.stem

    # .whlの場合、拡張子を2回削除（例: package-1.0.0-py3-none-any.whl）
    if package_file.endswith('.whl'):
        # パッケージ名とバージョンを抽出（最初のハイフンまで）
        parts = package_name.split('-')
        if len(parts) >= 2:
            base_name = f"{parts[0]}-{parts[1]}"
        else:
            base_name = package_name
    else:
        # .tar.gzなどの場合
        base_name = package_name.replace('.tar', '')

    def is_license(name: str) -> bool:
        # ファイル名がライセンス名で始まるものだけを対象にする
        return PurePosixPath(name).name.upper().startswith(
            ("LICENSE", "LICENCE", "COPYING"))

    contents: list[bytes] = []
    try:
        if package_file.endswith('.whl'):
            with zipfile.ZipFile(package_file, 'r') as zip_ref:
                # .dist-info内(licenses/等のサブフォルダを含む)を探す
                for name in zip_ref.namelist():
                    if '.dist-info/' in name and is_license(name):
                        contents.append(zip_ref.read(name))
        elif package_file.endswith(('.tar.gz', '.tgz')):
            with tarfile.open(package_file, 'r:gz') as tar_ref:
                for member in tar_ref.getmembers():
                    # 最上位フォルダ直下のみ(テストデータ等の誤検出を避ける)
                    if (member.isfile() and member.name.count('/') <= 1
                            and is_license(member.name)):
                        file_obj = tar_ref.extractfile(member)
                        if file_obj:
                            contents.append(file_obj.read())
    except (zipfile.BadZipFile, tarfile.TarError, OSError, IOError) as e:
        logger.error(
            _("log_extract_license_file_failed",
              file=package_file,
              error=e))
        return

    if not contents:
        logger.warning(
            _("log_license_file_not_found_in_package", file=package_file))
        return
    for index, content in enumerate(contents, 1):
        suffix = "" if index == 1 else f"_{index}"
        output_file = Path(licenses_dir) / f"{base_name}_LICENSE{suffix}.txt"
        output_file.write_bytes(content)
        logger.info(_("log_extracted_license_file", file=output_file))


def extract_licenses_from_directory(packages_dir: str) -> None:
    """ディレクトリ内のすべてのパッケージからライセンスを抽出する.

    Parameters
    ----------
    packages_dir : str
        パッケージファイルが格納されているディレクトリ
    """
    packages_path = Path(packages_dir)
    licenses_dir = packages_path / "LICENSES"
    licenses_dir.mkdir(exist_ok=True)

    logger.info(
        _("log_created_license_directory", directory=licenses_dir))

    # .whlと.tar.gzファイルを検索
    package_files = list(packages_path.glob("*.whl")) + list(
        packages_path.glob("*.tar.gz")) + list(packages_path.glob("*.tgz"))

    logger.info(
        _("log_extracting_licenses_from_package_files",
          count=len(package_files)))

    for package_file in package_files:
        extract_license_from_package(str(package_file), str(licenses_dir))

    logger.info(_("log_license_extraction_completed"))


def start_download(config: DownloadConfig, stop_event=None) -> None:
    """PyPISimpleとrequestsを使用してパッケージをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    """
    config.history.clear()
    os.makedirs(config.dest_folder, exist_ok=True)
    package_requirements_list = []
    with open(config.package_list_file, "r", encoding="utf-8") as file:
        for line_ in file.readlines():
            requirement = parse_package_condition("".join(line_.split()))
            if requirement is None:
                if line_.strip() and not line_.strip().startswith("#"):
                    logger.warning("Skipping unparsable requirement: %s",
                                   line_.strip())
                continue
            package_requirements_list.append(requirement)
    # ダウンロード処理
    if stop_event and stop_event.is_set():
        return  # 中止
    download_packages(config=config,
                      package_requirements_list=package_requirements_list,
                      stop_event=stop_event)

    # ダウンロード完了後、ライセンスファイルを抽出
    if stop_event and stop_event.is_set():
        return  # 中止
    extract_licenses_from_directory(config.dest_folder)


KEYRING_SERVICE = "python_package_downloader"
KEYRING_USERNAME = "settings_key"


def _generate_key_in_file() -> bytes:
    """暗号化キーをファイルから読み込む(なければ生成して保存する)."""
    key_file = DATA_DIR / "key.key"
    if key_file.exists():
        return key_file.read_bytes()
    key = Fernet.generate_key()
    key_file.write_bytes(key)
    return key


def generate_key() -> bytes:
    """暗号化キーを取得する.

    OSの資格情報ストア(keyring)を優先して使用する。keyringが使えない場合は
    DATA_DIRのkey.keyにフォールバックする。既存のkey.keyはkeyringへ移行する。
    """
    if not KEYRING_AVAILABLE:
        return _generate_key_in_file()
    key_file = DATA_DIR / "key.key"
    try:
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if stored:
            return stored.encode()
        key = (key_file.read_bytes()
               if key_file.exists() else Fernet.generate_key())
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key.decode())
        key_file.unlink(missing_ok=True)  # keyringへ移行済み
        return key
    except KeyringError as e:
        logger.warning("keyring unavailable, using key file: %s", e)
        return _generate_key_in_file()


def encrypt_password(password: str, key: bytes) -> str:
    """パスワードを暗号化する."""
    fernet = Fernet(key)
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str, key: bytes) -> str:
    """暗号化されたパスワードを復号化する."""
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_password.encode()).decode()


def save_settings(settings: dict) -> None:
    """設定をJSONファイルに保存する."""
    settings_copy = settings.copy()
    # 暗号化キーが有効な場合
    if CRYPTOGRAPHY_AVAILABLE:
        key = generate_key()
    else:
        key = None
    if CRYPTOGRAPHY_AVAILABLE:
        if settings_copy.get("proxy_password", "") != "":
            settings_copy["proxy_password"] = encrypt_password(
                settings_copy["proxy_password"], key)
        else:
            # proxy_passwordが設定されていない場合は削除
            if "proxy_password" in settings_copy:
                del settings_copy["proxy_password"]
    else:
        # cryptographyがインストールされていない場合は、パスワードを削除する
        if "proxy_password" in settings_copy:
            del settings_copy["proxy_password"]
    settings_file = DATA_DIR / "settings.json"
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings_copy, f, ensure_ascii=False, indent=4)


def load_settings() -> dict:
    """JSONファイルから設定を読み込む."""
    settings_file = DATA_DIR / "settings.json"
    if not settings_file.exists():
        return {}
    # 暗号化キーが有効な場合
    if CRYPTOGRAPHY_AVAILABLE:
        key = generate_key()
    else:
        key = None

    with open(settings_file, "r", encoding="utf-8") as f:
        settings = json.load(f)
    if "proxy_password" in settings:
        try:
            if key is None:
                raise ValueError("cryptography is not available")
            settings["proxy_password"] = decrypt_password(
                settings["proxy_password"], key)
        except Exception as e:  # InvalidToken等。復号不能なら空にする
            logger.warning("Failed to decrypt proxy password: %s", e)
            settings["proxy_password"] = ""
    return settings
