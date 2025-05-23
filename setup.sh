#!/bin/bash

# NovelCraft AI Setup Script
# This script sets up the complete project structure

set -e  # Exit on any error

echo "🚀 Setting up NovelCraft AI project structure..."

# Create main package directories
echo "📁 Creating package structure..."
mkdir -p novelcraft/{core,ai,editor,io,cli}
mkdir -p tests/{core,ai,editor,io,cli}
mkdir -p docs
mkdir -p examples
mkdir -p .github/workflows

# Create __init__.py files
echo "📝 Creating __init__.py files..."
touch novelcraft/__init__.py
touch novelcraft/core/__init__.py
touch novelcraft/ai/__init__.py
touch novelcraft/editor/__init__.py
touch novelcraft/io/__init__.py
touch novelcraft/cli/__init__.py
touch tests/__init__.py
touch tests/core/__init__.py
touch tests/ai/__init__.py
touch tests/editor/__init__.py
touch tests/io/__init__.py
touch tests/cli/__init__.py

# Create additional core files
echo "⚙️ Creating core module files..."

# Core module __init__.py
cat > novelcraft/core/__init__.py << 'EOF'
"""Core domain models for NovelCraft AI."""

from .document import Document, Chapter, Scene
from .character import Character, CharacterManager, CharacterRole
from .project import Project
from .snowflake import SnowflakeMethod, CharacterSheet

__all__ = [
    "Document",
    "Chapter", 
    "Scene",
    "Character",
    "CharacterManager",
    "CharacterRole",
    "Project",
    "SnowflakeMethod",
    "CharacterSheet",
]
EOF

# AI module __init__.py
cat > novelcraft/ai/__init__.py << 'EOF'
"""AI integration modules for NovelCraft AI."""

from .claude_client import ClaudeClient
from .content_generator import ContentGenerator
from .style_analyzer import StyleAnalyzer

__all__ = [
    "ClaudeClient",
    "ContentGenerator", 
    "StyleAnalyzer",
]
EOF

# Editor module __init__.py
cat > novelcraft/editor/__init__.py << 'EOF'
"""Editing and quality control modules."""

from .consistency_checker import ConsistencyChecker
from .continuity_tracker import ContinuityTracker

__all__ = [
    "ConsistencyChecker",
    "ContinuityTracker",
]
EOF

# IO module __init__.py
cat > novelcraft/io/__init__.py << 'EOF'
"""File I/O and data handling modules."""

from .file_handler import FileHandler
from .project_loader import ProjectLoader

__all__ = [
    "FileHandler",
    "ProjectLoader",
]
EOF

# CLI module __init__.py
cat > novelcraft/cli/__init__.py << 'EOF'
"""Command-line interface modules."""

from .main import main, cli

__all__ = [
    "main",
    "cli",
]
EOF

# Create Project class
echo "📋 Creating project management..."
cat > novelcraft/core/project.py << 'EOF'
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
EOF

# Create basic file handler
echo "📁 Creating file handlers..."
cat > novelcraft/io/file_handler.py << 'EOF'
"""File handling utilities."""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, Union
from docx import Document as DocxDocument
import markdown


class FileHandler:
    """Handles reading and writing various file formats."""
    
    def read_file(self, file_path: Union[str, Path]) -> str:
        """Read text content from various file formats."""
        path = Path(file_path)
        
        if path.suffix.lower() == '.docx':
            return self._read_docx(path)
        elif path.suffix.lower() == '.md':
            return self._read_markdown(path)
        else:
            # Default to plain text
            return path.read_text(encoding='utf-8')
    
    def write_file(self, file_path: Union[str, Path], content: str) -> None:
        """Write content to file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    
    def read_json(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Read JSON file."""
        path = Path(file_path)
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    
    def write_json(self, file_path: Union[str, Path], data: Dict[str, Any]) -> None:
        """Write JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def read_yaml(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Read YAML file."""
        path = Path(file_path)
        with path.open('r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def write_yaml(self, file_path: Union[str, Path], data: Dict[str, Any]) -> None:
        """Write YAML file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False)
    
    def _read_docx(self, path: Path) -> str:
        """Read DOCX file."""
        doc = DocxDocument(path)
        return '\n'.join(paragraph.text for paragraph in doc.paragraphs)
    
    def _read_markdown(self, path: Path) -> str:
        """Read Markdown file."""
        return path.read_text(encoding='utf-8')
EOF

# Create project loader
cat > novelcraft/io/project_loader.py << 'EOF'
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
EOF

# Create basic editor components
echo "✏️ Creating editor components..."
cat > novelcraft/editor/consistency_checker.py << 'EOF'
"""Consistency checking for manuscripts."""

from typing import List, Dict, Any
import re


class ConsistencyChecker:
    """Checks manuscript for consistency issues."""
    
    def __init__(self, ai_client=None):
        self.ai_client = ai_client
    
    async def check_consistency(
        self,
        manuscript: str,
        character_info: str,
        story_context: str,
    ) -> List[str]:
        """Check for consistency issues."""
        issues = []
        
        # Basic checks
        issues.extend(self._check_character_names(manuscript, character_info))
        issues.extend(self._check_timeline(manuscript))
        
        # AI-powered checks if available
        if self.ai_client:
            ai_issues = await self.ai_client.check_consistency(
                manuscript, character_info, story_context
            )
            issues.extend(ai_issues)
        
        return issues
    
    def _check_character_names(self, manuscript: str, character_info: str) -> List[str]:
        """Check for character name consistency."""
        issues = []
        
        # Extract character names from character info
        character_names = re.findall(r'^#+\s*(.+?)$', character_info, re.MULTILINE)
        
        for name in character_names:
            name = name.strip()
            if name and len(name.split()) <= 3:  # Reasonable name length
                # Check for variations in the manuscript
                variations = [name, name.lower(), name.upper(), name.title()]
                found_variations = []
                
                for var in variations:
                    if var in manuscript and var != name:
                        found_variations.append(var)
                
                if found_variations:
                    issues.append(f"Character name variations found for '{name}': {found_variations}")
        
        return issues
    
    def _check_timeline(self, manuscript: str) -> List[str]:
        """Check for timeline inconsistencies.""" 
        issues = []
        
        # Look for time references
        time_patterns = [
            r'\b(yesterday|today|tomorrow)\b',
            r'\b(morning|afternoon|evening|night)\b',
            r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b',
        ]
        
        time_refs = []
        for pattern in time_patterns:
            matches = re.findall(pattern, manuscript, re.IGNORECASE)
            time_refs.extend(matches)
        
        # Basic timeline consistency check (simplified)
        if 'yesterday' in manuscript.lower() and 'tomorrow' in manuscript.lower():
            # More sophisticated logic would be needed for real timeline checking
            pass
        
        return issues
EOF

cat > novelcraft/editor/continuity_tracker.py << 'EOF'
"""Continuity tracking for story elements."""

from typing import Dict, List, Set
from dataclasses import dataclass


@dataclass
class ContinuityElement:
    """Represents an element that needs continuity tracking."""
    name: str
    first_mention_chapter: int
    description: str
    category: str  # character, location, object, concept


class ContinuityTracker:
    """Tracks story elements for continuity."""
    
    def __init__(self):
        self.elements: Dict[str, ContinuityElement] = {}
    
    def add_element(self, element: ContinuityElement) -> None:
        """Add an element to track."""
        self.elements[element.name.lower()] = element
    
    def check_continuity(self, manuscript: str, chapter_number: int) -> List[str]:
        """Check for continuity issues in a chapter."""
        issues = []
        
        # Check if previously established elements are mentioned consistently
        for element_name, element in self.elements.items():
            if element_name in manuscript.lower():
                # Check if the description matches
                # This is a simplified check - real implementation would be more sophisticated
                pass
        
        return issues
EOF

# Create remaining AI components
echo "🤖 Creating AI components..."
cat > novelcraft/ai/content_generator.py << 'EOF'
"""Content generation using AI."""

from typing import Dict, List, Optional
import asyncio


class ContentGenerator:
    """Generates novel content using AI."""
    
    def __init__(self, ai_client):
        self.ai_client = ai_client
    
    async def generate_chapter(
        self,
        chapter_number: int,
        title: str,
        outline: str,
        synopsis: str,
        character_info: str,
        existing_chapters: Optional[Dict[int, str]] = None,
        word_count_target: int = 2000,
    ) -> str:
        """Generate a chapter."""
        return await self.ai_client.generate_chapter(
            chapter_number=chapter_number,
            chapter_title=title,
            outline=outline,
            synopsis=synopsis,
            character_info=character_info,
            existing_chapters=existing_chapters or {},
            word_count_target=word_count_target,
        )
    
    async def find_missing_chapters(
        self,
        outline: str,
        existing_chapters: List[int],
    ) -> List[int]:
        """Find missing chapters based on outline."""
        # Simple implementation - extract chapter numbers from outline
        import re
        
        chapter_matches = re.findall(r'chapter\s+(\d+)', outline.lower())
        expected_chapters = [int(match) for match in chapter_matches]
        
        missing = []
        for ch_num in expected_chapters:
            if ch_num not in existing_chapters:
                missing.append(ch_num)
        
        return sorted(missing)
EOF

cat > novelcraft/ai/style_analyzer.py << 'EOF'
"""Style analysis for maintaining author voice."""

from typing import Dict, Any, List
import re


class StyleAnalyzer:
    """Analyzes and maintains writing style."""
    
    def __init__(self, ai_client=None):
        self.ai_client = ai_client
    
    async def analyze_style(self, text_sample: str) -> Dict[str, Any]:
        """Analyze writing style."""
        if self.ai_client:
            return await self.ai_client.analyze_style(text_sample)
        else:
            return self._basic_style_analysis(text_sample)
    
    def _basic_style_analysis(self, text: str) -> Dict[str, Any]:
        """Basic style analysis without AI."""
        sentences = text.split('.')
        words = text.split()
        
        analysis = {
            "avg_sentence_length": len(words) / len(sentences) if sentences else 0,
            "total_words": len(words),
            "total_sentences": len(sentences),
            "dialogue_ratio": self._calculate_dialogue_ratio(text),
            "complexity_score": self._calculate_complexity(text),
        }
        
        return analysis
    
    def _calculate_dialogue_ratio(self, text: str) -> float:
        """Calculate ratio of dialogue to narrative."""
        dialogue_matches = re.findall(r'"[^"]*"', text)
        dialogue_words = sum(len(match.split()) for match in dialogue_matches)
        total_words = len(text.split())
        
        return dialogue_words / total_words if total_words > 0 else 0.0
    
    def _calculate_complexity(self, text: str) -> float:
        """Calculate text complexity score."""
        words = text.split()
        if not words:
            return 0.0
        
        # Simple complexity based on average word length
        avg_word_length = sum(len(word.strip('.,!?";')) for word in words) / len(words)
        return min(avg_word_length / 10.0, 1.0)  # Normalize to 0-1
EOF

# Create example files
echo "📚 Creating examples..."
mkdir -p examples
cat > examples/basic_usage.py << 'EOF'
"""Basic usage example for NovelCraft AI."""

import asyncio
from novelcraft import Project, ClaudeClient, ContentGenerator


async def main():
    """Example of basic novel generation."""
    
    # Create a project
    project = Project(
        title="The Time Traveler's Dilemma",
        author="Jane Doe"
    )
    
    # Set up AI client (requires ANTHROPIC_API_KEY environment variable)
    client = ClaudeClient()
    generator = ContentGenerator(client)
    
    # Generate a chapter
    chapter_content = await generator.generate_chapter(
        chapter_number=1,
        title="The Discovery",
        outline="Sarah finds the time machine in her grandmother's attic",
        synopsis="A young scientist discovers time travel and must prevent a dystopian future",
        character_info="Sarah: 28-year-old physicist, curious and determined",
        word_count_target=1500
    )
    
    print("Generated Chapter 1:")
    print(chapter_content)


if __name__ == "__main__":
    asyncio.run(main())
EOF

# Create test files
echo "🧪 Creating test files..."
cat > tests/test_basic.py << 'EOF'
"""Basic tests for NovelCraft AI."""

import pytest
from novelcraft.core import Document, Chapter, Character


def test_document_creation():
    """Test document creation."""
    doc = Document(title="Test Novel", author="Test Author")
    assert doc.title == "Test Novel"
    assert doc.author == "Test Author"
    assert doc.word_count == 0


def test_chapter_creation():
    """Test chapter creation."""
    chapter = Chapter(
        number=1,
        title="Test Chapter",
        content="This is a test chapter."
    )
    assert chapter.number == 1
    assert chapter.title == "Test Chapter"
    assert chapter.word_count == 5


def test_character_creation():
    """Test character creation."""
    character = Character(name="Test Character")
    assert character.name == "Test Character"
    assert len(character.traits) == 0
EOF

# Create additional configuration files
echo "⚙️ Creating configuration files..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.coverage
htmlcov/
.pytest_cache/
.tox/

# Documentation
docs/_build/

# OS
.DS_Store
Thumbs.db

# Project specific
*.log
config.yaml
.env

# Generated content
generated/
manuscripts/draft_*

# API keys
.anthropic_key
EOF

cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2024 NovelCraft AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

echo "✅ Project structure created successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Copy all the Python files from the artifacts into their respective directories"
echo "2. Install dependencies: pip install -e ."
echo "3. Set your API key: export ANTHROPIC_API_KEY='your-key'"
echo "4. Run tests: pytest"
echo "5. Try the CLI: novelcraft --help"
echo ""
echo "🎉 Happy writing!"