from unittest.mock import MagicMock, patch

import subprocessex


def _run(progress, exitcode, stop_set=False):
    queue = MagicMock()
    items = list(progress)
    queue.empty.side_effect = lambda: not items
    queue.get_nowait.side_effect = lambda: items.pop(0)
    process = MagicMock(exitcode=exitcode)
    process.is_alive.return_value = False
    stop_event = MagicMock()
    stop_event.is_set.return_value = stop_set
    with patch.object(subprocessex, "messagebox") as mb:
        subprocessex.monitor_download_process(
            queue, process, stop_event, MagicMock(), [""], [""], {},
            lambda: None, MagicMock(), MagicMock(), "ok", "err", "done",
            "cancelled", "failed: {error_msg}", "{current}", "{current}")
    return mb


def test_error_status_shows_error_dialog():
    mb = _run([{"status": "error", "message": "boom\ntrace"}], exitcode=1)
    mb.showerror.assert_called_once_with("err", "failed: boom")
    mb.showinfo.assert_not_called()


def test_success_shows_info():
    mb = _run([{"status": "completed"}], exitcode=0)
    mb.showinfo.assert_called_once()


def test_cancel_shows_no_dialog():
    mb = _run([{"status": "cancelled"}], exitcode=0, stop_set=True)
    mb.showinfo.assert_not_called()
    mb.showerror.assert_not_called()
