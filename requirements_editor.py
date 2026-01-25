"""
requirements_editor.

requirements.txtエディタ
Requirements.txt editor
"""
import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

from i18n import _
from treeviewex import TreeviewEx

REQUIREMENTS_FILE = "requirements.txt"

# パッケージ名とバージョン条件を分割する正規表現
REQ_PATTERN = re.compile(r"^([a-zA-Z0-9_.\-]+)\s*([<>=!~].*)?$")


class RequirementsEditor(tk.Toplevel):
    """
    requirements.txt エディタ.
    requirements.txt editor.
    """

    def __init__(self,
                 master=None,
                 requirements_path="requirements.txt",
                 modal=True):
        super().__init__(master)
        self.title(_("requirements_editor_title"))
        self.geometry("600x400")
        self.requirements_path = requirements_path
        if modal and master is not None:
            self.transient(master)
            self.grab_set()  # モーダル化
        self.create_widgets()
        self.load_requirements()
        self._edit_info = None  # Initialize _edit_info attribute

    def show_modal(self):
        """
        modal ダイアログとして表示する.
        Show as a modal dialog.
        """
        self.wait_window(self)

    def create_widgets(self):
        """
        widgets 作成.
        Create widgets.
        """
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True)

        columns = ("package", "version")
        self.tree = TreeviewEx(frame,
                               columns=columns,
                               show="headings",
                               selectmode="browse")
        self.tree.heading("package", text=_("package_name"))
        self.tree.heading("version", text=_("version_specifier"))
        self.tree.column("package", width=300)
        self.tree.column("version", width=300)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # ボタン
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text=_("add_row"),
                   command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_("delete_row"),
                   command=self.delete_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_("save"),
                   command=self.save_requirements).pack(side=tk.RIGHT, padx=2)

    def load_requirements(self):
        """
        requirements.txt 読み込み.
        Load requirements.txt
        """
        self.tree.delete(*self.tree.get_children())
        path = self.requirements_path
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = REQ_PATTERN.match(line)
                if m:
                    pkg, ver = m.group(1), m.group(2) or ""
                    self.tree.insert("", tk.END, values=(pkg, ver))
                else:
                    self.tree.insert("", tk.END, values=(line, ""))

    def save_requirements(self):
        """
        requirements.txt 保存.
        Save requirements.txt.
        """
        lines = []
        for item in self.tree.get_children():
            pkg, ver = self.tree.item(item, "values")
            line = pkg.strip()
            if ver.strip():
                line += ver.strip()
            lines.append(line)
        try:
            with open(self.requirements_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            messagebox.showinfo(
                _("saved"),
                _("saved_msg", file=os.path.basename(self.requirements_path)))
        except (OSError, IOError) as e:
            messagebox.showerror(_("save_failed"), _("save_failed_msg",
                                                     error=e))

    def add_row(self):
        """
        行追加.
        Add row.
        """
        self.tree.insert("", tk.END, values=("", ""))

    def delete_row(self):
        """
        行削除.
        Delete row.
        """
        selected = self.tree.selection()
        if selected:
            self.tree.delete(selected[0])


if __name__ == "__main__":

    class RequirementsEditorStandalone(tk.Tk):
        """
        単独実行用 RequirementsEditor.
        Standalone RequirementsEditor.
        """

        def __init__(self, requirements_path=REQUIREMENTS_FILE):
            super().__init__()
            self.title(_("requirements_editor_title"))
            self.geometry("600x400")
            self.requirements_path = requirements_path
            self.create_widgets()
            self.load_requirements()

        # RequirementsEditorのメソッドを利用
        create_widgets = RequirementsEditor.create_widgets
        load_requirements = RequirementsEditor.load_requirements
        save_requirements = RequirementsEditor.save_requirements
        add_row = RequirementsEditor.add_row
        delete_row = RequirementsEditor.delete_row

    app = RequirementsEditorStandalone(requirements_path=REQUIREMENTS_FILE)
    app.mainloop()
