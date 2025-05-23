"""Project loading and saving utilities."""

from pathlib import Path
from typing import Union
from ..core.project import Project
from .file_handler import FileHandler


class ProjectLoader:
    """Handles loading and saving projects."""
    
    def __init__(self):
        self.file_handler = FileHandler()
    
    def load_project(self, project_file: Union[str, Path]) -> Project:
        """Load project from file."""
        data = self.file_handler.read_json(project_file)
        return Project.from_dict(data)
    
    def save_project(self, project: Project, project_file: Union[str, Path]) -> None:
        """Save project to file."""
        self.file_handler.write_json(project_file, project.to_dict())
