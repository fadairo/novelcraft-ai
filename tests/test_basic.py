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
