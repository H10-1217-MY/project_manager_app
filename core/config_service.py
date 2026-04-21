from pathlib import Path

from utils.json_utils import JsonUtils


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