"""
Document management and processing for novel manuscripts.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import re


@dataclass
class Chapter:
    """Represents a chapter in the novel."""
    number: int
    title: str
    content: str
    word_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        self.word_count = len(self.content.split())
    
    def update_content(self, new_content: str) -> None:
        """Update chapter content and metadata."""
        self.content = new_content
        self.word_count = len(new_content.split())
        self.modified_at = datetime.now()


@dataclass
class Scene:
    """Represents a scene within a chapter."""
    chapter_number: int
    scene_number: int
    title: str
    content: str
    characters: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    word_count: int = 0
    
    def __post_init__(self):
        self.word_count = len(self.content.split())


class Document:
    """Main document class for managing novel manuscripts."""
    
    def __init__(self, title: str = "", author: str = ""):
        self.title = title
        self.author = author
        self.chapters: Dict[int, Chapter] = {}
        self.scenes: Dict[tuple, Scene] = {}  # (chapter_num, scene_num) -> Scene
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
    
    @property
    def word_count(self) -> int:
        """Get total word count of the document."""
        return sum(chapter.word_count for chapter in self.chapters.values())
    
    @property
    def chapter_count(self) -> int:
        """Get total number of chapters."""
        return len(self.chapters)
    
    def add_chapter(self, chapter: Chapter) -> None:
        """Add a new chapter to the document."""
        self.chapters[chapter.number] = chapter
        self.modified_at = datetime.now()
    
    def get_chapter(self, chapter_number: int) -> Optional[Chapter]:
        """Get a specific chapter by number."""
        return self.chapters.get(chapter_number)
    
    def remove_chapter(self, chapter_number: int) -> bool:
        """Remove a chapter from the document."""
        if chapter_number in self.chapters:
            del self.chapters[chapter_number]
            self.modified_at = datetime.now()
            return True
        return False
    
    def add_scene(self, scene: Scene) -> None:
        """Add a scene to the document."""
        key = (scene.chapter_number, scene.scene_number)
        self.scenes[key] = scene
        self.modified_at = datetime.now()
    
    def get_scenes_for_chapter(self, chapter_number: int) -> List[Scene]:
        """Get all scenes for a specific chapter."""
        return [
            scene for (ch_num, _), scene in self.scenes.items() 
            if ch_num == chapter_number
        ]
    
    def get_all_text(self) -> str:
        """Get the complete text of the document."""
        text_parts = []
        for chapter_num in sorted(self.chapters.keys()):
            chapter = self.chapters[chapter_num]
            text_parts.append(f"# Chapter {chapter_num}: {chapter.title}")
            text_parts.append(chapter.content)
            text_parts.append("")  # Empty line between chapters
        return "\n".join(text_parts)
    
    def find_missing_chapters(self, expected_chapters: List[int]) -> List[int]:
        """Find which chapters are missing from the expected list."""
        existing_chapters = set(self.chapters.keys())
        expected_set = set(expected_chapters)
        return sorted(expected_set - existing_chapters)
    
    def extract_character_names(self) -> List[str]:
        """Extract character names from the document content."""
        all_text = self.get_all_text()
        # Simple regex to find capitalized words (potential character names)
        potential_names = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', all_text)
        
        # Filter out common words and return unique names
        common_words = {
            'Chapter', 'The', 'And', 'But', 'When', 'Where', 'What', 'Who',
            'Why', 'How', 'Then', 'Now', 'Here', 'There', 'This', 'That'
        }
        
        unique_names = []
        for name in potential_names:
            if name not in common_words and name not in unique_names:
                unique_names.append(name)
        
        return unique_names
    
    def get_chapter_summary(self, chapter_number: int) -> str:
        """Get a brief summary of a chapter."""
        chapter = self.get_chapter(chapter_number)
        if not chapter:
            return f"Chapter {chapter_number} not found"
        
        # Return first 200 characters as summary
        content = chapter.content.strip()
        if len(content) <= 200:
            return content
        return content[:200] + "..."
    
    def merge_chapters(self, start_chapter: int, end_chapter: int, new_title: str) -> bool:
        """Merge multiple chapters into one."""
        chapters_to_merge = []
        for i in range(start_chapter, end_chapter + 1):
            if i in self.chapters:
                chapters_to_merge.append(self.chapters[i])
        
        if not chapters_to_merge:
            return False
        
        # Combine content
        combined_content = "\n\n".join(ch.content for ch in chapters_to_merge)
        
        # Create new merged chapter
        merged_chapter = Chapter(
            number=start_chapter,
            title=new_title,
            content=combined_content
        )
        
        # Remove old chapters and add merged one
        for i in range(start_chapter, end_chapter + 1):
            if i in self.chapters:
                del self.chapters[i]
        
        self.add_chapter(merged_chapter)
        return True
    
    def split_chapter(self, chapter_number: int, split_points: List[int]) -> bool:
        """Split a chapter into multiple chapters at specified positions."""
        chapter = self.get_chapter(chapter_number)
        if not chapter:
            return False
        
        content = chapter.content
        splits = [0] + split_points + [len(content)]
        
        # Remove original chapter
        del self.chapters[chapter_number]
        
        # Create new chapters from splits
        for i in range(len(splits) - 1):
            start, end = splits[i], splits[i + 1]
            new_content = content[start:end].strip()
            
            new_chapter = Chapter(
                number=chapter_number + i,
                title=f"{chapter.title} - Part {i + 1}",
                content=new_content
            )
            self.add_chapter(new_chapter)
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary for serialization."""
        return {
            "title": self.title,
            "author": self.author,
            "chapters": {
                num: {
                    "number": ch.number,
                    "title": ch.title,
                    "content": ch.content,
                    "word_count": ch.word_count,
                    "created_at": ch.created_at.isoformat(),
                    "modified_at": ch.modified_at.isoformat(),
                }
                for num, ch in self.chapters.items()
            },
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Create document from dictionary."""
        doc = cls(title=data.get("title", ""), author=data.get("author", ""))
        doc.metadata = data.get("metadata", {})
        
        if "created_at" in data:
            doc.created_at = datetime.fromisoformat(data["created_at"])
        if "modified_at" in data:
            doc.modified_at = datetime.fromisoformat(data["modified_at"])
        
        # Load chapters
        for ch_data in data.get("chapters", {}).values():
            chapter = Chapter(
                number=ch_data["number"],
                title=ch_data["title"],
                content=ch_data["content"],
                word_count=ch_data.get("word_count", 0),
                created_at=datetime.fromisoformat(ch_data.get("created_at", datetime.now().isoformat())),
                modified_at=datetime.fromisoformat(ch_data.get("modified_at", datetime.now().isoformat())),
            )
            doc.add_chapter(chapter)
        
        return doc