import multiprocessing
import os
import queue
import subprocess
import sys
import tkinter.messagebox as messagebox
from pathlib import Path


def run_with_progress(target_func, args=(), kwargs=None):
    """
    multiprocessingとQueueを使って進捗報告する汎用ラッパー。
    メインプロセスはQueueから進捗を受け取るだけにできる。
    :param target_func: サブプロセスで実行する関数（progress_queue, stop_eventを必ず引数に含めること）
    :param args: 関数に渡す追加の引数（progress_queue, stop_eventは自動で付与）
    :param kwargs: 関数に渡すキーワード引数
    :return: (progress_queue, stop_event, process)
    """
    if kwargs is None:
        kwargs = {}
    progress_queue = multiprocessing.Queue()
    stop_event = multiprocessing.Event()
    process_args = args + (progress_queue, stop_event)
    process = multiprocessing.Process(target=target_func,
                                      args=process_args,
                                      kwargs=kwargs)
    process.start()
    return progress_queue, stop_event, process


def monitor_download_process(
        progress_queue, download_process, stop_event, status_label,
        main_progress_text_ref, dependency_progress_text_ref,
        dependency_progress_stack_ref, update_status_label_func,
        download_button, cancel_button, complete_msg, error_msg,
        download_complete_msg, download_cancelled_msg, error_occurred_msg,
        downloading_progress_msg, downloading_simple_msg):
    """
    Queueから進捗情報を取得し、UIに反映する汎用関数。Tkinterのafterで繰り返し呼び出すことを想定。
    main_window.pyの_monitor_download_processのロジックを移管。
    """
    try:
        while not progress_queue.empty():
            progress = progress_queue.get_nowait()
            if "status" in progress:
                if progress["status"] == "completed":
                    main_progress_text_ref[0] = ""
                    dependency_progress_text_ref[0] = ""
                    dependency_progress_stack_ref.clear()
                    status_label.config(text=download_complete_msg)
                elif progress["status"] == "cancelled":
                    main_progress_text_ref[0] = ""
                    dependency_progress_text_ref[0] = ""
                    dependency_progress_stack_ref.clear()
                    status_label.config(text=download_cancelled_msg)
                elif progress["status"] == "error":
                    error_msg_val = progress.get("message", error_msg)
                    main_progress_text_ref[0] = ""
                    dependency_progress_text_ref[0] = ""
                    dependency_progress_stack_ref.clear()
                    status_label.config(text=error_occurred_msg.format(
                        error_msg=error_msg_val))
                elif progress["status"] == "downloading_dependencies":
                    level = progress.get("level", 0)
                    dependency_progress_stack_ref[level] = ""
                    update_status_label_func()
                elif progress["status"] == "downloading_dependency":
                    current = progress.get("current", 0)
                    total = progress.get("total", 0)
                    package = progress.get("package", "")
                    level = progress.get("level", 0)
                    dependency_progress_stack_ref[
                        level] = f"{current}/{total}({package})"
                    update_status_label_func()
                elif progress["status"] == "dependency_complete":
                    level = progress.get("level", 0)
                    if level in dependency_progress_stack_ref:
                        del dependency_progress_stack_ref[level]
                    update_status_label_func()
            elif "total" in progress and "current" in progress:
                total = progress["total"]
                current = progress["current"]
                package = progress.get("package", "")
                if package:
                    main_progress_text_ref[0] = downloading_progress_msg.format(
                        current=current, total=total, package=package)
                else:
                    main_progress_text_ref[0] = downloading_simple_msg.format(
                        current=current, total=total)
                update_status_label_func()
    except (EOFError, OSError, queue.Empty):
        pass
    if download_process.is_alive():
        # 100ms後に再度チェック（Tkinterのafterで呼び出し元で設定）
        status_label.after(
            100, lambda: monitor_download_process(
                progress_queue, download_process, stop_event, status_label,
                main_progress_text_ref, dependency_progress_text_ref,
                dependency_progress_stack_ref, update_status_label_func,
                download_button, cancel_button, complete_msg, error_msg,
                download_complete_msg, download_cancelled_msg,
                error_occurred_msg, downloading_progress_msg,
                downloading_simple_msg))
    else:
        download_process.join()
        download_button.config(state="normal")
        cancel_button.config(state="disabled")
        exit_code = getattr(download_process, "exitcode", 0)
        if exit_code == 0:
            messagebox.showinfo(complete_msg, download_complete_msg)
        elif not stop_event.is_set():
            messagebox.showerror(error_msg, error_msg)


def open_file_with_platform(filepath: str) -> None:
    """
    プラットフォームに応じてファイルを開く（HTMLやPDFなど）
    :param filepath: 開きたいファイルのパス
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as e:
        raise RuntimeError(f"ファイルのオープンに失敗: {e}") from e
