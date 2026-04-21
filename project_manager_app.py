import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


APP_TITLE = "Project Manager"
CONFIG_FILE = "config.json"
INDEX_FILE = "index.json"
INDEX_BAK_FILE = "index.json.bak"
INDEX_LOCK_FILE = "index.lock"
PROJECTS_DIR_NAME = "projects"
TRASH_DIR_NAME = "trash"
LOCK_RETRY_COUNT = 20
LOCK_RETRY_INTERVAL_MS = 300


# ==============================
# Models
# ==============================

@dataclass
class FileEntry:
    file_name: str
    relative_path: str
    size: int
    modified_at: str


@dataclass
class ProjectIndexEntry:
    project_id: str
    project_name: str
    description: str
    project_path: str
    created_at: str
    updated_at: str


@dataclass
class ProjectMetadata:
    project_id: str
    project_name: str
    description: str
    project_path: str
    created_at: str
    updated_at: str
    files: list


# ==============================
# Utils
# ==============================

class TimeUtils:
    @staticmethod
    def now_iso() -> str:
        return datetime.now().replace(microsecond=0).isoformat()

    @staticmethod
    def display(iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_str


class IdUtils:
    @staticmethod
    def generate_project_id() -> str:
        dt = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:4]
        return f"PJT_{dt}_{suffix}"


class JsonUtils:
    @staticmethod
    def read_json(path: Path, default=None):
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def atomic_write_json(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        bak_path = path.with_suffix(path.suffix + ".bak")

        if path.exists():
            shutil.copy2(path, bak_path)

        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        os.replace(tmp_path, path)


# ==============================
# Services
# ==============================

class ConfigService:
    DEFAULT_CONFIG = {
        "shared_root_path": "",
        "default_download_path": str(Path.home() / "Downloads" / "ProjectHub")
    }

    def __init__(self, config_path: Path):
        self.config_path = config_path

    def load_config(self) -> dict:
        if not self.config_path.exists():
            self.save_config(self.DEFAULT_CONFIG)
            return dict(self.DEFAULT_CONFIG)
        try:
            data = JsonUtils.read_json(self.config_path, default=dict(self.DEFAULT_CONFIG))
            for k, v in self.DEFAULT_CONFIG.items():
                data.setdefault(k, v)
            return data
        except Exception:
            return dict(self.DEFAULT_CONFIG)

    def save_config(self, config: dict):
        JsonUtils.atomic_write_json(self.config_path, config)


class LockError(Exception):
    pass


class IndexService:
    def __init__(self, shared_root: Path):
        self.shared_root = shared_root
        self.index_path = self.shared_root / INDEX_FILE
        self.lock_path = self.shared_root / INDEX_LOCK_FILE

    def ensure_structure(self):
        (self.shared_root / PROJECTS_DIR_NAME).mkdir(parents=True, exist_ok=True)
        (self.shared_root / TRASH_DIR_NAME).mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            JsonUtils.atomic_write_json(self.index_path, [])

    def load_index(self) -> list:
        data = JsonUtils.read_json(self.index_path, default=[])
        return data if isinstance(data, list) else []

    def save_index(self, index_data: list):
        JsonUtils.atomic_write_json(self.index_path, index_data)

    def acquire_lock(self):
        for _ in range(LOCK_RETRY_COUNT):
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(f"pid={os.getpid()} time={TimeUtils.now_iso()}\n")
                return
            except FileExistsError:
                root = tk._default_root
                if root:
                    root.update()
                    root.after(LOCK_RETRY_INTERVAL_MS)
                else:
                    import time
                    time.sleep(LOCK_RETRY_INTERVAL_MS / 1000)
        raise LockError("現在他の端末が更新中です。しばらく待ってから再試行してください。")

    def release_lock(self):
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
        except Exception:
            pass

    def add_project(self, entry: ProjectIndexEntry):
        self.acquire_lock()
        try:
            index_data = self.load_index()
            index_data.append(asdict(entry))
            self.save_index(index_data)
        finally:
            self.release_lock()

    def search_projects(self, name_keyword: str = "", desc_keyword: str = "", sort_mode: str = "updated_desc") -> list:
        items = self.load_index()
        name_keyword = name_keyword.strip().lower()
        desc_keyword = desc_keyword.strip().lower()

        def match(item):
            name_ok = True if not name_keyword else name_keyword in item.get("project_name", "").lower()
            desc_ok = True if not desc_keyword else desc_keyword in item.get("description", "").lower()
            return name_ok and desc_ok

        filtered = [item for item in items if match(item)]

        if sort_mode == "updated_desc":
            filtered.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        elif sort_mode == "updated_asc":
            filtered.sort(key=lambda x: x.get("updated_at", ""))
        elif sort_mode == "name_asc":
            filtered.sort(key=lambda x: x.get("project_name", "").lower())

        return filtered


class StorageService:
    def save_metadata(self, project_path: Path, metadata: ProjectMetadata):
        metadata_path = project_path / "metadata.json"
        JsonUtils.atomic_write_json(metadata_path, asdict(metadata))

    def load_metadata(self, project_path: Path) -> dict:
        metadata_path = project_path / "metadata.json"
        data = JsonUtils.read_json(metadata_path)
        if not isinstance(data, dict):
            raise ValueError("metadata.json の形式が不正です")
        return data


class FileService:
    def copy_files_to_project(self, src_paths: list[str], project_files_dir: Path) -> list[FileEntry]:
        project_files_dir.mkdir(parents=True, exist_ok=True)
        entries = []

        for src in src_paths:
            src_path = Path(src)
            if not src_path.exists() or not src_path.is_file():
                continue

            dest_name = self._resolve_duplicate_name(project_files_dir, src_path.name)
            dest_path = project_files_dir / dest_name
            shutil.copy2(src_path, dest_path)

            stat = dest_path.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime).replace(microsecond=0).isoformat()
            entries.append(
                FileEntry(
                    file_name=dest_name,
                    relative_path=f"files/{dest_name}",
                    size=stat.st_size,
                    modified_at=modified_at,
                )
            )
        return entries

    def copy_file_to_local(self, src_file: Path, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_name = self._resolve_duplicate_name(dest_dir, src_file.name)
        dest_path = dest_dir / dest_name
        shutil.copy2(src_file, dest_path)
        return dest_path

    def open_folder(self, path: Path):
        os.startfile(str(path))

    def _resolve_duplicate_name(self, dest_dir: Path, file_name: str) -> str:
        candidate = file_name
        stem = Path(file_name).stem
        suffix = Path(file_name).suffix
        count = 1
        while (dest_dir / candidate).exists():
            candidate = f"{stem}_{count}{suffix}"
            count += 1
        return candidate


class ProjectService:
    def __init__(self, shared_root: Path):
        self.shared_root = shared_root
        self.projects_root = self.shared_root / PROJECTS_DIR_NAME
        self.index_service = IndexService(shared_root)
        self.storage_service = StorageService()
        self.file_service = FileService()

    def ensure_ready(self):
        if not self.shared_root.exists():
            raise FileNotFoundError("共有フォルダに接続できません")
        self.index_service.ensure_structure()

    def validate_project_input(self, project_name: str) -> tuple[bool, str]:
        if not project_name.strip():
            return False, "プロジェクト名を入力してください"
        return True, ""

    def create_project(self, project_name: str, description: str, file_paths: list[str]) -> str:
        self.ensure_ready()
        ok, msg = self.validate_project_input(project_name)
        if not ok:
            raise ValueError(msg)

        project_id = IdUtils.generate_project_id()
        now = TimeUtils.now_iso()
        project_path = self.projects_root / project_id
        files_dir = project_path / "files"

        project_path.mkdir(parents=True, exist_ok=False)
        file_entries = self.file_service.copy_files_to_project(file_paths, files_dir)

        metadata = ProjectMetadata(
            project_id=project_id,
            project_name=project_name.strip(),
            description=description.strip(),
            project_path=str(project_path),
            created_at=now,
            updated_at=now,
            files=[asdict(entry) for entry in file_entries],
        )
        self.storage_service.save_metadata(project_path, metadata)

        index_entry = ProjectIndexEntry(
            project_id=project_id,
            project_name=project_name.strip(),
            description=description.strip(),
            project_path=str(project_path),
            created_at=now,
            updated_at=now,
        )
        self.index_service.add_project(index_entry)
        return project_id

    def get_projects(self, name_keyword: str = "", desc_keyword: str = "", sort_mode: str = "updated_desc") -> list:
        self.ensure_ready()
        return self.index_service.search_projects(name_keyword, desc_keyword, sort_mode)

    def get_project_detail(self, project_path: str) -> dict:
        return self.storage_service.load_metadata(Path(project_path))


# ==============================
# UI
# ==============================

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


class RegisterView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.selected_files = []
        self.project_name_var = tk.StringVar()
        self._build()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="プロジェクト登録", font=("Yu Gothic UI", 14, "bold")).pack(side="left")
        ttk.Button(top, text="戻る", command=self.app.show_home).pack(side="right")

        form = ttk.Frame(self)
        form.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(form, text="プロジェクト名").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.project_name_var, width=60).grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 8))

        ttk.Label(form, text="説明文").grid(row=2, column=0, sticky="w")
        self.desc_text = tk.Text(form, height=6, width=60)
        self.desc_text.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 8))

        ttk.Label(form, text="添付ファイル").grid(row=4, column=0, sticky="w")
        file_btns = ttk.Frame(form)
        file_btns.grid(row=5, column=0, columnspan=2, sticky="we", pady=(0, 8))
        ttk.Button(file_btns, text="ファイル追加", command=self.add_files).pack(side="left", padx=(0, 4))
        ttk.Button(file_btns, text="選択削除", command=self.remove_selected_file).pack(side="left")

        self.file_listbox = tk.Listbox(form, height=10, selectmode=tk.SINGLE)
        self.file_listbox.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=(0, 12))

        ttk.Button(form, text="登録", command=self.register_project).grid(row=7, column=1, sticky="e")

        form.columnconfigure(0, weight=1)
        form.rowconfigure(6, weight=1)

    def add_files(self):
        paths = filedialog.askopenfilenames(title="添付ファイルを選択")
        if not paths:
            return
        for p in paths:
            if p not in self.selected_files:
                self.selected_files.append(p)
                self.file_listbox.insert(tk.END, p)

    def remove_selected_file(self):
        selection = self.file_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        self.file_listbox.delete(idx)
        self.selected_files.pop(idx)

    def register_project(self):
        project_name = self.project_name_var.get().strip()
        description = self.desc_text.get("1.0", tk.END).strip()

        try:
            project_id = self.app.project_service.create_project(project_name, description, self.selected_files)
        except Exception as e:
            messagebox.showerror("登録エラー", str(e))
            return

        messagebox.showinfo("登録完了", f"プロジェクトを登録しました\n{project_id}")
        self.clear_form()
        self.app.home_view.refresh_status()

    def clear_form(self):
        self.project_name_var.set("")
        self.desc_text.delete("1.0", tk.END)
        self.file_listbox.delete(0, tk.END)
        self.selected_files.clear()


class BrowseView(ttk.Frame):
    SORT_OPTIONS = {
        "更新日 ↓": "updated_desc",
        "更新日 ↑": "updated_asc",
        "名前順": "name_asc",
    }

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.projects = []
        self.name_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        self.sort_var = tk.StringVar(value="更新日 ↓")
        self.current_detail = None
        self._build()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="プロジェクト閲覧", font=("Yu Gothic UI", 14, "bold")).pack(side="left")
        ttk.Button(top, text="戻る", command=self.app.show_home).pack(side="right")

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.pack(fill="both", expand=True, pady=(12, 0))

        left = ttk.Frame(body, padding=8)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=1)
        body.add(right, weight=2)

        ttk.Label(left, text="名前検索").pack(anchor="w")
        ttk.Entry(left, textvariable=self.name_var).pack(fill="x", pady=(0, 8))
        ttk.Label(left, text="説明文検索").pack(anchor="w")
        ttk.Entry(left, textvariable=self.desc_var).pack(fill="x", pady=(0, 8))
        ttk.Label(left, text="並び順").pack(anchor="w")
        ttk.Combobox(left, textvariable=self.sort_var, values=list(self.SORT_OPTIONS.keys()), state="readonly").pack(fill="x", pady=(0, 8))
        ttk.Button(left, text="検索", command=self.refresh_list).pack(fill="x", pady=(0, 8))

        self.project_list = tk.Listbox(left, height=20)
        self.project_list.pack(fill="both", expand=True)
        self.project_list.bind("<<ListboxSelect>>", self.on_select_project)

        self.detail_title = ttk.Label(right, text="プロジェクト未選択", font=("Yu Gothic UI", 13, "bold"))
        self.detail_title.pack(anchor="w")
        self.detail_desc = ttk.Label(right, text="", wraplength=500, justify="left")
        self.detail_desc.pack(anchor="w", pady=(8, 8))
        self.detail_info = ttk.Label(right, text="", justify="left")
        self.detail_info.pack(anchor="w", pady=(0, 8))

        ttk.Label(right, text="ファイル一覧").pack(anchor="w")
        self.file_list = tk.Listbox(right, height=15)
        self.file_list.pack(fill="both", expand=True, pady=(4, 8))

        file_btns = ttk.Frame(right)
        file_btns.pack(fill="x")
        ttk.Button(file_btns, text="ファイル取得", command=self.download_selected_file).pack(side="left", padx=(0, 4))
        ttk.Button(file_btns, text="フォルダを開く", command=self.open_project_folder).pack(side="left")

    def refresh_list(self):
        try:
            sort_mode = self.SORT_OPTIONS[self.sort_var.get()]
            self.projects = self.app.project_service.get_projects(
                name_keyword=self.name_var.get(),
                desc_keyword=self.desc_var.get(),
                sort_mode=sort_mode,
            )
        except Exception as e:
            messagebox.showerror("読込エラー", str(e))
            return

        self.project_list.delete(0, tk.END)
        for item in self.projects:
            label = f"{item['project_name']} | {TimeUtils.display(item['updated_at'])}"
            self.project_list.insert(tk.END, label)

        self.clear_detail()

    def on_select_project(self, _event=None):
        sel = self.project_list.curselection()
        if not sel:
            return
        idx = sel[0]
        project = self.projects[idx]
        try:
            detail = self.app.project_service.get_project_detail(project["project_path"])
        except Exception as e:
            messagebox.showerror("詳細読込エラー", str(e))
            return
        self.current_detail = detail
        self.show_detail(detail)

    def show_detail(self, detail: dict):
        self.detail_title.config(text=detail.get("project_name", ""))
        self.detail_desc.config(text=detail.get("description", ""))
        info = (
            f"プロジェクトID: {detail.get('project_id', '')}\n"
            f"作成日: {TimeUtils.display(detail.get('created_at', ''))}\n"
            f"更新日: {TimeUtils.display(detail.get('updated_at', ''))}"
        )
        self.detail_info.config(text=info)
        self.file_list.delete(0, tk.END)
        for file_info in detail.get("files", []):
            text = f"{file_info['file_name']} ({file_info['size']} bytes)"
            self.file_list.insert(tk.END, text)

    def clear_detail(self):
        self.current_detail = None
        self.detail_title.config(text="プロジェクト未選択")
        self.detail_desc.config(text="")
        self.detail_info.config(text="")
        self.file_list.delete(0, tk.END)

    def download_selected_file(self):
        if not self.current_detail:
            messagebox.showwarning("未選択", "プロジェクトを選択してください")
            return
        sel = self.file_list.curselection()
        if not sel:
            messagebox.showwarning("未選択", "ファイルを選択してください")
            return

        file_info = self.current_detail["files"][sel[0]]
        project_path = Path(self.current_detail["project_path"])
        src_file = project_path / file_info["relative_path"]
        default_dir = self.app.config.get("default_download_path", str(Path.home() / "Downloads"))
        dest_dir = filedialog.askdirectory(title="保存先を選択", initialdir=default_dir)
        if not dest_dir:
            return

        try:
            saved = self.app.project_service.file_service.copy_file_to_local(src_file, Path(dest_dir))
            messagebox.showinfo("完了", f"保存しました\n{saved}")
        except Exception as e:
            messagebox.showerror("コピーエラー", str(e))

    def open_project_folder(self):
        if not self.current_detail:
            messagebox.showwarning("未選択", "プロジェクトを選択してください")
            return
        try:
            self.app.project_service.file_service.open_folder(Path(self.current_detail["project_path"]))
        except Exception as e:
            messagebox.showerror("フォルダ表示エラー", str(e))


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1000x700")

        self.config_service = ConfigService(Path(CONFIG_FILE))
        self.config = self.config_service.load_config()
        self.project_service = ProjectService(Path(self.config.get("shared_root_path", ".")) if self.config.get("shared_root_path") else Path("."))

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


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
