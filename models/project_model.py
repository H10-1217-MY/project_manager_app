from dataclasses import dataclass


@dataclass
class FileEntry:
    file_name: str
    relative_path: str
    size: int
    modified_at: str


@dataclass
class ProjectIndexEntry:
    project_id: str
    project_name: str
    description: str
    project_path: str
    created_at: str
    updated_at: str


@dataclass
class ProjectMetadata:
    project_id: str
    project_name: str
    description: str
    project_path: str
    created_at: str
    updated_at: str
    files: list