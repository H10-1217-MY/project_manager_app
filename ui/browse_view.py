from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from utils.time_utils import TimeUtils


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
        ttk.Combobox(
            left,
            textvariable=self.sort_var,
            values=list(self.SORT_OPTIONS.keys()),
            state="readonly"
        ).pack(fill="x", pady=(0, 8))

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
        selection = self.project_list.curselection()
        if not selection:
            return

        idx = selection[0]
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

        selection = self.file_list.curselection()
        if not selection:
            messagebox.showwarning("未選択", "ファイルを選択してください")
            return

        file_info = self.current_detail["files"][selection[0]]
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