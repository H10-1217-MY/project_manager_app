from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.config_service import ConfigService
from core.project_service import ProjectService
from ui.register_view import RegisterView
from ui.browse_view import BrowseView


APP_TITLE = "Project Manager"
CONFIG_FILE = "config.json"


class HomeView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.status_var = tk.StringVar(value="状態確認中...")
        self._build()

    def _build(self):
        ttk.Label(self, text=APP_TITLE, font=("Yu Gothic UI", 18, "bold")).pack(pady=(0, 20))

        status_frame = ttk.LabelFrame(self, text="共有フォルダ状態", padding=12)
        status_frame.pack(fill="x", pady=(0, 16))
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor="w")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=8)

        ttk.Button(btn_frame, text="登録画面へ", command=self.app.show_register).pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="閲覧画面へ", command=self.app.show_browse).pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="設定", command=self.app.show_settings).pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="終了", command=self.app.root.destroy).pack(fill="x", pady=4)

    def refresh_status(self):
        try:
            self.app.project_service.ensure_ready()
            self.status_var.set("共有フォルダに接続済み")
        except Exception as e:
            self.status_var.set(f"共有フォルダに接続できません: {e}")


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config_service: ConfigService, current_config: dict, on_saved):
        super().__init__(parent)
        self.title("設定")
        self.resizable(False, False)
        self.config_service = config_service
        self.on_saved = on_saved

        self.shared_root_var = tk.StringVar(value=current_config.get("shared_root_path", ""))
        self.download_var = tk.StringVar(value=current_config.get("default_download_path", ""))

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="共有フォルダパス").grid(row=0, column=0, sticky="w")
        ttk.Entry(body, textvariable=self.shared_root_var, width=60).grid(row=1, column=0, sticky="we", padx=(0, 8))
        ttk.Button(body, text="参照", command=self._browse_shared_root).grid(row=1, column=1, sticky="e")

        ttk.Label(body, text="既定の保存先").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(body, textvariable=self.download_var, width=60).grid(row=3, column=0, sticky="we", padx=(0, 8))
        ttk.Button(body, text="参照", command=self._browse_download_root).grid(row=3, column=1, sticky="e")

        btns = ttk.Frame(body)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(btns, text="保存", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="閉じる", command=self.destroy).pack(side="left", padx=4)

        body.columnconfigure(0, weight=1)

        self.transient(parent)
        self.grab_set()

    def _browse_shared_root(self):
        path = filedialog.askdirectory(title="共有フォルダを選択")
        if path:
            self.shared_root_var.set(path)

    def _browse_download_root(self):
        path = filedialog.askdirectory(title="既定の保存先を選択")
        if path:
            self.download_var.set(path)

    def _save(self):
        config = {
            "shared_root_path": self.shared_root_var.get().strip(),
            "default_download_path": self.download_var.get().strip(),
        }
        self.config_service.save_config(config)
        self.on_saved(config)
        messagebox.showinfo("設定", "設定を保存しました")
        self.destroy()


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1000x700")

        self.config_service = ConfigService(Path(CONFIG_FILE))
        self.config = self.config_service.load_config()

        shared_root = self.config.get("shared_root_path", "").strip()
        self.project_service = ProjectService(Path(shared_root) if shared_root else Path("."))

        self.container = ttk.Frame(root)
        self.container.pack(fill="both", expand=True)

        self.home_view = HomeView(self.container, self)
        self.register_view = RegisterView(self.container, self)
        self.browse_view = BrowseView(self.container, self)

        for view in (self.home_view, self.register_view, self.browse_view):
            view.grid(row=0, column=0, sticky="nsew")

        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        self.show_home()

    def refresh_services(self):
        shared_root = self.config.get("shared_root_path", "").strip()
        self.project_service = ProjectService(Path(shared_root) if shared_root else Path("."))
        self.home_view.refresh_status()
        self.browse_view.refresh_list()

    def show_home(self):
        self.home_view.refresh_status()
        self.home_view.tkraise()

    def show_register(self):
        self.register_view.tkraise()

    def show_browse(self):
        self.browse_view.refresh_list()
        self.browse_view.tkraise()

    def show_settings(self):
        SettingsDialog(self.root, self.config_service, self.config, self.on_settings_saved)

    def on_settings_saved(self, config: dict):
        self.config = config
        self.refresh_services()