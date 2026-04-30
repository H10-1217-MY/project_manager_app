from dataclasses import asdict
from pathlib import Path

from core.file_service import FileService
from core.index_service import IndexService, PROJECTS_DIR_NAME, TRASH_DIR_NAME
from core.storage_service import StorageService
from utils.id_utils import IdUtils
from utils.time_utils import TimeUtils


STATUS_LIST = [
    "未着手",
    "進行中",
    "保留",
    "完了",
]


class ProjectService:
    def __init__(self, shared_root: Path):
        self.shared_root = shared_root
        self.projects_root = self.shared_root / PROJECTS_DIR_NAME
        self.trash_root = self.shared_root / TRASH_DIR_NAME
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

    def validate_status(self, status: str) -> tuple[bool, str]:
        if status not in STATUS_LIST:
            return False, f"不正なステータスです: {status}"
        return True, ""

    def _add_history(self, metadata: dict, action: str, detail: str):
        metadata.setdefault("history", [])
        metadata["history"].append({
            "timestamp": TimeUtils.now_iso(),
            "action": action,
            "detail": detail
        })

    def create_project(
        self,
        project_name: str,
        description: str,
        file_paths: list[str] | None = None,
        folder_paths: list[str] | None = None,
    ) -> dict:
        self.ensure_ready()

        ok, msg = self.validate_project_input(project_name)
        if not ok:
            raise ValueError(msg)

        file_paths = file_paths or []
        folder_paths = folder_paths or []

        project_id = IdUtils.generate_project_id()
        now = TimeUtils.now_iso()
        project_path = self.projects_root / project_id
        files_dir = project_path / "files"

        project_path.mkdir(parents=True, exist_ok=False)

        file_entries, skipped_files = self.file_service.copy_files_to_project(file_paths, files_dir)
        folder_entries, skipped_folders = self.file_service.copy_folders_to_project(folder_paths, files_dir)
        all_entries = file_entries + folder_entries
        skipped_count = skipped_files + skipped_folders

        metadata = {
            "project_id": project_id,
            "project_name": project_name.strip(),
            "description": description.strip(),
            "project_path": str(project_path),
            "status": "未着手",
            "created_at": now,
            "updated_at": now,
            "sections": {
                "overview": "",
                "requirements": "",
                "technology": "",
                "issues": "",
                "next_actions": ""
            },
            "history": [
                {
                    "timestamp": now,
                    "action": "created",
                    "detail": "プロジェクト作成"
                }
            ],
            "files": [asdict(entry) for entry in all_entries]
        }
        self.storage_service.save_metadata(project_path, metadata)

        index_entry = {
            "project_id": project_id,
            "project_name": project_name.strip(),
            "description": description.strip(),
            "project_path": str(project_path),
            "status": "未着手",
            "created_at": now,
            "updated_at": now,
        }
        self.index_service.add_project(index_entry)

        return {
            "project_id": project_id,
            "copied_count": len(all_entries),
            "skipped_count": skipped_count,
        }

    def get_projects(
        self,
        name_keyword: str = "",
        desc_keyword: str = "",
        sort_mode: str = "updated_desc"
    ) -> list:
        self.ensure_ready()
        return self.index_service.search_projects(name_keyword, desc_keyword, sort_mode)

    def get_project_detail(self, project_path: str) -> dict:
        return self.storage_service.load_metadata(Path(project_path))

    def update_project_info(
        self,
        project_path: str,
        project_name: str,
        description: str,
        status: str = "未着手",
    ):
        self.ensure_ready()

        ok, msg = self.validate_project_input(project_name)
        if not ok:
            raise ValueError(msg)

        ok, msg = self.validate_status(status)
        if not ok:
            raise ValueError(msg)

        project_dir = Path(project_path)
        metadata = self.storage_service.load_metadata(project_dir)

        old_status = metadata.get("status", "未着手")
        updated_at = TimeUtils.now_iso()

        metadata["project_name"] = project_name.strip()
        metadata["description"] = description.strip()
        metadata["status"] = status
        metadata["updated_at"] = updated_at

        self._add_history(metadata, "updated", "プロジェクト情報更新")

        if old_status != status:
            self._add_history(metadata, "status_changed", f"{old_status} → {status}")

        self.storage_service.save_metadata(project_dir, metadata)

        self.index_service.update_project(
            project_id=metadata["project_id"],
            project_name=metadata["project_name"],
            description=metadata["description"],
            updated_at=updated_at,
            status=status,
        )

    def update_status(self, project_path: str, status: str):
        self.ensure_ready()

        ok, msg = self.validate_status(status)
        if not ok:
            raise ValueError(msg)

        project_dir = Path(project_path)
        metadata = self.storage_service.load_metadata(project_dir)

        old_status = metadata.get("status", "未着手")
        if old_status == status:
            return

        updated_at = TimeUtils.now_iso()
        metadata["status"] = status
        metadata["updated_at"] = updated_at

        self._add_history(metadata, "status_changed", f"{old_status} → {status}")

        self.storage_service.save_metadata(project_dir, metadata)

        self.index_service.update_project(
            project_id=metadata["project_id"],
            project_name=metadata["project_name"],
            description=metadata["description"],
            updated_at=updated_at,
            status=status,
        )

    def delete_project(self, project_path: str) -> Path:
        self.ensure_ready()

        project_dir = Path(project_path)
        metadata = self.storage_service.load_metadata(project_dir)
        project_id = metadata["project_id"]

        trash_path = self.file_service.move_project_to_trash(project_dir, self.trash_root)
        self.index_service.remove_project(project_id)

        return trash_path