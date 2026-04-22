import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

from models.project_model import FileEntry


class FileService:
    EXCLUDED_DIR_NAMES = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
        "build",
        "dist",
    }

    EXCLUDED_FILE_SUFFIXES = {
        ".pyc",
        ".pyo",
    }

    EXCLUDED_FILE_NAMES = {
        "Thumbs.db",
        ".DS_Store",
    }

    def copy_files_to_project(self, src_paths: list[str], project_files_dir: Path) -> tuple[list[FileEntry], int]:
        project_files_dir.mkdir(parents=True, exist_ok=True)
        entries = []
        skipped_count = 0

        for src in src_paths:
            src_path = Path(src)
            if not src_path.exists() or not src_path.is_file():
                skipped_count += 1
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

        return entries, skipped_count

    def copy_folders_to_project(self, src_dirs: list[str], project_files_dir: Path) -> tuple[list[FileEntry], int]:
        project_files_dir.mkdir(parents=True, exist_ok=True)
        entries = []
        skipped_count = 0

        for src_dir in src_dirs:
            src_dir_path = Path(src_dir)
            if not src_dir_path.exists() or not src_dir_path.is_dir():
                skipped_count += 1
                continue

            top_name = self._resolve_duplicate_name(project_files_dir, src_dir_path.name)
            dest_root = project_files_dir / top_name
            dest_root.mkdir(parents=True, exist_ok=True)

            for root, dirs, files in os.walk(src_dir_path):
                root_path = Path(root)

                original_dir_count = len(dirs)
                dirs[:] = [d for d in dirs if not self._is_excluded_dir_name(d)]
                skipped_count += original_dir_count - len(dirs)

                for file_name in files:
                    src_path = root_path / file_name

                    if self._is_excluded_file(src_path):
                        skipped_count += 1
                        continue

                    rel_inside = src_path.relative_to(src_dir_path)
                    dest_path = dest_root / rel_inside
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dest_path)

                    stat = dest_path.stat()
                    modified_at = datetime.fromtimestamp(stat.st_mtime).replace(microsecond=0).isoformat()

                    relative_path = Path("files") / top_name / rel_inside
                    entries.append(
                        FileEntry(
                            file_name=src_path.name,
                            relative_path=str(relative_path).replace("\\", "/"),
                            size=stat.st_size,
                            modified_at=modified_at,
                        )
                    )

        return entries, skipped_count

    def copy_file_to_local(self, src_file: Path, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_name = self._resolve_duplicate_name(dest_dir, src_file.name)
        dest_path = dest_dir / dest_name
        shutil.copy2(src_file, dest_path)
        return dest_path

    def export_project_to_zip(self, project_path: Path, zip_path: Path) -> Path:
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in project_path.rglob("*"):
                if path.is_file():
                    arcname = path.relative_to(project_path)
                    zf.write(path, arcname=str(arcname))

        return zip_path

    def move_project_to_trash(self, project_path: Path, trash_root: Path) -> Path:
        trash_root.mkdir(parents=True, exist_ok=True)
        dest_name = self._resolve_duplicate_name(trash_root, project_path.name)
        dest_path = trash_root / dest_name
        shutil.move(str(project_path), str(dest_path))
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

    def _is_excluded_dir_name(self, dir_name: str) -> bool:
        return dir_name in self.EXCLUDED_DIR_NAMES

    def _is_excluded_file(self, file_path: Path) -> bool:
        if file_path.name in self.EXCLUDED_FILE_NAMES:
            return True
        if file_path.suffix.lower() in self.EXCLUDED_FILE_SUFFIXES:
            return True
        return False