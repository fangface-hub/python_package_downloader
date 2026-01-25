# python3
"""Treeview拡張版のテストコード."""
# pylint: disable=protected-access
import unittest
from unittest.mock import MagicMock
from tkinter import Tk
from treeviewex import TreeviewEx


class TestTreeviewEx(unittest.TestCase):
    """TreeviewExのテストクラス.

    Parameters
    ----------
    unittest : _type_
        テストケースクラス.
    """

    def setUp(self):
        """Set up the test environment."""
        self.root = Tk()
        self.root.withdraw()  # ウィンドウを非表示にする
        self.treeview_ex = TreeviewEx(self.root)  # pylint: disable=not-callable
        self.treeview_ex["columns"] = ("#1", "#2", "#3")  # 列をモック
        for col in self.treeview_ex["columns"]:
            self.treeview_ex.heading(col, text=col)
            self.treeview_ex.column(col, width=100)

        # Add test data
        self.treeview_ex.insert(
            "", "end", iid="row1", values=("A1", "B1", "C1")
        )
        self.treeview_ex.insert(
            "", "end", iid="row2", values=("A2", "B2", "C2")
        )

        # bbox メソッドをモック
        self.treeview_ex.bbox = MagicMock(return_value=(0, 0, 100, 20))

        # entry ウィジェットをモック
        self.treeview_ex.entry = MagicMock()
        self.entry_value = "A1"  # モックの内部状態を保持
        self.treeview_ex.entry.get = MagicMock(
            side_effect=lambda: self.entry_value
        )
        self.treeview_ex.entry.insert = MagicMock(
            side_effect=self._mock_entry_insert
        )
        self.treeview_ex.entry.winfo_ismapped = MagicMock(return_value=False)

        # exists メソッドをモック
        self.treeview_ex.exists = MagicMock(
            side_effect=lambda row_id: row_id == "row1"
        )

    def _mock_entry_insert(self, index, value):
        """entry.insert のモック動作."""
        if index == 0:
            self.entry_value = value

    def tearDown(self):
        """Tear down the test environment."""
        self.root.destroy()

    def test_get_clicked_cell_id_pair(self):
        """Test get_clicked_cell_id_pair method."""
        event = type("Event", (object,), {"x": 50, "y": 20})()
        cell_id_pair = self.treeview_ex.get_clicked_cell_id_pair(event)
        self.assertEqual(cell_id_pair, ("", ""))  # No cell clicked

    def test_get_cell_value(self):
        """Test get_cell_value method."""
        cell_value = self.treeview_ex.get_cell_value(("row1", "#1"))
        self.assertEqual(cell_value, "A1")

    def test_start_edit(self):
        """Test start_edit method."""
        # 必要な列と行を準備
        self.treeview_ex["columns"] = ("#1", "#2", "#3")

        # 有効なセルで編集を開始
        self.treeview_ex.start_edit(("row1", "#1"))
        self.assertEqual(self.treeview_ex._editing_cell, ("row1", "#1"))
        self.assertEqual(self.treeview_ex.entry.get(), "A1")

        # 無効なセルで編集を開始しようとするとエラー
        with self.assertRaises(ValueError):
            self.treeview_ex.start_edit(("invalid_row", "#1"))

        with self.assertRaises(ValueError):
            self.treeview_ex.start_edit(("row1", "#99"))

        with self.assertRaises(ValueError):
            self.treeview_ex.start_edit(("row1", "invalid_column"))

        # bbox が None の場合のエラー
        self.treeview_ex.bbox = lambda row_id, column_id: None  # bbox をモック
        with self.assertRaises(ValueError):
            self.treeview_ex.start_edit(("row1", "#1"))

    def test_start_edit_invalid_cell(self):
        """Test start_edit with an invalid cell."""
        # 無効なセルで編集を開始しようとするとエラー
        with self.assertRaises(ValueError):
            self.treeview_ex.start_edit(("invalid_row", "#1"))

        with self.assertRaises(ValueError):
            self.treeview_ex.start_edit(("row1", "#99"))

        with self.assertRaises(ValueError):
            self.treeview_ex.start_edit(("row1", "invalid_column"))

    def test_start_edit_bbox_none(self):
        """Test start_edit when bbox returns None."""
        # bbox をモックして None を返す
        self.treeview_ex.bbox = lambda row_id, column_id: None

        # bbox が None の場合にエラーが発生することを確認
        with self.assertRaises(ValueError):
            self.treeview_ex.start_edit(("row1", "#1"))

    def test_update_cell(self):
        """Test update_cell method."""
        self.treeview_ex.start_edit(("row1", "#1"))
        self.treeview_ex.entry.insert(0, "Updated")
        self.treeview_ex.update_cell(("row1", "#1"), self.treeview_ex.entry)
        updated_value = self.treeview_ex.get_cell_value(("row1", "#1"))
        self.assertEqual(updated_value, "Updated")

    def test_update_cell_invalid_cell(self):
        """Test update_cell with an invalid cell."""
        with self.assertRaises(ValueError):  # 適切な例外を指定
            self.treeview_ex.update_cell(
                ("invalid_row", "#1"), self.treeview_ex.entry
            )

    def test_update_cell_no_change(self):
        """Test update_cell when the value does not change."""
        # セルの初期値を設定
        self.treeview_ex["columns"] = ("#1", "#2", "#3")

        # Entry に現在の値と同じ値を設定
        self.treeview_ex.entry.insert(0, "A1")

        # update_cell を呼び出す
        self.treeview_ex.update_cell(("row1", "#1"), self.treeview_ex.entry)

        # セルの値が変更されていないことを確認
        updated_value = self.treeview_ex.get_cell_value(("row1", "#1"))
        self.assertEqual(updated_value, "A1")  # 値は変更されない

    def test_cancel_edit(self):
        """Test cancel_edit method."""
        self.treeview_ex.start_edit(("row1", "#1"))
        self.treeview_ex.cancel_edit()
        self.assertIsNone(
            self.treeview_ex._editing_cell  # pylint: disable=protected-access
        )
        self.assertFalse(self.treeview_ex.entry.winfo_ismapped())

    def test_scroll_y(self):
        """Test vertical scrolling."""
        self.treeview_ex._on_scroll_y(  # pylint: disable=protected-access
            "moveto", 0.5
        )
        # No assertion here, just ensuring no exceptions occur

    def test_scroll_x(self):
        """Test horizontal scrolling."""
        self.treeview_ex._on_scroll_x(  # pylint: disable=protected-access
            "moveto", 0.5
        )
        # No assertion here, just ensuring no exceptions occur

    def test_mouse_wheel(self):
        """Test mouse wheel scrolling."""
        event = type("Event", (object,), {"delta": 120})()
        self.treeview_ex._on_mouse_wheel(  # pylint: disable=protected-access
            event
        )
        # No assertion here, just ensuring no exceptions occur

    def test_mouse_wheel_scroll_up(self):
        """Test mouse wheel scrolling up."""
        event = type("Event", (object,), {"delta": 120})()
        self.treeview_ex._on_mouse_wheel(  # pylint: disable=protected-access
            event
        )
        # Add assertions to verify the scroll position if applicable

    def test_mouse_wheel_scroll_down(self):
        """Test mouse wheel scrolling down."""
        event = type("Event", (object,), {"delta": -120})()
        self.treeview_ex._on_mouse_wheel(  # pylint: disable=protected-access
            event
        )
        # Add assertions to verify the scroll position if applicable

    def test_on_scroll_y(self):
        """Test _on_scroll_y method."""
        # 編集中のセルを設定
        self.treeview_ex._editing_cell = (  # pylint: disable=protected-access
            "row1",
            "#1",
        )

        # スクロールイベントをシミュレート
        self.treeview_ex._on_scroll_y(  # pylint: disable=protected-access
            "moveto", 0.5
        )

        # 編集がキャンセルされていることを確認
        self.assertIsNone(
            self.treeview_ex._editing_cell  # pylint: disable=protected-access
        )

    def test_on_scroll_x(self):
        """Test _on_scroll_x method."""
        # 編集中のセルを設定
        self.treeview_ex._editing_cell = (  # pylint: disable=protected-access
            "row1",
            "#1",
        )

        # 横スクロールイベントをシミュレート
        self.treeview_ex._on_scroll_x(  # pylint: disable=protected-access
            "moveto", 0.5
        )

        # 編集がキャンセルされていることを確認
        self.assertIsNone(
            self.treeview_ex._editing_cell  # pylint: disable=protected-access
        )

    def test_on_mouse_wheel(self):
        """Test _on_mouse_wheel method."""
        # 編集中のセルを設定
        self.treeview_ex._editing_cell = (
            "row1",
            "#1",
        )

        # マウスホイールイベントをシミュレート
        event = type(
            "Event", (object,), {"delta": 120}
        )()  # 正の delta は上スクロール
        self.treeview_ex._on_mouse_wheel(event)

        # 編集がキャンセルされていることを確認
        self.assertIsNone(self.treeview_ex._editing_cell)

        # マウスホイールイベントでスクロールが呼び出されることを確認
        self.treeview_ex.yview_scroll = MagicMock()
        self.treeview_ex._on_mouse_wheel(event)
        self.treeview_ex.yview_scroll.assert_called_with(-1, "units")

    def test_additional_bind_double_click(self):
        """Test _additional_bind_double_click method."""
        # ダブルクリックイベントをシミュレート
        # on_double_click メソッドをモック
        self.treeview_ex.on_double_click = MagicMock()

        # 既存の <Double-1> バインドをモック
        original_handler = MagicMock()
        self.treeview_ex._original_bind_double_click = original_handler

        # bind メソッドをモック
        self.treeview_ex.bind = MagicMock()

        # ダブルクリックハンドラを追加
        self.treeview_ex._additional_bind_double_click()

        # on_double_click が呼び出されることを確認
        self.treeview_ex.on_double_click.assert_not_called()

        # 元のハンドラが呼び出されることを確認
        original_handler.assert_not_called()

    def test_combined_handler(self):
        """Test _combined_handler method."""
        mock_event = MagicMock()

        # on_double_click メソッドをモック
        self.treeview_ex.on_double_click = MagicMock()

        # 元のハンドラをモック
        self.treeview_ex._original_bind_double_click = MagicMock()

        # _combined_handler を呼び出す
        self.treeview_ex._combined_handler(mock_event)

        # on_double_click が呼び出されたことを確認
        self.treeview_ex.on_double_click.assert_called_once_with(mock_event)

        # 元のハンドラが呼び出されたことを確認
        self.treeview_ex._original_bind_double_click.assert_called_once_with(
            mock_event
        )

    def test_combined_handler_with_original_handler(self):
        """Test _combined_handler when _original_bind_double_click is set."""
        mock_event = MagicMock()

        # 元のハンドラをモック
        original_handler = MagicMock()
        self.treeview_ex._original_bind_double_click = original_handler

        # on_double_click メソッドをモック
        self.treeview_ex.on_double_click = MagicMock()

        # _combined_handler を呼び出す
        self.treeview_ex._combined_handler(mock_event)

        # on_double_click と元のハンドラが呼び出されたことを確認
        self.treeview_ex.on_double_click.assert_called_once_with(mock_event)
        original_handler.assert_called_once_with(mock_event)

    def test_combined_handler_without_original_handler(self):
        """Test _combined_handler when _original_bind_double_click is not set."""
        mock_event = MagicMock()

        # 元のハンドラを None に設定
        self.treeview_ex._original_bind_double_click = None

        # on_double_click メソッドをモック
        self.treeview_ex.on_double_click = MagicMock()

        # _combined_handler を呼び出す
        self.treeview_ex._combined_handler(mock_event)

        # on_double_click が呼び出されたことを確認
        self.treeview_ex.on_double_click.assert_called_once_with(mock_event)

    def test_is_valid_cell(self):
        """Test is_valid_cell method."""
        # 有効なセルの場合
        self.assertTrue(self.treeview_ex.is_valid_cell(("row1", "#1")))

        # 無効な行IDの場合
        self.assertFalse(self.treeview_ex.is_valid_cell(("invalid_row", "#1")))

        # 無効な列IDの場合
        self.assertFalse(self.treeview_ex.is_valid_cell(("row1", "#99")))

        # 無効な列ID形式の場合
        self.assertFalse(
            self.treeview_ex.is_valid_cell(("row1", "invalid_column"))
        )

    def test_readonly_behavior(self):
        """Test readonly behavior."""
        self.treeview_ex["columns"] = ("#1", "#2", "#3")

        # 行を readonly に設定
        self.treeview_ex.set_readonly_row("row1")
        self.treeview_ex.start_edit(("row1", "#1"))
        self.assertIsNone(self.treeview_ex._editing_cell)  # 編集が開始されない

        # 列を readonly に設定
        self.treeview_ex.set_readonly_row(
            "row1", readonly=False
        )  # 行の readonly を解除
        self.treeview_ex.set_readonly_column("#1")
        self.treeview_ex.start_edit(("row1", "#1"))
        self.assertIsNone(self.treeview_ex._editing_cell)  # 編集が開始されない

        # セルを readonly に設定
        self.treeview_ex.set_readonly_column(
            "#1", readonly=False
        )  # 列の readonly を解除
        self.treeview_ex.set_readonly_cell(("row1", "#1"))
        self.treeview_ex.start_edit(("row1", "#1"))
        self.assertIsNone(self.treeview_ex._editing_cell)  # 編集が開始されない

        # readonly を解除して編集可能にする
        self.treeview_ex.set_readonly_cell(("row1", "#1"), readonly=False)
        self.treeview_ex.start_edit(("row1", "#1"))
        self.assertEqual(
            self.treeview_ex._editing_cell, ("row1", "#1")
        )  # 編集が開始される


if __name__ == "__main__":
    unittest.main()
