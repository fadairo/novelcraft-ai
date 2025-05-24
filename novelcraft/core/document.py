"""Document and chapter management for NovelCraft AI with file-based architecture."""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re


def normalize_chapter_title(title: str) -> str:
    """Convert various chapter title formats to standardized 'Chapter N' format."""
    
    # Dictionary for word-to-number conversion
    word_to_num = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'eleven': '11', 'twelve': '12', 'thirteen': '13', 'fourteen': '14',
        'fifteen': '15', 'sixteen': '16', 'seventeen': '17', 'eighteen': '18',
        'nineteen': '19', 'twenty': '20', 'twenty-one': '21', 'twenty-two': '22',
        'twenty-three': '23', 'twenty-four': '24', 'twenty-five': '25'
    }
    
    # Patterns to match various chapter formats
    patterns = [
        r'chapter\s+(\w+(?:-\w+)?)',
        r'ch\.?\s+(\w+(?:-\w+)?)',
        r'^(\w+(?:-\w+)?)$',
    ]
    
    title_lower = title.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, title_lower)
        if match:
            chapter_part = match.group(1)
            
            # Convert word to number if needed
            if chapter_part in word_to_num:
                return f"Chapter {word_to_num[chapter_part]}"
            
            # If already a number, use it
            if chapter_part.isdigit():
                return f"Chapter {chapter_part}"
    
    # If no pattern matches, return original title
    return title.strip()


@dataclass
class Scene:
    """Represents a scene within a chapter."""
    
    number: int
    title: str = ""
    content: str = ""
    setting: str = ""
    characters: List[str] = field(default_factory=list)
    notes: str = ""
    word_count: int = field(init=False)
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Calculate word count after initialization."""
        self.word_count = len(self.content.split()) if self.content else 0
    
    def update_content(self, content: str) -> None:
        """Update scene content and recalculate word count."""
        self.content = content
        self.word_count = len(content.split()) if content else 0
    
    def add_character(self, character_name: str) -> None:
        """Add a character to this scene."""
        if character_name not in self.characters:
            self.characters.append(character_name)
    
    def remove_character(self, character_name: str) -> None:
        """Remove a character from this scene."""
        if character_name in self.characters:
            self.characters.remove(character_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert scene to dictionary for serialization."""
        return {
            "number": self.number,
            "title": self.title,
            "content": self.content,
            "setting": self.setting,
            "characters": self.characters,
            "notes": self.notes,
            "word_count": self.word_count,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        """Create scene from dictionary."""
        scene = cls(
            number=data["number"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            setting=data.get("setting", ""),
            characters=data.get("characters", []),
            notes=data.get("notes", ""),
        )
        
        if "created_at" in data:
            scene.created_at = datetime.fromisoformat(data["created_at"])
        
        return scene


@dataclass
class ChapterReference:
    """Represents a reference to a chapter file rather than storing content directly."""
    
    number: int
    title: str = ""
    file_path: Optional[str] = None
    summary: str = ""
    notes: str = ""
    scenes: Dict[int, Scene] = field(default_factory=dict)
    word_count: int = 0
    status: str = "draft"  # draft, complete, needs_revision, etc.
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    file_modified_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Normalize title after initialization."""
        if self.title:
            self.title = normalize_chapter_title(self.title)
    
    def get_file_path(self, project_path: Optional[Path] = None) -> Optional[Path]:
        """Get the full path to the chapter file."""
        if not self.file_path:
            return None
        
        file_path = Path(self.file_path)
        if file_path.is_absolute():
            return file_path
        
        # Relative path - resolve against project path
        if project_path:
            return project_path / file_path
        else:
            return Path.cwd() / file_path
    
    def generate_file_path(self, project_path: Optional[Path] = None) -> Path:
        """Generate a standard file path for this chapter."""
        if not project_path:
            project_path = Path.cwd()
        
        # Create chapters directory if it doesn't exist
        chapters_dir = project_path / "chapters"
        chapters_dir.mkdir(exist_ok=True)
        
        # Generate filename: 00_chapter_0.md, 01_chapter_1.md, etc.
        filename = f"{self.number:02d}_chapter_{self.number}.md"
        return chapters_dir / filename
    
    def read_content(self, project_path: Optional[Path] = None) -> str:
        """Read chapter content from file."""
        file_path = self.get_file_path(project_path)
        
        if not file_path or not file_path.exists():
            return ""
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Update file modification time
            stat = file_path.stat()
            self.file_modified_at = datetime.fromtimestamp(stat.st_mtime)
            
            # Extract content (skip markdown header if present)
            if content.startswith(f'# {self.title}'):
                lines = content.split('\n', 2)
                return lines[2] if len(lines) > 2 else ""
            
            return content
        except Exception as e:
            print(f"Error reading chapter file {file_path}: {e}")
            return ""
    
    def write_content(self, content: str, project_path: Optional[Path] = None) -> bool:
        """Write chapter content to file."""
        if not self.file_path:
            # Generate file path if not set
            file_path = self.generate_file_path(project_path)
            self.file_path = str(file_path.relative_to(project_path or Path.cwd()))
        else:
            file_path = self.get_file_path(project_path)
        
        if not file_path:
            return False
        
        try:
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create markdown content with header
            markdown_content = f"# {self.title}\n\n{content.strip()}\n"
            
            # Write to file
            file_path.write_text(markdown_content, encoding='utf-8')
            
            # Update modification times
            self.modified_at = datetime.now()
            stat = file_path.stat()
            self.file_modified_at = datetime.fromtimestamp(stat.st_mtime)
            
            # Update word count
            self.word_count = len(content.split()) if content else 0
            
            return True
        except Exception as e:
            print(f"Error writing chapter file {file_path}: {e}")
            return False
    
    def is_file_modified(self, project_path: Optional[Path] = None) -> bool:
        """Check if the file has been modified since last read."""
        file_path = self.get_file_path(project_path)
        
        if not file_path or not file_path.exists():
            return False
        
        if not self.file_modified_at:
            return True
        
        try:
            stat = file_path.stat()
            file_mod_time = datetime.fromtimestamp(stat.st_mtime)
            return file_mod_time > self.file_modified_at
        except Exception:
            return False
    
    def sync_with_file(self, project_path: Optional[Path] = None) -> None:
        """Sync metadata with file (update word count, modification time)."""
        if self.is_file_modified(project_path):
            content = self.read_content(project_path)
            self.word_count = len(content.split()) if content else 0
    
    def add_scene(self, scene: Scene) -> None:
        """Add a scene to this chapter."""
        self.scenes[scene.number] = scene
        self.modified_at = datetime.now()
    
    def remove_scene(self, scene_number: int) -> None:
        """Remove a scene from this chapter."""
        if scene_number in self.scenes:
            del self.scenes[scene_number]
            self.modified_at = datetime.now()
    
    def get_scene(self, scene_number: int) -> Optional[Scene]:
        """Get a scene by number."""
        return self.scenes.get(scene_number)
    
    def get_total_word_count(self, project_path: Optional[Path] = None) -> int:
        """Get total word count including scenes."""
        # Sync with file first to get accurate count
        self.sync_with_file(project_path)
        
        total = self.word_count
        for scene in self.scenes.values():
            total += scene.word_count
        return total
    
    def get_characters_in_chapter(self, project_path: Optional[Path] = None) -> List[str]:
        """Get all characters mentioned in this chapter."""
        characters = set()
        
        # Extract characters from scene metadata
        for scene in self.scenes.values():
            characters.update(scene.characters)
        
        # Could also analyze chapter content for character names
        # This would require integration with character database
        
        return list(characters)
    
    def generate_summary(self, project_path: Optional[Path] = None) -> str:
        """Generate a basic summary of the chapter."""
        if self.summary:
            return self.summary
        
        # Read content for auto-summary
        content = self.read_content(project_path)
        if content:
            sentences = re.split(r'[.!?]+', content)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if len(sentences) >= 2:
                return f"{sentences[0]}... {sentences[-1]}"
            elif sentences:
                return sentences[0]
        
        return "No summary available."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chapter reference to dictionary for serialization."""
        return {
            "number": self.number,
            "title": self.title,
            "file_path": self.file_path,
            "summary": self.summary,
            "notes": self.notes,
            "scenes": {num: scene.to_dict() for num, scene in self.scenes.items()},
            "word_count": self.word_count,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "file_modified_at": self.file_modified_at.isoformat() if self.file_modified_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterReference":
        """Create chapter reference from dictionary."""
        chapter = cls(
            number=data["number"],
            title=data.get("title", ""),
            file_path=data.get("file_path"),
            summary=data.get("summary", ""),
            notes=data.get("notes", ""),
            word_count=data.get("word_count", 0),
            status=data.get("status", "draft"),
        )
        
        # Load scenes
        if "scenes" in data:
            for scene_num, scene_data in data["scenes"].items():
                scene = Scene.from_dict(scene_data)
                chapter.scenes[int(scene_num)] = scene
        
        if "created_at" in data:
            chapter.created_at = datetime.fromisoformat(data["created_at"])
        if "modified_at" in data:
            chapter.modified_at = datetime.fromisoformat(data["modified_at"])
        if data.get("file_modified_at"):
            chapter.file_modified_at = datetime.fromisoformat(data["file_modified_at"])
        
        return chapter


# For backward compatibility, create an alias
Chapter = ChapterReference


@dataclass
class Document:
    """Represents the main novel document with file-based chapter management."""
    
    title: str = ""
    author: str = ""
    synopsis: str = ""
    genre: str = ""
    target_word_count: int = 80000
    chapters: Dict[int, ChapterReference] = field(default_factory=dict)
    outline: str = ""
    themes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    word_count: int = field(init=False, default=0)
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    project_path: Optional[Path] = None
    
    def __post_init__(self):
        """Calculate total word count after initialization."""
        self.word_count = self.calculate_word_count()
    
    def set_project_path(self, project_path: Union[str, Path]) -> None:
        """Set the project path for resolving file references."""
        self.project_path = Path(project_path)
    
    def calculate_word_count(self) -> int:
        """Calculate total word count of the document."""
        total = 0
        for chapter in self.chapters.values():
            total += chapter.get_total_word_count(self.project_path)
        return total
    
    def add_chapter(self, chapter: ChapterReference) -> None:
        """Add a chapter to the document."""
        # Normalize the chapter title before adding
        if chapter.title:
            chapter.title = normalize_chapter_title(chapter.title)
        
        self.chapters[chapter.number] = chapter
        self.word_count = self.calculate_word_count()
        self.modified_at = datetime.now()
    
    def create_chapter_from_content(self, number: int, title: str, content: str) -> ChapterReference:
        """Create a new chapter with content and add it to the document."""
        chapter = ChapterReference(number=number, title=title)
        
        # Write content to file
        if chapter.write_content(content, self.project_path):
            self.add_chapter(chapter)
            return chapter
        else:
            raise Exception(f"Failed to write chapter {number} to file")
    
    def remove_chapter(self, chapter_number: int) -> None:
        """Remove a chapter from the document."""
        if chapter_number in self.chapters:
            del self.chapters[chapter_number]
            self.word_count = self.calculate_word_count()
            self.modified_at = datetime.now()
    
    def get_chapter(self, chapter_number: int) -> Optional[ChapterReference]:
        """Get a chapter by number."""
        return self.chapters.get(chapter_number)
    
    def get_chapter_content(self, chapter_number: int) -> str:
        """Get the content of a specific chapter."""
        chapter = self.get_chapter(chapter_number)
        if chapter:
            return chapter.read_content(self.project_path)
        return ""
    
    def update_chapter_content(self, chapter_number: int, content: str) -> bool:
        """Update the content of a specific chapter."""
        chapter = self.get_chapter(chapter_number)
        if chapter:
            success = chapter.write_content(content, self.project_path)
            if success:
                self.word_count = self.calculate_word_count()
                self.modified_at = datetime.now()
            return success
        return False
    
    def get_chapters_sorted(self) -> List[ChapterReference]:
        """Get all chapters sorted by number."""
        return [self.chapters[num] for num in sorted(self.chapters.keys())]
    
    def get_chapter_count(self) -> int:
        """Get the number of chapters."""
        return len(self.chapters)
    
    def get_progress_percentage(self) -> float:
        """Get progress as percentage of target word count."""
        if self.target_word_count <= 0:
            return 0.0
        current_count = self.calculate_word_count()
        return min(100.0, (current_count / self.target_word_count) * 100)
    
    def find_missing_chapters(self) -> List[int]:
        """Find gaps in chapter numbering."""
        if not self.chapters:
            return []
        
        existing_numbers = sorted(self.chapters.keys())
        min_chapter = existing_numbers[0]
        max_chapter = existing_numbers[-1]
        
        missing = []
        for i in range(min_chapter, max_chapter + 1):
            if i not in self.chapters:
                missing.append(i)
        
        return missing
    
    def sync_all_chapters(self) -> None:
        """Sync all chapters with their files."""
        for chapter in self.chapters.values():
            chapter.sync_with_file(self.project_path)
        self.word_count = self.calculate_word_count()
    
    def discover_chapter_files(self, chapters_dir: Optional[Path] = None) -> List[ChapterReference]:
        """Discover chapter files in the chapters directory and create references."""
        if not chapters_dir:
            if self.project_path:
                chapters_dir = self.project_path / "chapters"
            else:
                chapters_dir = Path.cwd() / "chapters"
        
        if not chapters_dir.exists():
            return []
        
        discovered = []
        
        # Look for chapter files matching patterns
        patterns = ["chapter_*.md", "*.md"]
        
        for pattern in patterns:
            for file_path in chapters_dir.glob(pattern):
                # Try to extract chapter number from filename
                chapter_num = self._extract_chapter_number(file_path.name)
                
                if chapter_num is not None and chapter_num not in self.chapters:
                    # Create chapter reference
                    relative_path = file_path.relative_to(self.project_path or Path.cwd())
                    
                    chapter = ChapterReference(
                        number=chapter_num,
                        title=f"Chapter {chapter_num}",
                        file_path=str(relative_path)
                    )
                    
                    # Sync with file to get title and word count
                    chapter.sync_with_file(self.project_path)
                    
                    discovered.append(chapter)
        
        return discovered
    
    def _extract_chapter_number(self, filename: str) -> Optional[int]:
        """Extract chapter number from filename."""
        # Try various patterns
        patterns = [
            r'chapter_(\d+)',  # chapter_01.md
            r'(\d+)_chapter',  # 01_chapter.md
            r'^(\d+)\.md$',    # 01.md
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename.lower())
            if match:
                return int(match.group(1))
        
        return None
    
    def get_all_characters(self) -> List[str]:
        """Get all characters mentioned across all chapters."""
        characters = set()
        for chapter in self.chapters.values():
            characters.update(chapter.get_characters_in_chapter(self.project_path))
        return list(characters)
    
    def search_content(self, query: str) -> List[Dict[str, Any]]:
        """Search for text across all chapters."""
        results = []
        query_lower = query.lower()
        
        for chapter in self.chapters.values():
            content = chapter.read_content(self.project_path)
            if query_lower in content.lower():
                # Find the context around the match
                content_lower = content.lower()
                index = content_lower.find(query_lower)
                start = max(0, index - 50)
                end = min(len(content), index + len(query) + 50)
                context = content[start:end]
                
                results.append({
                    "chapter_number": chapter.number,
                    "chapter_title": chapter.title,
                    "context": context,
                    "position": index,
                    "file_path": chapter.file_path
                })
        
        return results
    
    def generate_table_of_contents(self) -> str:
        """Generate a table of contents."""
        toc = f"Table of Contents - {self.title}\n"
        toc += "=" * (len(toc) - 1) + "\n\n"
        
        for chapter in self.get_chapters_sorted():
            word_count = chapter.get_total_word_count(self.project_path)
            toc += f"Chapter {chapter.number}: {chapter.title} ({word_count:,} words)\n"
        
        total_words = self.calculate_word_count()
        toc += f"\nTotal: {self.get_chapter_count()} chapters, {total_words:,} words"
        return toc
    
    def export_text(self) -> str:
        """Export the entire document as plain text."""
        text = f"{self.title}\n"
        text += f"by {self.author}\n\n"
        
        if self.synopsis:
            text += f"Synopsis:\n{self.synopsis}\n\n"
        
        text += "=" * 50 + "\n\n"
        
        for chapter in self.get_chapters_sorted():
            text += f"Chapter {chapter.number}: {chapter.title}\n\n"
            content = chapter.read_content(self.project_path)
            text += content + "\n\n"
            
            # Add scenes if any
            for scene in chapter.scenes.values():
                if scene.content:
                    text += f"--- Scene {scene.number}: {scene.title} ---\n"
                    text += scene.content + "\n\n"
        
        return text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary for serialization."""
        return {
            "title": self.title,
            "author": self.author,
            "synopsis": self.synopsis,
            "genre": self.genre,
            "target_word_count": self.target_word_count,
            "chapters": {num: chapter.to_dict() for num, chapter in self.chapters.items()},
            "outline": self.outline,
            "themes": self.themes,
            "tags": self.tags,
            "word_count": self.word_count,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_path: Optional[Path] = None) -> "Document":
        """Create document from dictionary."""
        document = cls(
            title=data.get("title", ""),
            author=data.get("author", ""),
            synopsis=data.get("synopsis", ""),
            genre=data.get("genre", ""),
            target_word_count=data.get("target_word_count", 80000),
            outline=data.get("outline", ""),
            themes=data.get("themes", []),
            tags=data.get("tags", []),
            project_path=project_path,
        )
        
        # Load chapters
        if "chapters" in data:
            for chapter_num, chapter_data in data["chapters"].items():
                chapter = ChapterReference.from_dict(chapter_data)
                document.chapters[int(chapter_num)] = chapter
        
        if "created_at" in data:
            document.created_at = datetime.fromisoformat(data["created_at"])
        if "modified_at" in data:
            document.modified_at = datetime.fromisoformat(data["modified_at"])
        
        # Recalculate word count
        document.word_count = document.calculate_word_count()
        
        return document