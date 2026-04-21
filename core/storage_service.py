from pathlib import Path
from dataclasses import asdict

from models.project_model import ProjectMetadata
from utils.json_utils import JsonUtils


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