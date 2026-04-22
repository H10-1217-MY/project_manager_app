import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class RegisterView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.selected_files = []
        self.selected_folders = []
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
        ttk.Entry(form, textvariable=self.project_name_var, width=60).grid(
            row=1, column=0, columnspan=2, sticky="we", pady=(0, 8)
        )

        ttk.Label(form, text="説明文").grid(row=2, column=0, sticky="w")
        self.desc_text = tk.Text(form, height=6, width=60)
        self.desc_text.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 8))

        ttk.Label(form, text="追加対象").grid(row=4, column=0, sticky="w")
        file_btns = ttk.Frame(form)
        file_btns.grid(row=5, column=0, columnspan=2, sticky="we", pady=(0, 8))

        ttk.Button(file_btns, text="ファイル追加", command=self.add_files).pack(side="left", padx=(0, 4))
        ttk.Button(file_btns, text="フォルダ追加", command=self.add_folder).pack(side="left", padx=(0, 4))
        ttk.Button(file_btns, text="選択削除", command=self.remove_selected_item).pack(side="left")

        self.file_listbox = tk.Listbox(form, height=12, selectmode=tk.SINGLE)
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
                self.file_listbox.insert(tk.END, f"[FILE] {p}")

    def add_folder(self):
        path = filedialog.askdirectory(title="フォルダを選択")
        if not path:
            return

        if path not in self.selected_folders:
            self.selected_folders.append(path)
            self.file_listbox.insert(tk.END, f"[DIR]  {path}")

    def remove_selected_item(self):
        selection = self.file_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        value = self.file_listbox.get(idx)
        self.file_listbox.delete(idx)

        if value.startswith("[FILE] "):
            target = value.replace("[FILE] ", "", 1)
            if target in self.selected_files:
                self.selected_files.remove(target)
        elif value.startswith("[DIR]  "):
            target = value.replace("[DIR]  ", "", 1)
            if target in self.selected_folders:
                self.selected_folders.remove(target)

    def register_project(self):
        project_name = self.project_name_var.get().strip()
        description = self.desc_text.get("1.0", tk.END).strip()

        try:
            result = self.app.project_service.create_project(
                project_name=project_name,
                description=description,
                file_paths=self.selected_files,
                folder_paths=self.selected_folders,
            )
        except Exception as e:
            messagebox.showerror("登録エラー", str(e))
            return

        message = (
            f"プロジェクトを登録しました\n"
            f"{result['project_id']}\n\n"
            f"登録ファイル数: {result['copied_count']}\n"
            f"除外・スキップ件数: {result['skipped_count']}"
        )
        messagebox.showinfo("登録完了", message)

        self.clear_form()
        self.app.home_view.refresh_status()

    def clear_form(self):
        self.project_name_var.set("")
        self.desc_text.delete("1.0", tk.END)
        self.file_listbox.delete(0, tk.END)
        self.selected_files.clear()
        self.selected_folders.clear()