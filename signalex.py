#! python3
"""シグナル拡張."""
import re
import select
import signal
import subprocess
import sys
import threading

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
    global subprocess_instances  # pylint: disable=global-variable-not-assigned
    if subprocess_instances:
        logger.info("すべてのサブプロセスを終了します...")
        while subprocess_instances:  # リストが空になるまでループ
            instance = subprocess_instances.pop(0)  # リストの先頭から取得して削除
            instance.terminate()  # サブプロセスを終了
            instance.wait()  # 終了を待機
    sys.exit(0)


def stream_output(pipe, log_func):
    """リアルタイムで出力をログに記録"""
    for line in iter(pipe.readline, ""):
        log_func(line.strip())


def run_command(command: list[str]) -> None:
    """コマンドの実行結果をパイプでログ出力する.

    Parameters
    ----------
    command : _type_
        コマンド
    """
    logger.info("コマンドを実行します: %s", mask_password_in_command(command))
    global subprocess_instances  # pylint: disable=global-variable-not-assigned
    popen_kwargs = dict(stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True)
    if sys.platform == "win32":
        # Windowsでウィンドウ非表示
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW",
                                                0)
    process = subprocess.Popen(command, **popen_kwargs)
    subprocess_instances.append(process)  # サブプロセスをリストに追加

    if sys.platform == "win32":
        # Windowsでは `threading` を使用
        stdout_thread = threading.Thread(target=stream_output,
                                         args=(process.stdout, logger.info))
        stderr_thread = threading.Thread(target=stream_output,
                                         args=(process.stderr, logger.error))

        stdout_thread.start()
        stderr_thread.start()
        try:
            process.wait(timeout=10.0)
            subprocess_instances.remove(process)  # サブプロセスをリストから削除
        except (TimeoutError, subprocess.TimeoutExpired):
            logger.error("Timeout command=%s",
                         mask_password_in_command(command))
            subprocess_instances.remove(process)  # サブプロセスをリストから削除
        stdout_thread.join()
        stderr_thread.join()
    else:
        # Unix系では `select` を使用
        while True:
            reads = [process.stdout, process.stderr]
            readable, _, _ = select.select(reads, [], [], 0.1)

            for stream in readable:
                line = stream.readline().strip()
                if line:
                    if stream == process.stdout:
                        logger.info(line)
                    else:
                        logger.error(line)

            if process.poll() is not None:
                break
        try:
            process.wait(timeout=10.0)
            subprocess_instances.remove(process)  # サブプロセスをリストから削除
        except TimeoutError:
            logger.error("Timeout command=%s",
                         mask_password_in_command(command))
            subprocess_instances.remove(process)  # サブプロセスをリストから削除
        logger.info("サブプロセスを終了しました: %s", mask_password_in_command(command))


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
    global subprocess_instances  # pylint: disable=global-variable-not-assigned
    process = subprocess.Popen(command)
    subprocess_instances.append(process)  # サブプロセスをリストに追加
    logger.info("サブプロセスを開始しました: %s", mask_password_in_command(command))
