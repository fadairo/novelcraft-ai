"""Project management for NovelCraft AI with file-based architecture."""

from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from .document import Document
from .character import CharacterManager


class Project:
    """Represents a novel writing project with file-based content management."""
    
    def __init__(
        self,
        title: str = "",
        author: str = "",
        project_path: Optional[Path] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.title = title
        self.author = author
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.metadata = metadata or {}
        
        # Initialize document with project path
        self.document = Document(title, author)
        self.document.set_project_path(self.project_path)
        
        self.characters = CharacterManager()
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        
        # Ensure project directory structure exists
        self._ensure_project_structure()
    
    def _ensure_project_structure(self) -> None:
        """Ensure the project directory structure exists."""
        if not self.project_path.exists():
            self.project_path.mkdir(parents=True, exist_ok=True)
        
        # Create standard directories
        (self.project_path / "chapters").mkdir(exist_ok=True)
        (self.project_path / "characters").mkdir(exist_ok=True)
        (self.project_path / "assets").mkdir(exist_ok=True)
    
    def discover_existing_content(self) -> Dict[str, List[str]]:
        """Discover existing content files in the project directory."""
        discovered = {
            "chapters": [],
            "characters": [],
            "other_files": []
        }
        
        # Discover chapter files
        chapters_dir = self.project_path / "chapters"
        if chapters_dir.exists():
            chapter_files = list(chapters_dir.glob("*.md"))
            for file_path in chapter_files:
                discovered["chapters"].append(str(file_path.relative_to(self.project_path)))
        
        # Discover character files
        characters_dir = self.project_path / "characters"
        if characters_dir.exists():
            character_files = list(characters_dir.glob("*.md"))
            for file_path in character_files:
                discovered["characters"].append(str(file_path.relative_to(self.project_path)))
        
        # Discover other markdown files in project root
        for file_path in self.project_path.glob("*.md"):
            if file_path.name not in ["README.md"]:
                discovered["other_files"].append(file_path.name)
        
        return discovered
    
    def import_existing_chapters(self) -> List[str]:
        """Import existing chapter files into the project."""
        imported = []
        
        # Discover and import chapter files
        chapter_refs = self.document.discover_chapter_files()
        
        for chapter_ref in chapter_refs:
            self.document.add_chapter(chapter_ref)
            imported.append(f"Chapter {chapter_ref.number}: {chapter_ref.title}")
        
        if imported:
            self.modified_at = datetime.now()
        
        return imported
    
    def create_chapter(self, number: int, title: str, content: str = "") -> bool:
        """Create a new chapter with content."""
        try:
            chapter_ref = self.document.create_chapter_from_content(number, title, content)
            self.modified_at = datetime.now()
            return True
        except Exception as e:
            print(f"Error creating chapter: {e}")
            return False
    
    def get_chapter_content(self, chapter_number: int) -> str:
        """Get the content of a specific chapter."""
        return self.document.get_chapter_content(chapter_number)
    
    def update_chapter_content(self, chapter_number: int, content: str) -> bool:
        """Update the content of a specific chapter."""
        success = self.document.update_chapter_content(chapter_number, content)
        if success:
            self.modified_at = datetime.now()
        return success
    
    def get_chapter_files(self) -> Dict[int, str]:
        """Get a mapping of chapter numbers to file paths."""
        return {
            num: chapter.file_path 
            for num, chapter in self.document.chapters.items() 
            if chapter.file_path
        }
    
    def sync_with_files(self) -> None:
        """Sync project metadata with all files."""
        self.document.sync_all_chapters()
        self.modified_at = datetime.now()
    
    def get_project_statistics(self) -> Dict[str, Any]:
        """Get comprehensive project statistics."""
        # Ensure we have latest data
        self.sync_with_files()
        
        chapters = self.document.get_chapters_sorted()
        total_words = self.document.calculate_word_count()
        
        stats = {
            "title": self.title,
            "author": self.author,
            "total_chapters": len(chapters),
            "total_words": total_words,
            "target_words": self.document.target_word_count,
            "progress_percentage": self.document.get_progress_percentage(),
            "average_chapter_length": total_words // len(chapters) if chapters else 0,
            "characters_count": len(self.characters.characters),
            "missing_chapters": self.document.find_missing_chapters(),
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }
        
        # Chapter-by-chapter breakdown
        stats["chapters"] = []
        for chapter in chapters:
            word_count = chapter.get_total_word_count(self.project_path)
            stats["chapters"].append({
                "number": chapter.number,
                "title": chapter.title,
                "words": word_count,
                "status": chapter.status,
                "file_path": chapter.file_path,
                "has_file": bool(chapter.file_path and 
                               chapter.get_file_path(self.project_path) and 
                               chapter.get_file_path(self.project_path).exists())
            })
        
        return stats
    
    def create_outline_file(self, outline_content: str) -> bool:
        """Create or update the outline.md file."""
        try:
            outline_path = self.project_path / "outline.md"
            outline_path.write_text(f"# Outline\n\n{outline_content}", encoding='utf-8')
            self.document.outline = outline_content
            self.modified_at = datetime.now()
            return True
        except Exception as e:
            print(f"Error creating outline file: {e}")
            return False
    
    def create_synopsis_file(self, synopsis_content: str) -> bool:
        """Create or update the synopsis.md file."""
        try:
            synopsis_path = self.project_path / "synopsis.md"
            synopsis_path.write_text(f"# Synopsis\n\n{synopsis_content}", encoding='utf-8')
            self.document.synopsis = synopsis_content
            self.modified_at = datetime.now()
            return True
        except Exception as e:
            print(f"Error creating synopsis file: {e}")
            return False
    
    def create_characters_file(self, characters_content: str) -> bool:
        """Create or update the characters.md file."""
        try:
            characters_path = self.project_path / "characters.md"
            characters_path.write_text(f"# Characters\n\n{characters_content}", encoding='utf-8')
            self.modified_at = datetime.now()
            return True
        except Exception as e:
            print(f"Error creating characters file: {e}")
            return False
    
    def load_auxiliary_files(self) -> Dict[str, str]:
        """Load content from auxiliary files (outline, synopsis, characters)."""
        content = {}
        
        # Load outline
        outline_path = self.project_path / "outline.md"
        if outline_path.exists():
            try:
                content["outline"] = outline_path.read_text(encoding='utf-8')
                # Extract content after header
                lines = content["outline"].split('\n', 2)
                if len(lines) > 2 and lines[0].startswith('# '):
                    self.document.outline = lines[2]
                else:
                    self.document.outline = content["outline"]
            except Exception:
                content["outline"] = ""
        
        # Load synopsis
        synopsis_path = self.project_path / "synopsis.md"
        if synopsis_path.exists():
            try:
                content["synopsis"] = synopsis_path.read_text(encoding='utf-8')
                # Extract content after header
                lines = content["synopsis"].split('\n', 2)
                if len(lines) > 2 and lines[0].startswith('# '):
                    self.document.synopsis = lines[2]
                else:
                    self.document.synopsis = content["synopsis"]
            except Exception:
                content["synopsis"] = ""
        
        # Load characters
        characters_path = self.project_path / "characters.md"
        if characters_path.exists():
            try:
                content["characters"] = characters_path.read_text(encoding='utf-8')
            except Exception:
                content["characters"] = ""
        
        return content
    
    def export_to_format(self, format_type: str, output_path: Optional[Path] = None) -> bool:
        """Export project to various formats."""
        if not output_path:
            output_path = self.project_path / f"{self.title.lower().replace(' ', '_')}.{format_type}"
        
        try:
            if format_type.lower() == "txt":
                content = self.document.export_text()
                output_path.write_text(content, encoding='utf-8')
            elif format_type.lower() == "md":
                # Export as combined markdown
                content = f"# {self.document.title}\n\n"
                content += f"**Author:** {self.document.author}\n\n"
                
                if self.document.synopsis:
                    content += f"## Synopsis\n\n{self.document.synopsis}\n\n"
                
                for chapter in self.document.get_chapters_sorted():
                    content += f"## {chapter.title}\n\n"
                    chapter_content = chapter.read_content(self.project_path)
                    content += f"{chapter_content}\n\n"
                
                output_path.write_text(content, encoding='utf-8')
            else:
                return False
            
            return True
        except Exception as e:
            print(f"Error exporting to {format_type}: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for serialization."""
        return {
            "title": self.title,
            "author": self.author,
            "project_path": str(self.project_path),
            "metadata": self.metadata,
            "document": self.document.to_dict(),
            "characters": self.characters.to_dict(),
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Create project from dictionary."""
        project_path = Path(data.get("project_path", "."))
        
        project = cls(
            title=data.get("title", ""),
            author=data.get("author", ""),
            project_path=project_path,
            metadata=data.get("metadata", {}),
        )
        
        # Load document with project path
        if "document" in data:
            project.document = Document.from_dict(data["document"], project_path)
            project.document.set_project_path(project_path)
        
        # Load characters
        if "characters" in data:
            project.characters = CharacterManager.from_dict(data["characters"])
        
        # Set timestamps
        if "created_at" in data:
            project.created_at = datetime.fromisoformat(data["created_at"])
        if "modified_at" in data:
            project.modified_at = datetime.fromisoformat(data["modified_at"])
        
        # Load auxiliary files
        project.load_auxiliary_files()
        
        return project
    
    def validate_project(self) -> List[str]:
        """Validate project integrity and return list of issues."""
        issues = []
        
        # Check project structure
        if not self.project_path.exists():
            issues.append(f"Project directory does not exist: {self.project_path}")
        
        # Check chapter files
        for chapter_num, chapter in self.document.chapters.items():
            if chapter.file_path:
                file_path = chapter.get_file_path(self.project_path)
                if not file_path or not file_path.exists():
                    issues.append(f"Chapter {chapter_num} file missing: {chapter.file_path}")
                elif chapter.is_file_modified(self.project_path):
                    issues.append(f"Chapter {chapter_num} file modified since last sync: {chapter.file_path}")
        
        # Check for orphaned files
        chapters_dir = self.project_path / "chapters"
        if chapters_dir.exists():
            existing_files = set(chapters_dir.glob("*.md"))
            tracked_files = set()
            
            for chapter in self.document.chapters.values():
                if chapter.file_path:
                    file_path = chapter.get_file_path(self.project_path)
                    if file_path:
                        tracked_files.add(file_path)
            
            orphaned = existing_files - tracked_files
            for orphan in orphaned:
                issues.append(f"Orphaned chapter file (not tracked in project): {orphan.relative_to(self.project_path)}")
        
        return issues