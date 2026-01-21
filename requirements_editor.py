import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

REQUIREMENTS_FILE = "requirements.txt"

# パッケージ名とバージョン条件を分割する正規表現
REQ_PATTERN = re.compile(r"^([a-zA-Z0-9_.\-]+)\s*([<>=!~].*)?$")


class RequirementsEditor(tk.Toplevel):

    def __init__(self,
                 master=None,
                 requirements_path="requirements.txt",
                 modal=True):
        super().__init__(master)
        self.title("requirements.txt エディタ")
        self.geometry("600x400")
        self.requirements_path = requirements_path
        if modal and master is not None:
            self.transient(master)
            self.grab_set()  # モーダル化
        self.create_widgets()
        self.load_requirements()
        self._edit_info = None  # Initialize _edit_info attribute

    def show_modal(self):
        self.wait_window(self)

    def create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True)

        columns = ("package", "version")
        self.tree = ttk.Treeview(frame,
                                 columns=columns,
                                 show="headings",
                                 selectmode="browse")
        self.tree.heading("package", text="パッケージ名")
        self.tree.heading("version", text="バージョン条件")
        self.tree.column("package", width=200)
        self.tree.column("version", width=200)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # スクロールバー
        scrollbar = ttk.Scrollbar(frame,
                                  orient=tk.VERTICAL,
                                  command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 編集用エントリ
        self.edit_entry = tk.Entry(self)
        self.edit_entry.bind("<Return>", self.on_edit_entry_return)
        self.edit_entry.bind("<Escape>",
                             lambda e: self.edit_entry.place_forget())

        # ボタン
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="行追加",
                   command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="行削除",
                   command=self.delete_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="保存",
                   command=self.save_requirements).pack(side=tk.RIGHT, padx=2)

        self.tree.bind("<Double-1>", self.on_tree_double_click)

    def load_requirements(self):
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
                "保存", f"{os.path.basename(self.requirements_path)} を保存しました。")
        except (OSError, IOError) as e:
            messagebox.showerror("エラー", f"保存に失敗しました: {e}")

    def add_row(self):
        self.tree.insert("", tk.END, values=("", ""))

    def delete_row(self):
        selected = self.tree.selection()
        if selected:
            self.tree.delete(selected[0])

    def on_tree_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        rowid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not rowid or not col:
            return
        col_idx = int(col.replace("#", "")) - 1
        x, y, width, height = self.tree.bbox(rowid, col)
        value = self.tree.item(rowid, "values")[col_idx]
        self.edit_entry.place(x=x,
                              y=y + self.tree.winfo_y(),
                              width=width,
                              height=height)
        self.edit_entry.delete(0, tk.END)
        self.edit_entry.insert(0, value)
        self.edit_entry.focus()
        self._edit_info = (rowid, col_idx)

    def on_edit_entry_return(self, _event):
        if not hasattr(self, "_edit_info"):
            return
        rowid, col_idx = self._edit_info
        values = list(self.tree.item(rowid, "values"))
        values[col_idx] = self.edit_entry.get()
        self.tree.item(rowid, values=values)
        self.edit_entry.place_forget()
        del self._edit_info


if __name__ == "__main__":

    class RequirementsEditorStandalone(tk.Tk):

        def __init__(self, requirements_path=REQUIREMENTS_FILE):
            super().__init__()
            self.title("requirements.txt エディタ")
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
        on_tree_double_click = RequirementsEditor.on_tree_double_click
        on_edit_entry_return = RequirementsEditor.on_edit_entry_return

    app = RequirementsEditorStandalone(requirements_path=REQUIREMENTS_FILE)
    app.mainloop()
