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
