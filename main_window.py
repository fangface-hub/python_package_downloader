"""Main window for Python package downloader application."""

import multiprocessing
import multiprocessing.synchronize
import os
import shutil
import subprocess
import sys
import urllib.parse  # URLエンコード用
from pathlib import Path
from tkinter import END, Label, Menu, StringVar, Tk, filedialog, messagebox
from tkinter.ttk import Button, Combobox, Frame, Radiobutton

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None

import pathlibex
from i18n import (
    _,
    get_available_languages,
    get_current_language,
    get_language_name,
    has_translation,
    set_language,
)
from python_package_utility import (
    OS_TO_PLATFORMS,
    PYPISIMPLE_AVAILABLE,
    PYTHON_VERSION_TO_ABI,
    DownloadConfig,
    load_settings,
    parse_package_condition,
    save_settings,
    start_download,
)
from tkinterex import CustomCheckbutton, CustomEntry, CustomListbox


def get_version() -> str:
    """pyproject.tomlからバージョン情報を取得する.

    Returns
    -------
    str
        バージョン番号
    """
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    if not pyproject_path.exists():
        return "1.0.0"

    if tomllib is None:
        raise RuntimeError(
            "tomli/tomllib が利用できません。Python 3.11未満の場合は tomli をインストールしてください。")

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
        return data.get("project", {}).get("version", "1.0.0")


# アプリケーションバージョン
VERSION = get_version()

# データディレクトリ
DATA_DIR = pathlibex.get_data_dir()


def _run_download_process(
        config: DownloadConfig, progress_queue: multiprocessing.Queue,
        stop_event: multiprocessing.synchronize.Event) -> None:
    """別プロセスでダウンロードを実行する.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定
    progress_queue : multiprocessing.Queue
        進捗情報を送信するキュー
    stop_event : multiprocessing.Event
        中止イベント
    """
    try:
        # パッケージリストの読み込み
        with open(config.package_list_file, "r", encoding="utf-8") as file:
            package_lines = [
                line.strip() for line in file.readlines() if line.strip()
            ]

        total_packages = len(package_lines)
        progress_queue.put({"total": total_packages, "current": 0})

        package_requirements_list = []
        for line in package_lines:
            if stop_event.is_set():
                progress_queue.put({"status": "cancelled"})
                return

            requirement = parse_package_condition("".join(line.split()))
            if requirement:
                package_requirements_list.append(requirement)

        # 各パッケージごとに進捗を更新
        for i, requirement in enumerate(package_requirements_list, 1):
            if stop_event.is_set():
                progress_queue.put({"status": "cancelled"})
                return

            progress_queue.put({
                "total": total_packages,
                "current": i,
                "package": requirement.package_name
            })

        # 実際のダウンロード処理（stop_eventを渡す）
        start_download(config, stop_event=stop_event)

        if stop_event.is_set():
            progress_queue.put({"status": "cancelled"})
        else:
            progress_queue.put({"status": "completed"})
    except (OSError, ValueError, RuntimeError) as e:
        progress_queue.put({"status": "error", "message": str(e)})
        sys.exit(1)


class MainWindow(Tk):
    """pythonパッケージダウンローダーのメインウィンドウ.

    Parameters
    ----------
    tk : tkinter.Tk
        親クラス.Tkのインスタンスを継承.
    """

    def __init__(self) -> None:
        """初期化."""
        super().__init__()

        # 保存された言語設定を読み込む
        settings = load_settings()
        if settings and "language" in settings:
            set_language(settings["language"])

        self.title(_("app_title"))
        self.geometry("600x600")  # ウィンドウサイズを設定
        self.progress_queue = None
        self.stop_event = None
        self.download_process = None
        # 進捗状態を保持する変数
        self.main_progress_text = ""
        self.dependency_progress_text = ""
        # 階層ごとの依存関係進捗を管理（level -> progress_text）
        self.dependency_progress_stack = {}
        self.setup_menu()
        self.setup_ui()

        # ウィンドウクローズ時の処理を設定
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        if settings:
            self.os_options_listbox.curselection_list = settings.get(
                "os_list", [])
            self.python_version_listbox.curselection_list = settings.get(
                "python_versions", [])
            # package_list_filesをリストとして読み込み（存在するファイルのみ）
            package_list_files = settings.get("package_list_files", [])
            # 存在するファイルのみをフィルタリング
            existing_files = [f for f in package_list_files if Path(f).exists()]
            self.package_list_combobox["values"] = existing_files
            if existing_files:
                self.package_list_combobox.current(0)
            self.dest_folder_entry.value = settings.get("dest_folder", "")
            self.pip_path_entry.value = settings.get("pip_path", "")
            self.proxy_user_entry.value = settings.get("proxy_user", "")
            self.proxy_password_entry.value = settings.get("proxy_password", "")
            self.proxy_server_entry.value = settings.get("proxy_server", "")
            self.proxy_port_entry.value = settings.get("proxy_port", "")
            self.include_source_check.value = settings.get(
                "include_source", False)
            self.include_deps_check.value = settings.get("incude_deps", False)
            self.use_proxy_checkbox.value = settings.get("use_proxy", False)
            self.toggle_proxy_widgets()
        else:
            # 初回起動時のデフォルト値設定
            # package_list.txtが存在する場合はそのパスをリストに追加
            if (DATA_DIR / "package_list.txt").exists():
                default_package_list_path = str(DATA_DIR / "package_list.txt")
                self.package_list_combobox["values"] = [
                    default_package_list_path
                ]
                self.package_list_combobox.current(0)

    def setup_menu(self) -> None:
        """メニューバーを設定する."""
        menubar = Menu(self)
        self.config(menu=menubar)

        # 言語メニュー
        language_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("menu_language"), menu=language_menu)

        # 利用可能な言語を取得
        available_languages = get_available_languages()
        current_lang = get_current_language()

        for lang_code in available_languages:
            # JSONファイルから言語名を取得
            lang_name = get_language_name(lang_code)
            # 現在の言語にチェックマークを表示
            if lang_code == current_lang:
                lang_name = "✓ " + lang_name
            language_menu.add_command(
                label=lang_name,
                command=lambda lc=lang_code: self.change_language(lc))

        # ヘルプメニュー
        help_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("menu_help"), menu=help_menu)
        help_menu.add_command(label=_("menu_help_content"),
                              command=self.show_help)
        help_menu.add_separator()
        help_menu.add_command(label=_("menu_about"), command=self.show_about)

    def change_language(self, lang_code: str) -> None:
        """言語を変更する.

        Parameters
        ----------
        lang_code : str
            言語コード（例: 'ja', 'en'）
        """
        # 設定を保存
        settings = load_settings()
        settings["language"] = lang_code
        save_settings(settings)

        # 言語を変更
        set_language(lang_code)

        # 再起動を促すメッセージを表示
        messagebox.showinfo(_("language_change_title"), _("language_changed"))

    def show_help(self) -> None:
        """ヘルプファイルを開く."""
        current_lang = get_current_language()
        help_file = Path(__file__).parent / "help" / f"help_{current_lang}.html"

        # ヘルプファイルが存在しない場合は英語版にフォールバック
        if not help_file.exists():
            help_file = Path(__file__).parent / "help" / "help_en.html"

        # ヘルプファイルが存在する場合は開く
        if help_file.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(help_file))
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(help_file)], check=False)
                else:
                    subprocess.run(["xdg-open", str(help_file)], check=False)
            except (OSError, subprocess.SubprocessError) as e:
                messagebox.showerror(_("error"),
                                     _("error_opening_help", error=str(e)))
        else:
            messagebox.showerror(_("error"), _("help_file_not_found"))

    def show_about(self) -> None:
        """バージョン情報を表示する."""
        messagebox.showinfo(_("about_title"), _("about_message",
                                                version=VERSION))

    def setup_ui(self) -> None:
        """GUIの各要素を設定する."""
        # pip使用選択
        pip_use_frame = Frame(self)
        pip_use_frame.pack(side="top", fill="x", padx=2, pady=2)
        pip_use_lbl = Label(pip_use_frame, text=_("download_method"))
        pip_use_lbl.pack(side="left", padx=10, pady=5)
        self.download_method_var = StringVar(value="pip")
        pip_radio = Radiobutton(
            pip_use_frame,
            text=_("use_pip"),
            variable=self.download_method_var,
            value="pip",
        )
        pip_radio.pack(side="left", padx=10, pady=5)
        no_pip_radio = Radiobutton(
            pip_use_frame,
            text=_("dont_use_pip"),
            variable=self.download_method_var,
            value="no_pip",
        )
        no_pip_radio.pack(side="left", padx=10, pady=5)
        # OS選択
        os_frame = Frame(self)
        os_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(os_frame, text=_("os_selection")).pack(side="left",
                                                     padx=10,
                                                     pady=5,
                                                     anchor="w")
        self.os_options = list(OS_TO_PLATFORMS.keys())
        self.os_options_listbox = CustomListbox(
            os_frame,
            selectmode="multiple",
            exportselection=False,
            height=min(3, len(self.os_options)),
        )
        self.os_options_listbox.pack(side="left",
                                     padx=10,
                                     pady=5,
                                     fill="both",
                                     expand=True)
        for os_option in self.os_options:
            self.os_options_listbox.insert(END, os_option)
        # Pythonバージョン選択（複数選択可能）
        python_version_frame = Frame(self)
        python_version_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(python_version_frame, text=_("python_version")).pack(side="left",
                                                                   padx=10,
                                                                   pady=5,
                                                                   anchor="w")
        self.python_versions = list(PYTHON_VERSION_TO_ABI.keys())
        self.python_version_listbox = CustomListbox(
            python_version_frame,
            selectmode="multiple",
            exportselection=False,
            height=min(3, len(self.python_versions)),
        )
        for version in self.python_versions:
            self.python_version_listbox.insert(END, version)
        self.python_version_listbox.pack(side="left",
                                         padx=10,
                                         pady=5,
                                         fill="both",
                                         expand=True)

        # パッケージリストファイル選択
        package_list_frame = Frame(self)
        package_list_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(package_list_frame, text=_("package_list_file")).pack(side="left",
                                                                    padx=10,
                                                                    pady=5,
                                                                    anchor="w")
        self.package_list_combobox = Combobox(
            package_list_frame,
            state="readonly",
        )
        self.package_list_combobox.pack(side="left",
                                        padx=10,
                                        pady=5,
                                        fill="both",
                                        expand=True)
        add_button = Button(package_list_frame,
                            text=_("add"),
                            command=self.add_package_list)
        add_button.pack(side="left", padx=2, pady=5, fill="x", expand=False)
        delete_button = Button(package_list_frame,
                               text=_("delete"),
                               command=self.delete_package_list)
        delete_button.pack(side="left", padx=2, pady=5, fill="x", expand=False)
        # ダウンロード先フォルダ選択
        dest_folder_frame = Frame(self)
        dest_folder_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(dest_folder_frame,
              text=_("download_destination")).pack(side="left",
                                                   padx=10,
                                                   pady=5,
                                                   anchor="w")
        self.dest_folder_entry = CustomEntry(
            dest_folder_frame,
            state="readonly",
        )
        self.dest_folder_entry.pack(side="left",
                                    padx=10,
                                    pady=5,
                                    fill="both",
                                    expand=True)
        # 初期値をデータディレクトリの downloads に設定
        default_dest_folder_path = DATA_DIR / "downloads"
        default_dest_folder_path.mkdir(parents=True, exist_ok=True)
        default_dest_folder = str(default_dest_folder_path)
        self.dest_folder_entry.value = default_dest_folder
        dest_folder_button = Button(dest_folder_frame,
                                    text=_("select"),
                                    command=self.select_dest_folder)
        dest_folder_button.pack(side="left",
                                padx=10,
                                pady=5,
                                fill="x",
                                expand=False)

        # pipパス指定
        pip_path_frame = Frame(self)
        pip_path_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(pip_path_frame, text=_("pip_path")).pack(side="left",
                                                       padx=10,
                                                       pady=5,
                                                       anchor="w")
        self.pip_path_entry = CustomEntry(pip_path_frame)
        self.pip_path_entry.pack(side="left",
                                 padx=10,
                                 pady=5,
                                 fill="both",
                                 expand=True)
        self.pip_path_entry.value = self.get_default_pip_path()
        pip_path_button = Button(pip_path_frame,
                                 text=_("select"),
                                 command=self.select_pip_path)
        pip_path_button.pack(side="left",
                             padx=10,
                             pady=5,
                             fill="x",
                             expand=False)

        # プロキシ設定
        proxy_setting_frame = Frame(self)
        proxy_setting_frame.pack(side="top", fill="x", padx=2, pady=2)
        use_proxy_frame = Frame(proxy_setting_frame)
        use_proxy_frame.pack(side="top", fill="x", padx=2, pady=0)
        self.use_proxy_checkbox = CustomCheckbutton(
            use_proxy_frame,
            text=_("use_proxy"),
            command=self.toggle_proxy_widgets,
        )
        self.use_proxy_checkbox.pack(side="left", padx=10, pady=2, anchor="w")
        self.use_proxy_checkbox.value = False
        proxy_user_frame = Frame(proxy_setting_frame)
        proxy_user_frame.pack(side="top", fill="x", padx=2, pady=0)
        Label(proxy_user_frame, text=_("proxy_username")).pack(side="left",
                                                               padx=10,
                                                               pady=2,
                                                               anchor="w")
        self.proxy_user_entry = CustomEntry(
            proxy_user_frame,
            state="disabled",
        )
        self.proxy_user_entry.pack(side="left",
                                   padx=10,
                                   pady=2,
                                   fill="both",
                                   expand=True)
        proxy_password_frame = Frame(proxy_setting_frame)
        proxy_password_frame.pack(side="top", fill="x", padx=2, pady=0)
        Label(proxy_password_frame, text=_("proxy_password")).pack(side="left",
                                                                   padx=10,
                                                                   pady=2,
                                                                   anchor="w")
        self.proxy_password_entry = CustomEntry(
            proxy_password_frame,
            state="disabled",
            show="*",
        )
        self.proxy_password_entry.pack(side="left",
                                       padx=10,
                                       pady=2,
                                       fill="both",
                                       expand=True)
        proxy_server_frame = Frame(proxy_setting_frame)
        proxy_server_frame.pack(side="top", fill="x", padx=2, pady=0)
        Label(proxy_server_frame, text=_("proxy_server")).pack(side="left",
                                                               padx=10,
                                                               pady=2,
                                                               anchor="w")
        self.proxy_server_entry = CustomEntry(
            proxy_server_frame,
            state="disabled",
        )
        self.proxy_server_entry.pack(side="left",
                                     padx=10,
                                     pady=2,
                                     fill="both",
                                     expand=True)
        proxy_port_frame = Frame(proxy_setting_frame)
        proxy_port_frame.pack(side="top", fill="x", padx=2, pady=0)
        Label(proxy_port_frame, text=_("proxy_port")).pack(side="left",
                                                           padx=10,
                                                           pady=2,
                                                           anchor="w")
        self.proxy_port_entry = CustomEntry(proxy_port_frame,
                                            state="disabled",
                                            validate="key")
        self.proxy_port_entry.pack(side="left",
                                   padx=10,
                                   pady=2,
                                   fill="both",
                                   expand=True)
        validatecommand = (
            proxy_port_frame.register(self.validate_port),
            "%P",
        )
        self.proxy_port_entry.configure(validatecommand=validatecommand)

        # ソース形式を含めるチェックボックス
        source_format_frame = Frame(self)
        source_format_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(source_format_frame, text=_("include_source")).pack(side="left",
                                                                  padx=10,
                                                                  pady=5,
                                                                  anchor="w")
        self.include_source_check = CustomCheckbutton(source_format_frame)
        self.include_source_check.pack(side="left", padx=10, pady=5, anchor="w")
        self.include_source_check.value = False
        include_deps_frame = Frame(self)
        include_deps_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(include_deps_frame,
              text=_("include_dependencies")).pack(side="left",
                                                   padx=10,
                                                   pady=5,
                                                   anchor="w")
        self.include_deps_check = CustomCheckbutton(include_deps_frame)
        self.include_deps_check.pack(side="left", padx=10, pady=5, anchor="w")
        self.include_deps_check.value = False
        # ダウンロード開始ボタン
        button_frame = Frame(self)
        button_frame.pack(side="top", fill="x", padx=2, pady=2)
        self.download_button = Button(button_frame,
                                      text=_("start_download"),
                                      command=self.on_download)
        self.download_button.pack(side="left",
                                  padx=10,
                                  pady=5,
                                  fill="x",
                                  expand=True)

        # 中止ボタン（初期状態は無効）
        self.cancel_button = Button(button_frame,
                                    text=_("cancel"),
                                    command=self.on_cancel,
                                    state="disabled")
        self.cancel_button.pack(side="left",
                                padx=10,
                                pady=5,
                                fill="x",
                                expand=True)

        # 設定を保存ボタン
        save_button = Button(button_frame,
                             text=_("save_settings"),
                             command=self.on_save_settings)
        save_button.pack(side="left", padx=10, pady=5, fill="x", expand=True)

        # ステータスバー
        status_frame = Frame(self)
        status_frame.pack(side="bottom", fill="x", padx=2, pady=2)
        self.status_label = Label(status_frame,
                                  text=_("ready"),
                                  anchor="w",
                                  relief="sunken")
        self.status_label.pack(side="left",
                               fill="x",
                               expand=True,
                               padx=5,
                               pady=2)

    def toggle_proxy_widgets(self) -> None:
        """プロキシ関連のウィジェットを有効化または無効化する."""
        state = "normal" if self.use_proxy_checkbox.value else "disabled"
        self.proxy_user_entry.config(state=state)
        self.proxy_password_entry.config(state=state)
        self.proxy_server_entry.config(state=state)
        self.proxy_port_entry.config(state=state)

    def validate_port(self, value: str) -> bool:
        """ポート番号が数字のみで構成されているかを検証する.

        Parameters
        ----------
        value : str
            入力された値.

        Returns
        -------
        bool
            数字のみの場合はTrue、それ以外はFalse.
        """
        return value.isdigit() or value == ""

    def add_package_list(self) -> None:
        """パッケージリストファイルを追加する."""
        current_path = self.package_list_combobox.get()
        initial_dir, initial_file = pathlibex.get_initial_dir_and_file(
            current_path, fallback_dir=str(DATA_DIR))

        file_path = filedialog.askopenfilename(
            title=_("select_package_list"),
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[
                (_("text_files"), "*.txt"),
                (_("all_files"), "*.*"),
            ],
        )
        if file_path:
            # 現在のリストを取得
            current_values = list(self.package_list_combobox["values"])
            # 重複チェック
            if file_path not in current_values:
                current_values.append(file_path)
                self.package_list_combobox["values"] = current_values
            # 追加したファイルを選択
            self.package_list_combobox.set(file_path)

    def delete_package_list(self) -> None:
        """選択中のパッケージリストファイルを削除する."""
        current_value = self.package_list_combobox.get()
        if not current_value:
            messagebox.showwarning(_("warning"),
                                   _("select_package_list_to_delete"))
            return

        # 確認ダイアログ
        if messagebox.askyesno(
                _("confirm"), _("remove_from_list",
                                current_value=current_value)):
            current_values = list(self.package_list_combobox["values"])
            if current_value in current_values:
                current_values.remove(current_value)
                self.package_list_combobox["values"] = current_values
                # リストが空でない場合は最初の項目を選択
                if current_values:
                    self.package_list_combobox.current(0)
                else:
                    self.package_list_combobox.set("")

    def select_dest_folder(self) -> None:
        """ダウンロード先フォルダを選択する."""
        current_path = self.dest_folder_entry.get()
        initial_dir, _file = pathlibex.get_initial_dir_and_file(
            current_path, fallback_dir=str(DATA_DIR))

        folder_path = filedialog.askdirectory(
            title=_("select_download_folder"),
            initialdir=initial_dir,
        )
        if folder_path:
            self.dest_folder_entry.value = folder_path

    def select_pip_path(self) -> None:
        """pipのパスを選択する."""
        current_path = self.pip_path_entry.get()
        initial_dir, initial_file = pathlibex.get_initial_dir_and_file(
            current_path, fallback_dir=str(DATA_DIR))

        file_path = filedialog.askopenfilename(
            title=_("select_pip_path"),
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[(_("executable_files"), "*.exe"),
                       (_("all_files"), "*.*")],
        )
        if file_path:
            self.pip_path_entry.value = file_path

    def on_download(self) -> None:
        """ダウンロード処理を開始する."""
        download_method = self.download_method_var.get()
        use_pip = download_method == "pip" or not PYPISIMPLE_AVAILABLE
        pip_path = self.pip_path_entry.get() if use_pip else ""
        os_list = self.os_options_listbox.curselection_list
        python_versions = self.python_version_listbox.curselection_list
        package_list_file = self.package_list_combobox.get()
        dest_folder = self.dest_folder_entry.get()
        include_source = self.include_source_check.value
        include_deps = self.include_deps_check.value

        # プロキシ情報を組み立て
        proxy = None
        if self.use_proxy_checkbox.value:
            proxy_user = self.proxy_user_entry.value
            proxy_password = self.proxy_password_entry.value
            proxy_server = self.proxy_server_entry.value
            proxy_port = self.proxy_port_entry.value

            if proxy_server and proxy_port:
                proxy = "http://"
                if proxy_user and proxy_password:
                    # パスワードをURLエンコード
                    encoded_password = urllib.parse.quote(proxy_password)
                    proxy += f"{proxy_user}:{encoded_password}@"
                proxy += f"{proxy_server}:{proxy_port}"

        # 環境変数にプロキシを設定
        if proxy:
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy

        if len(os_list) < 1:
            messagebox.showerror(_("error"), _("select_at_least_one_os"))
            return

        if len(python_versions) < 1:
            messagebox.showerror(_("error"),
                                 _("select_at_least_one_python_version"))
            return

        if not package_list_file:
            messagebox.showerror(_("error"), _("select_package_list_file"))
            return

        # パッケージリストファイルの存在チェック
        if not Path(package_list_file).exists():
            messagebox.showerror(_("error"),
                                 _("file_not_found", file=package_list_file))
            return

        if not dest_folder:
            messagebox.showerror(_("error"), _("select_download_destination"))
            return

        # 進捗情報用Queueと中止用Eventを作成
        self.progress_queue = multiprocessing.Queue()
        self.stop_event = multiprocessing.Event()

        # 各バージョンに対してダウンロードを実行
        config = DownloadConfig(
            os_list=os_list,
            python_versions=python_versions,
            package_list_file=package_list_file,
            dest_folder=dest_folder,
            include_source=include_source,
            include_deps=include_deps,
            proxy=proxy,
            use_pip=use_pip,
            pip_path=pip_path,
            progress_queue=self.progress_queue,
        )

        # ボタンの状態を変更
        self.download_button.config(state="disabled")
        self.cancel_button.config(state="normal")

        # 別プロセスでダウンロードを実行
        self.download_process = multiprocessing.Process(
            target=_run_download_process,
            args=(config, self.progress_queue, self.stop_event))
        self.download_process.start()

        # プロセスの完了を監視
        self._monitor_download_process()

    def _update_status_label(self) -> None:
        """ステータスラベルを更新する."""
        # 依存関係の階層ごとの進捗をまとめて表示
        if self.dependency_progress_stack:
            # level順に並べて表示
            dep_texts = [
                self.dependency_progress_stack[level]
                for level in sorted(self.dependency_progress_stack.keys())
                if self.dependency_progress_stack[level]  # 空文字は除外
            ]
            self.dependency_progress_text = " > ".join(dep_texts)
        else:
            self.dependency_progress_text = ""

        if self.main_progress_text and self.dependency_progress_text:
            text = (f"{self.main_progress_text} "
                    f"[{self.dependency_progress_text}]")
            self.status_label.config(text=text)
        elif self.main_progress_text:
            self.status_label.config(text=self.main_progress_text)
        elif self.dependency_progress_text:
            self.status_label.config(text=self.dependency_progress_text)

    def _monitor_download_process(self) -> None:
        """ダウンロードプロセスの完了を監視する."""
        # Queueから進捗情報を取得
        try:
            while not self.progress_queue.empty():
                progress = self.progress_queue.get_nowait()
                if "status" in progress:
                    if progress["status"] == "completed":
                        self.main_progress_text = ""
                        self.dependency_progress_text = ""
                        self.dependency_progress_stack.clear()
                        self.status_label.config(text=_("download_complete"))
                    elif progress["status"] == "cancelled":
                        self.main_progress_text = ""
                        self.dependency_progress_text = ""
                        self.dependency_progress_stack.clear()
                        self.status_label.config(text=_("download_cancelled"))
                    elif progress["status"] == "error":
                        error_msg = progress.get("message", _("unknown_error"))
                        self.main_progress_text = ""
                        self.dependency_progress_text = ""
                        self.dependency_progress_stack.clear()
                        self.status_label.config(
                            text=_("error_occurred", error_msg=error_msg))
                    elif progress["status"] == "downloading_dependencies":
                        # 総数表示は不要なので空文字で上書き（または何もしない）
                        level = progress.get("level", 0)
                        self.dependency_progress_stack[level] = ""
                        self._update_status_label()
                    elif progress["status"] == "downloading_dependency":
                        current = progress.get("current", 0)
                        total = progress.get("total", 0)
                        package = progress.get("package", "")
                        level = progress.get("level", 0)
                        self.dependency_progress_stack[
                            level] = f"{current}/{total}>{package}"
                        self._update_status_label()
                    elif progress["status"] == "dependency_complete":
                        # 指定された階層の依存関係ダウンロードが完了したら削除
                        level = progress.get("level", 0)
                        if level in self.dependency_progress_stack:
                            del self.dependency_progress_stack[level]
                        self._update_status_label()
                elif "total" in progress and "current" in progress:
                    total = progress["total"]
                    current = progress["current"]
                    package = progress.get("package", "")
                    if package:
                        self.main_progress_text = _("downloading_progress",
                                                    current=current,
                                                    total=total,
                                                    package=package)
                    else:
                        self.main_progress_text = _("downloading_simple",
                                                    current=current,
                                                    total=total)
                    self._update_status_label()
        except (EOFError, OSError):
            # Queue操作で発生しうる例外のみキャッチ
            pass

        if self.download_process.is_alive():
            # 100ms後に再度チェック
            self.after(100, self._monitor_download_process)
        else:
            # プロセス終了
            self.download_process.join()

            # ボタンの状態を復元
            self.download_button.config(state="normal")
            self.cancel_button.config(state="disabled")

            if self.download_process.exitcode == 0:
                # 成功
                messagebox.showinfo(_("complete"), _("all_packages_downloaded"))
            elif not self.stop_event.is_set():
                # エラー（中止ではない場合）
                messagebox.showerror(
                    _("error"),
                    _("download_error_exitcode",
                      exitcode=self.download_process.exitcode))

    def on_cancel(self) -> None:
        """ダウンロードを中止する."""
        if hasattr(self, 'stop_event'):
            self.stop_event.set()
            self.status_label.config(text=_("cancelling"))
            self.cancel_button.config(state="disabled")

    def on_closing(self) -> None:
        """ウィンドウを閉じる時の処理."""
        # ダウンロード中の場合は確認
        if self.download_process and self.download_process.is_alive():
            result = messagebox.askyesno(
                _("confirm"),
                _("download_in_progress_close_confirm")
                if has_translation("download_in_progress_close_confirm") else
                "Download is in progress. Do you want to cancel and close?")
            if not result:
                return

            # ダウンロードを中止
            if self.stop_event:
                self.stop_event.set()

            # プロセスの終了を待つ（最大5秒）
            if self.download_process:
                self.download_process.join(timeout=5)
                if self.download_process.is_alive():
                    # まだ終了していない場合は強制終了
                    self.download_process.terminate()
                    self.download_process.join(timeout=2)

        # ウィンドウを閉じる
        self.destroy()

    def get_default_pip_path(self) -> str:
        """実行環境のpipまたはpip3のパスを検索する.

        Returns
        -------
        str
            実行環境のpipまたはpip3のパス。見つからない場合は空文字列.
        """
        # pipを検索
        pip_path = shutil.which("pip")
        if pip_path:
            return pip_path

        # pip3を検索
        pip3_path = shutil.which("pip3")
        if pip3_path:
            return pip3_path

        # 見つからない場合は空文字列を返す
        return ""

    def on_save_settings(self) -> None:
        """現在の設定を保存する."""
        settings = {
            "os_list": self.os_options_listbox.curselection_list,
            "python_versions": self.python_version_listbox.curselection_list,
            "package_list_files": list(self.package_list_combobox["values"]),
            "dest_folder": self.dest_folder_entry.value,
            "pip_path": self.pip_path_entry.value,
            "proxy_user": self.proxy_user_entry.value,
            "proxy_password": self.proxy_password_entry.value,
            "proxy_server": self.proxy_server_entry.value,
            "proxy_port": self.proxy_port_entry.value,
            "include_source": self.include_source_check.value,
            "include_deps": self.include_deps_check.value,
            "use_proxy": self.use_proxy_checkbox.value,
        }
        save_settings(settings)
        messagebox.showinfo(_("save_complete"), _("settings_saved"))
