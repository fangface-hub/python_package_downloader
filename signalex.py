#! python3
"""シグナル拡張."""
import re
import select
import signal
import subprocess
import sys
import threading

from i18n import _
from loggingex import generate_logger

# グローバル変数でサブプロセスを追跡
subprocess_instances = []

logger = generate_logger(name=__name__, debug=__debug__, filepath=__file__)


def mask_password_in_command(command: list[str]) -> list[str]:
    """コマンド内のパスワードを伏字に置換する.

    Parameters
    ----------
    command : list[str]
        コマンドのリスト

    Returns
    -------
    list[str]
        パスワードが伏字に置換されたコマンドのリスト
    """
    masked_command = []
    for arg in command:
        # プロキシURLのパスワード部分を伏字に置換
        # 例: http://user:password@proxy:port -> http://user:****@proxy:port
        masked_arg = re.sub(r'(https?://[^:]+:)([^@]+)(@)', r'\1****\3', arg)
        masked_command.append(masked_arg)
    return masked_command


def __signal_handler(sig, frame) -> None:  # pylint: disable=unused-argument
    """
    子プロセスを終了するシグナルハンドラ.

    Parameters
    ----------
    sig : TYPE
        シグナル.
    frame : TYPE
        フレーム.

    Returns
    -------
    None
        なし.

    """
    if subprocess_instances:
        logger.info(_("log_terminating_all_subprocesses"))
        while subprocess_instances:  # リストが空になるまでループ
            instance = subprocess_instances.pop(0)  # リストの先頭から取得して削除
            instance.terminate()  # サブプロセスを終了
            instance.wait()  # 終了を待機
    sys.exit(0)


def stream_output(pipe, log_func):
    """リアルタイムで出力をログに記録"""
    for line in iter(pipe.readline, ""):
        log_func(line.strip())


def _apply_windows_no_window_options(popen_kwargs: dict) -> None:
    """Windows向けにサブプロセスのウィンドウ非表示オプションを適用する。"""
    if sys.platform != "win32":
        return

    popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    popen_kwargs["startupinfo"] = startupinfo


def run_command(command: list[str],
                timeout: float | None = None,
                stderr_as_error: bool = True) -> None:
    """コマンドの実行結果をパイプでログ出力する.

    Parameters
    ----------
    command : _type_
        コマンド
    timeout : float | None, optional
        タイムアウト秒数. Noneの場合は完了まで待機する.
    stderr_as_error : bool, optional
        Trueの場合は標準エラー出力をERRORとして記録する.
    """
    logger.info(
        _("log_running_command",
          command=mask_password_in_command(command)))
    stderr_log_func = logger.error if stderr_as_error else logger.info
    popen_kwargs = dict(stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True)
    _apply_windows_no_window_options(popen_kwargs)
    process = subprocess.Popen(command, **popen_kwargs)
    subprocess_instances.append(process)  # サブプロセスをリストに追加

    if sys.platform == "win32":
        # Windowsでは `threading` を使用
        stdout_thread = threading.Thread(target=stream_output,
                                         args=(process.stdout, logger.info))
        stderr_thread = threading.Thread(target=stream_output,
                                         args=(process.stderr, stderr_log_func))

        stdout_thread.start()
        stderr_thread.start()
        try:
            process.wait(timeout=timeout)
        except (TimeoutError, subprocess.TimeoutExpired) as e:
            process.terminate()
            process.wait()
            logger.error("Timeout command=%s",
                         mask_password_in_command(command))
            raise subprocess.TimeoutExpired(command, timeout) from e
        finally:
            if process in subprocess_instances:
                subprocess_instances.remove(process)
        stdout_thread.join()
        stderr_thread.join()
    else:
        # Unix系では `select` を使用
        while True:
            reads = [process.stdout, process.stderr]
            select_result = select.select(reads, [], [], 0.1)
            readable = select_result[0]

            for stream in readable:
                line = stream.readline().strip()
                if line:
                    if stream == process.stdout:
                        logger.info(line)
                    else:
                        stderr_log_func(line)

            if process.poll() is not None:
                break
        try:
            process.wait(timeout=timeout)
        except (TimeoutError, subprocess.TimeoutExpired) as e:
            process.terminate()
            process.wait()
            logger.error("Timeout command=%s",
                         mask_password_in_command(command))
            raise subprocess.TimeoutExpired(command, timeout) from e
        finally:
            if process in subprocess_instances:
                subprocess_instances.remove(process)
                logger.info(
                    _("log_subprocess_terminated",
                      command=mask_password_in_command(command)))

    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command)


def terminate_subprocess_at_signal() -> None:
    """
    親プロセス終了時に子プロセス終了のハンドラ登録.

    Returns
    -------
    None
        なし.

    """
    signal.signal(signal.SIGINT, __signal_handler)
    signal.signal(signal.SIGTERM, __signal_handler)


def start_subprocess(command: list) -> None:
    """
    サブプロセスを開始する.

    Parameters
    ----------
    command : list
        実行するコマンド.

    Returns
    -------
    None
        なし.

    """
    popen_kwargs = {}
    _apply_windows_no_window_options(popen_kwargs)
    process = subprocess.Popen(command, **popen_kwargs)
    subprocess_instances.append(process)  # サブプロセスをリストに追加
    logger.info(
        _("log_subprocess_started",
          command=mask_password_in_command(command)))
