import os
import shutil
from pathlib import Path
from datetime import datetime

from models.project_model import FileEntry


class FileService:
    def copy_files_to_project(self, src_paths: list[str], project_files_dir: Path) -> list[FileEntry]:
        project_files_dir.mkdir(parents=True, exist_ok=True)
        entries = []

        for src in src_paths:
            src_path = Path(src)
            if not src_path.exists() or not src_path.is_file():
                continue

            dest_name = self._resolve_duplicate_name(project_files_dir, src_path.name)
            dest_path = project_files_dir / dest_name
            shutil.copy2(src_path, dest_path)

            stat = dest_path.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime).replace(microsecond=0).isoformat()

            entries.append(
                FileEntry(
                    file_name=dest_name,
                    relative_path=f"files/{dest_name}",
                    size=stat.st_size,
                    modified_at=modified_at,
                )
            )

        return entries

    def copy_file_to_local(self, src_file: Path, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_name = self._resolve_duplicate_name(dest_dir, src_file.name)
        dest_path = dest_dir / dest_name
        shutil.copy2(src_file, dest_path)
        return dest_path

    def open_folder(self, path: Path):
        os.startfile(str(path))

    def _resolve_duplicate_name(self, dest_dir: Path, file_name: str) -> str:
        candidate = file_name
        stem = Path(file_name).stem
        suffix = Path(file_name).suffix
        count = 1

        while (dest_dir / candidate).exists():
            candidate = f"{stem}_{count}{suffix}"
            count += 1

        return candidate