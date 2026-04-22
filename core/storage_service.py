from pathlib import Path

from utils.json_utils import JsonUtils


class StorageService:
    def save_metadata(self, project_path: Path, metadata: dict):
        metadata_path = project_path / "metadata.json"
        JsonUtils.atomic_write_json(metadata_path, metadata)

    def load_metadata(self, project_path: Path) -> dict:
        metadata_path = project_path / "metadata.json"
        data = JsonUtils.read_json(metadata_path)

        if not isinstance(data, dict):
            raise ValueError("metadata.json の形式が不正です")

        # 互換補完
        if "project_path" not in data:
            data["project_path"] = str(project_path)

        if "status" not in data:
            data["status"] = "未着手"

        if "sections" not in data:
            data["sections"] = {
                "overview": "",
                "requirements": "",
                "technology": "",
                "issues": "",
                "next_actions": ""
            }

        if "history" not in data:
            data["history"] = []

        if "files" not in data:
            data["files"] = []

        return data