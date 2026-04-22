import os
import time
from dataclasses import asdict
from pathlib import Path

from models.project_model import ProjectIndexEntry
from utils.json_utils import JsonUtils
from utils.time_utils import TimeUtils


INDEX_FILE = "index.json"
INDEX_LOCK_FILE = "index.lock"
PROJECTS_DIR_NAME = "projects"
TRASH_DIR_NAME = "trash"
LOCK_RETRY_COUNT = 20
LOCK_RETRY_INTERVAL_SEC = 0.3


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
                time.sleep(LOCK_RETRY_INTERVAL_SEC)

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

    def update_project(self, project_id: str, project_name: str, description: str, updated_at: str):
        self.acquire_lock()
        try:
            index_data = self.load_index()
            found = False

            for item in index_data:
                if item.get("project_id") == project_id:
                    item["project_name"] = project_name
                    item["description"] = description
                    item["updated_at"] = updated_at
                    found = True
                    break

            if not found:
                raise ValueError("index.json 内に対象プロジェクトが見つかりません")

            self.save_index(index_data)
        finally:
            self.release_lock()

    def remove_project(self, project_id: str):
        self.acquire_lock()
        try:
            index_data = self.load_index()
            new_index = [item for item in index_data if item.get("project_id") != project_id]

            if len(new_index) == len(index_data):
                raise ValueError("index.json 内に削除対象プロジェクトが見つかりません")

            self.save_index(new_index)
        finally:
            self.release_lock()

    def search_projects(
        self,
        name_keyword: str = "",
        desc_keyword: str = "",
        sort_mode: str = "updated_desc"
    ) -> list:
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