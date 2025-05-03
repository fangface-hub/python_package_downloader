"""Custom tkinter widgets with enhanced functionality."""

from tkinter import END, BooleanVar, Frame, Listbox, Scrollbar, StringVar
from tkinter.ttk import Checkbutton, Entry


class CustomEntry(Entry):
    """カスタムエントリウィジェット.
    StringVarを使用して、値の取得と設定を行う.

    Parameters
    ----------
    Entry : _type_
        tkinterのEntryウィジェットを継承.
    """

    def __init__(self, master=None, **kwargs):
        self.var = StringVar()
        super().__init__(master, textvariable=self.var, **kwargs)

    @property
    def value(self) -> str:
        """値を取得（getter）."""
        return self.var.get()

    @value.setter
    def value(self, new_value) -> None:
        """値を設定（setter）."""
        self.var.set(new_value)


class CustomCheckbutton(Checkbutton):
    """カスタムチェックボックスウィジェット.
    BooleanVarを使用して、値の取得と設定を行う.

    Parameters
    ----------
    Checkbutton : _type_
        tkinterのCheckbuttonウィジェットを継承.
    """

    def __init__(self, master=None, **kwargs):
        self.var = BooleanVar()
        super().__init__(master, variable=self.var, **kwargs)

    @property
    def value(self) -> bool:
        """値を取得（getter）."""
        return self.var.get()

    @value.setter
    def value(self, new_value) -> None:
        """値を設定（setter）."""
        self.var.set(new_value)


class CustomListbox(Frame):
    """カスタムリストボックスウィジェット（スクロールバー付き）.
    Frameベースで、内部にListboxとScrollbarを持つ.

    Parameters
    ----------
    Frame : _type_
        tkinterのFrameウィジェットを継承.
    """

    def __init__(self, master=None, **kwargs):
        super().__init__(master)

        # Scrollbarを作成
        self.scrollbar = Scrollbar(self, orient="vertical")
        self.scrollbar.pack(side="right", fill="y")

        # Listboxを作成
        self.listbox = Listbox(self,
                               yscrollcommand=self.scrollbar.set,
                               **kwargs)
        self.listbox.pack(side="left", fill="both", expand=True)

        # ScrollbarとListboxを接続
        self.scrollbar.config(command=self.listbox.yview)

    def __getattr__(self, name):
        """Listboxのメソッドやプロパティを透過的に呼び出す."""
        return getattr(self.listbox, name)

    @property
    def curselection_list(self) -> list[str]:
        """選択中のリスト."""
        return [self.listbox.get(i) for i in self.listbox.curselection()]

    @curselection_list.setter
    def curselection_list(self, new_value) -> None:
        """選択中のリストを設定."""
        self.listbox.selection_clear(0, END)
        for item in new_value:
            index = self.listbox.get(0, END).index(item)
            self.listbox.selection_set(index)
