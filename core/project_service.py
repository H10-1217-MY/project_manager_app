from dataclasses import asdict
from pathlib import Path

from core.file_service import FileService
from core.index_service import IndexService, PROJECTS_DIR_NAME
from core.storage_service import StorageService
from models.project_model import ProjectIndexEntry, ProjectMetadata
from utils.id_utils import IdUtils
from utils.time_utils import TimeUtils


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