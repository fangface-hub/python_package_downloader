"""Pythonパッケージのダウンロードに関するユーティリティモジュール."""

# -*- coding: utf-8 -*-
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import parse

import pathlibex
from i18n import _
from signalex import run_command

try:
    from cryptography.fernet import Fernet

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

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

package_requirements_history = []


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


# ロギングの設定
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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
    pattern = re.compile(r"^([a-zA-Z0-9_\-]+)([<>=!]+)?(\d+\.\d+\.\d+)?$")
    match = pattern.match(requirement)

    if match:
        package = match.group(1)
        operator = match.group(2) if match.group(2) else ""
        version = match.group(3) if match.group(3) else ""
        version_condition = operator + version if operator else ""
        return PackageRequirements(package, version_condition)

    return None  # 不明なフォーマット


def find_whl_package_info_list(folder: str,
                               package_name: str) -> list[PackageInfo]:
    """指定フォルダ内の .whl ファイルから指定パッケージのバージョンを取得"""
    package_info_list = []

    for file in os.listdir(folder):
        if not file.startswith(package_name) or not file.endswith(".whl"):
            continue
        pakage_info = get_package_info_from_whl(file)
        if pakage_info.name == package_name:
            package_info_list.append(pakage_info)

    return package_info_list


def find_targz_package_info_list(folder: str,
                                 package_name: str) -> list[PackageInfo]:
    """指定フォルダ内の .tar.gz ファイルから指定パッケージのバージョンを取得"""
    package_info_list = []

    for file in os.listdir(folder):
        if not file.startswith(package_name) or not file.endswith(".tar.gz"):
            continue
        match = re.search(f"{package_name}-([0-9.]*).tar.gz", file)
        if match:
            version = match.group(1)
            package_info_list.append(
                PackageInfo(
                    name=package_name,
                    version=version,
                    python_version="none",
                    abi="none",
                    platform="none",
                ))
            continue

    return package_info_list


def normalize_version(version):
    """バージョンを標準化（メジャーのみの場合も補完）"""
    version_parts = version.split(".")

    # メジャーのみの場合はマイナー・パッチを補完（例: "2" → "2.0.0"）
    while len(version_parts) < 3:
        version_parts.append("0")

    return [int(part) if part.isdigit() else part for part in version_parts]


def compare_versions(version1, version2, operator):
    """バージョンを分割して数値比較を行う"""
    if version2 is None or operator is None:
        return True
    v1_parts = normalize_version(version1)
    v2_parts = normalize_version(version2)
    if operator == "==":
        return v1_parts == v2_parts
    if operator == ">":
        return v1_parts > v2_parts
    if operator == ">=":
        return v1_parts >= v2_parts
    if operator == "<":
        return v1_parts < v2_parts
    if operator == "<=":
        return v1_parts <= v2_parts
    return False  # 不明な条件


def parse_condition(condition):
    """演算子とバージョン番号を正規表現で抽出"""
    pattern = re.compile(r"^(==|!=|>=|<=|>|<)\s*(\d+\.\d+\.\d+)$")
    match = pattern.match(condition)

    if match:
        return match.group(1), match.group(2)  # 演算子, バージョン番号

    return None, None  # 未指定


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

    # 条件の解析
    operator, target_version = parse_condition(requirement.version_condition)

    for package_info in package_info_list:
        if (package_info.platform != "any"
                and platform not in package_info.platform):
            continue
        if not re.search(python_version_pattern, package_info.python_version):
            continue
        if compare_versions(package_info.version, target_version, operator):
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
    # 条件の解析
    operator, target_version = parse_condition(requirement.version_condition)
    for pachage_info in package_info_list:
        # バージョン番号が適用外はスキップ
        if compare_versions(pachage_info.version, target_version, operator):
            ret = True
            break
    logger.debug("return=%s,folder=%s,requirement=%s", ret, folder, requirement)
    return ret


def get_dependencies_from_whl(whl_file: str) -> list[PackageRequirements]:
    """.whlファイルから依存関係を取得する.

    Parameters
    ----------
    whl_file : str
        .whlファイルのパス.

    Returns
    -------
    list[PackageRequirements]
        依存関係のリスト.
    """
    dependencies = []
    try:
        with zipfile.ZipFile(whl_file, "r") as z:
            metadata_files = [f for f in z.namelist() if "METADATA" in f]
            if not metadata_files:
                logger.info(
                    _("log_metadata_file_not_found", file=whl_file))
                return dependencies
            with z.open(metadata_files[0]) as metadata:
                lines = metadata.read().decode().split("\n")
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
                            requirement, package_requirements_history):
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


def get_dependencies_from_targz(targz_file: str) -> list[PackageRequirements]:
    """.tar.gzファイルから依存関係を取得する.

    Parameters
    ----------
    targz_file : str
        .tar.gzファイルのパス.

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

            pkg_info = tar.extractfile(pkg_info_files[0]).read().decode()
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
                        requirement, package_requirements_history):
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


def download_package_pip(package_requirements: PackageRequirements,
                         config: DownloadConfig,
                         stop_event=None) -> None:
    """指定された条件でpipでパッケージをダウンロードする.

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

    before_files = set(os.listdir(config.dest_folder))
    base_command: list[str] | None = None
    try:
        pip_command_prefix = _resolve_pip_command_prefix(config.pip_path)
        if not pip_command_prefix:
            raise FileNotFoundError("利用可能なpipコマンドが見つかりません。"
                                    "pip_pathの指定またはPython環境の設定を確認してください。")

        base_command = pip_command_prefix + [
            "download",
            package_requirements.requirement,
        ]
        if config.proxy:
            base_command.append(f"--proxy={config.proxy}")  # プロキシ設定を追加

        for os_name in config.os_list:
            if stop_event and stop_event.is_set():
                return
            if stop_event and stop_event.is_set():
                return
            platforms = OS_TO_PLATFORMS.get(os_name, [])
            if not platforms:
                logger.warning(
                    _("log_skipping_unsupported_os", os_name=os_name))
                continue
            for platform in platforms:
                if stop_event and stop_event.is_set():
                    return
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
                    tmp_version = python_version.replace(".", "")
                    only_binary_command = base_command.copy()
                    only_binary_command.append("--only-binary=:all:")
                    only_binary_command.append(f"--platform={platform}")
                    only_binary_command.append(
                        f"--python-version={tmp_version}")
                    only_binary_command.append(f"--dest={config.dest_folder}")
                    run_command(
                        only_binary_command,
                        stderr_as_error=not config.include_source,
                    )
        after_files = set(os.listdir(config.dest_folder))
        new_files = after_files - before_files
        if 0 < len(new_files):
            logger.info(_("log_downloaded_successfully", files=new_files))
            if config.include_deps:
                download_dep_package(config=config,
                                     filelist=new_files,
                                     stop_event=stop_event)
            return
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError) as e:
        # pip自体が実行できない場合は、ソース取得へフォールバックできない。
        if isinstance(e, (FileNotFoundError, OSError)) or base_command is None:
            logger.error(
                _("log_download_error",
                  requirement=package_requirements,
                  error=e))
            if PYPISIMPLE_AVAILABLE:
                logger.warning(
                    _(
                        "pip unavailable, falling back to "
                        "pypi-simple for {requirement}",
                        requirement=package_requirements))
                download_package_no_pip(
                    package_requirements=package_requirements,
                    config=config,
                    stop_event=stop_event,
                )
            return
        if not config.include_source:
            logger.error(
                _("log_download_error",
                  requirement=package_requirements,
                  error=e))
            return

    if not config.include_source:
        logger.warning(
            _(
                "Could not download {requirement} with pip "
                "(no matching wheel or pip execution failed).",
                requirement=package_requirements))
        return
    if check_targz(folder=config.dest_folder, requirement=package_requirements):
        logger.info(
            _("log_source_distribution_already_downloaded",
              requirement=package_requirements))
        return
    # ソース形式は依存解決なしで取得し、ビルド依存関係解決の失敗ログを抑える。
    no_source_command = base_command.copy()
    no_source_command.append("--no-binary=:all:")
    no_source_command.append("--no-deps")
    no_source_command.append(f"--dest={config.dest_folder}")
    try:
        run_command(no_source_command, stderr_as_error=False)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError):
        pass
    after_files = set(os.listdir(config.dest_folder))
    new_files = after_files - before_files
    if 0 < len(new_files):
        logger.info(_("log_downloaded_successfully", files=new_files))
        if config.include_deps:
            download_dep_package(config=config, filelist=new_files)


def download_package_uv(package_requirements: PackageRequirements,
                        config: DownloadConfig,
                        stop_event=None) -> None:
    """指定された条件でuv(pip互換)でパッケージをダウンロードする."""
    if stop_event and stop_event.is_set():
        return

    before_files = set(os.listdir(config.dest_folder))
    base_command: list[str] | None = None
    try:
        uv_command_prefix = _resolve_uv_command_prefix(config.pip_path)
        if not uv_command_prefix:
            raise FileNotFoundError("利用可能なuvコマンドが見つかりません。"
                                    "uvをインストールするか、pip方式を利用してください。")

        if not _supports_uv_pip_download(uv_command_prefix):
            logger.warning(
                _(
                    "Current uv does not support "
                    "uv pip download; "
                    "falling back to pip for {requirement}",
                    requirement=package_requirements))
            download_package_pip(
                package_requirements=package_requirements,
                config=config,
                stop_event=stop_event,
            )
            return

        base_command = uv_command_prefix + [
            "pip",
            "download",
            package_requirements.requirement,
        ]
        if config.proxy:
            base_command.append(f"--proxy={config.proxy}")

        for os_name in config.os_list:
            if stop_event and stop_event.is_set():
                return
            platforms = OS_TO_PLATFORMS.get(os_name, [])
            if not platforms:
                logger.warning(
                    _("log_skipping_unsupported_os", os_name=os_name))
                continue
            for platform in platforms:
                if stop_event and stop_event.is_set():
                    return
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
                    tmp_version = python_version.replace(".", "")
                    only_binary_command = base_command.copy()
                    only_binary_command.append("--only-binary=:all:")
                    only_binary_command.append(f"--platform={platform}")
                    only_binary_command.append(
                        f"--python-version={tmp_version}")
                    only_binary_command.append(f"--dest={config.dest_folder}")
                    run_command(
                        only_binary_command,
                        stderr_as_error=not config.include_source,
                    )
        after_files = set(os.listdir(config.dest_folder))
        new_files = after_files - before_files
        if 0 < len(new_files):
            logger.info(_("log_downloaded_successfully", files=new_files))
            if config.include_deps:
                download_dep_package(config=config,
                                     filelist=new_files,
                                     stop_event=stop_event)
            return
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError) as e:
        if isinstance(e, (FileNotFoundError, OSError)) or base_command is None:
            logger.error(
                _("log_download_error",
                  requirement=package_requirements,
                  error=e))
            if PYPISIMPLE_AVAILABLE:
                logger.warning(
                    _(
                        "uv unavailable, falling back to "
                        "pypi-simple for {requirement}",
                        requirement=package_requirements))
                download_package_no_pip(
                    package_requirements=package_requirements,
                    config=config,
                    stop_event=stop_event,
                )
            return
        if not config.include_source:
            logger.error(
                _("log_download_error",
                  requirement=package_requirements,
                  error=e))
            return

    if not config.include_source:
        logger.warning(
            _(
                "Could not download {requirement} with uv "
                "(no matching wheel or uv execution failed).",
                requirement=package_requirements))
        return
    if check_targz(folder=config.dest_folder, requirement=package_requirements):
        logger.info(
            _("log_source_distribution_already_downloaded",
              requirement=package_requirements))
        return

    no_source_command = base_command.copy()
    no_source_command.append("--no-binary=:all:")
    no_source_command.append("--no-deps")
    no_source_command.append(f"--dest={config.dest_folder}")
    try:
        run_command(no_source_command, stderr_as_error=False)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError):
        pass
    after_files = set(os.listdir(config.dest_folder))
    new_files = after_files - before_files
    if 0 < len(new_files):
        logger.info(_("log_downloaded_successfully", files=new_files))
        if config.include_deps:
            download_dep_package(config=config, filelist=new_files)


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


def download_package_no_pip(package_requirements: PackageRequirements,
                            config: DownloadConfig,
                            stop_event=None) -> None:
    """PyPISimpleとrequestsを使用して1つのパッケージをダウンロードする.

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

        dlcnt = 0
        for package in reversed(packages_info.packages):
            # プラットフォームでフィルタリング
            package_info = get_package_info_from_whl(package.filename)
            if check_whl_version(
                    folder=config.dest_folder,
                    requirement=package_requirements,
                    platform=package_info.platform,
                    python_version=package_info.python_version,
            ):
                continue
            # ファイル名取得
            filename = os.path.join(config.dest_folder,
                                    os.path.basename(package.url))
            if os.path.exists(filename):
                continue

            # パッケージをダウンロード
            response = requests.get(package.url, stream=True, timeout=10)
            response.raise_for_status()

            # ファイルを保存
            with open(filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            dlcnt += 1
            break
        if config.include_source and dlcnt == 0:
            if check_targz(folder=config.dest_folder,
                           requirement=package_requirements):
                logger.info(
                    _(
                        "Source distribution is already downloaded for "
                        "{requirement}.",
                        requirement=package_requirements,
                    ))
                return
            for package in reversed(packages_info.packages):
                # ソース形式を含める場合は、再度ダウンロード
                if package.filename.endswith(".tar.gz"):
                    # ファイル名取得
                    filename = os.path.join(config.dest_folder,
                                            os.path.basename(package.url))
                    if os.path.exists(filename):
                        continue
                    response = requests.get(package.url,
                                            stream=True,
                                            timeout=10)
                    response.raise_for_status()
                    # ファイルを保存
                    with open(filename, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    dlcnt += 1
                    break
        after_files = set(os.listdir(config.dest_folder))
        new_files = after_files - before_files
        if 0 < len(new_files) and 0 < dlcnt:
            logger.info(_("log_download_completed", files=new_files))
            if config.include_deps:
                download_dep_package(config=config,
                                     filelist=new_files,
                                     stop_event=stop_event)
            return
        logger.warning(
            _("log_download_url_not_found",
              requirement=package_requirements))
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
                                           package_requirements_history):
            continue
        package_requirements_history.append(package_requirements)
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
            dependencies = get_dependencies_from_targz(targz_file=file_path)
            package_requirements_list.extend(dependencies)
            continue
        if file_.endswith(".whl"):
            dependencies = get_dependencies_from_whl(whl_file=file_path)
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
    from dataclasses import replace
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

    license_found = False

    try:
        if package_file.endswith('.whl'):
            # wheelファイルの場合
            with zipfile.ZipFile(package_file, 'r') as zip_ref:
                # .dist-info内のLICENSEファイルを探す
                for file_info in zip_ref.filelist:
                    filename = file_info.filename.upper()
                    if '.dist-info/' in file_info.filename and (
                            'LICENSE' in filename or 'LICENCE' in filename
                            or 'COPYING' in filename):
                        # ライセンスファイルを抽出
                        license_content = zip_ref.read(file_info.filename)
                        output_file = Path(
                            licenses_dir) / f"{base_name}_LICENSE.txt"
                        with open(output_file, 'wb') as f:
                            f.write(license_content)
                        logger.info(
                            _("log_extracted_license_file",
                              file=output_file))
                        license_found = True
                        break

        elif package_file.endswith('.tar.gz') or package_file.endswith('.tgz'):
            # tar.gzファイルの場合
            with tarfile.open(package_file, 'r:gz') as tar_ref:
                # LICENSEファイルを探す
                for member in tar_ref.getmembers():
                    member_name = member.name.upper()
                    if ('LICENSE' in member_name or 'LICENCE' in member_name
                            or 'COPYING' in member_name):
                        # ライセンスファイルを抽出
                        file_obj = tar_ref.extractfile(member)
                        if file_obj:
                            license_content = file_obj.read()
                            output_file = Path(
                                licenses_dir) / f"{base_name}_LICENSE.txt"
                            with open(output_file, 'wb') as f:
                                f.write(license_content)
                            logger.info(
                                _("log_extracted_license_file",
                                  file=output_file))
                            license_found = True
                            break

        if not license_found:
            logger.warning(
                _("log_license_file_not_found_in_package",
                  file=package_file))

    except (zipfile.BadZipFile, tarfile.TarError, OSError, IOError) as e:
        logger.error(
            _("log_extract_license_file_failed",
              file=package_file,
              error=e))


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
    package_requirements_history.clear()
    os.makedirs(config.dest_folder, exist_ok=True)
    package_requirements_list = []
    with open(config.package_list_file, "r", encoding="utf-8") as file:
        for line_ in file.readlines():
            requirement = parse_package_condition("".join(line_.split()))
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


def generate_key() -> bytes:
    """暗号化キーを生成し、ファイルに保存する."""
    key_file = DATA_DIR / "key.key"
    if not key_file.exists():
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
    else:
        with open(key_file, "rb") as f:
            key = f.read()
    return key


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
        settings["proxy_password"] = decrypt_password(
            settings["proxy_password"], key)
    return settings
