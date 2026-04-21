from pathlib import Path


class PathUtils:
    @staticmethod
    def ensure_dir(path: Path):
        path.mkdir(parents=True, exist_ok=True)