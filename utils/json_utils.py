import json
import os
import shutil
from pathlib import Path


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