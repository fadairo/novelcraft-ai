"""Project management for NovelCraft AI."""

from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from .document import Document
from .character import CharacterManager


class Project:
    """Represents a novel writing project."""
    
    def __init__(
        self,
        title: str = "",
        author: str = "",
        project_path: Optional[Path] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.title = title
        self.author = author
        self.project_path = project_path
        self.metadata = metadata or {}
        self.document = Document(title, author)
        self.characters = CharacterManager()
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for serialization."""
        return {
            "title": self.title,
            "author": self.author,
            "project_path": str(self.project_path) if self.project_path else None,
            "metadata": self.metadata,
            "document": self.document.to_dict(),
            "characters": self.characters.to_dict(),
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Create project from dictionary."""
        project = cls(
            title=data.get("title", ""),
            author=data.get("author", ""),
            project_path=Path(data["project_path"]) if data.get("project_path") else None,
            metadata=data.get("metadata", {}),
        )
        
        if "document" in data:
            project.document = Document.from_dict(data["document"])
        
        if "characters" in data:
            project.characters = CharacterManager.from_dict(data["characters"])
        
        if "created_at" in data:
            project.created_at = datetime.fromisoformat(data["created_at"])
        if "modified_at" in data:
            project.modified_at = datetime.fromisoformat(data["modified_at"])
        
        return project
