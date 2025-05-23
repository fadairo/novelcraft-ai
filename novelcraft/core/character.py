"""
Character management for novel writing.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CharacterRole(Enum):
    """Enumeration of character roles in the story."""
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"
    BACKGROUND = "background"


@dataclass
class CharacterTrait:
    """Represents a character trait or attribute."""
    name: str
    description: str
    importance: int = 1  # 1-10 scale
    
    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


@dataclass
class CharacterRelationship:
    """Represents a relationship between two characters."""
    character_name: str
    relationship_type: str
    description: str
    strength: int = 5  # 1-10 scale
    
    def __str__(self) -> str:
        return f"{self.relationship_type} with {self.character_name}: {self.description}"


class Character:
    """Represents a character in the novel."""
    
    def __init__(
        self,
        name: str,
        role: CharacterRole = CharacterRole.MINOR,
        description: str = "",
        age: Optional[int] = None,
    ):
        self.name = name
        self.role = role
        self.description = description
        self.age = age
        self.traits: List[CharacterTrait] = []
        self.relationships: List[CharacterRelationship] = []
        self.backstory: str = ""
        self.goals: List[str] = []
        self.fears: List[str] = []
        self.secrets: List[str] = []
        self.appearance: Dict[str, str] = {}
        self.personality: Dict[str, str] = {}
        self.speech_patterns: List[str] = []
        self.first_appearance_chapter: Optional[int] = None
        self.last_appearance_chapter: Optional[int] = None
        self.chapter_appearances: List[int] = []
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
    
    def add_trait(self, name: str, description: str, importance: int = 1) -> None:
        """Add a character trait."""
        trait = CharacterTrait(name, description, importance)
        self.traits.append(trait)
        self.modified_at = datetime.now()
    
    def remove_trait(self, trait_name: str) -> bool:
        """Remove a character trait by name."""
        for i, trait in enumerate(self.traits):
            if trait.name.lower() == trait_name.lower():
                del self.traits[i]
                self.modified_at = datetime.now()
                return True
        return False
    
    def add_relationship(
        self, 
        character_name: str, 
        relationship_type: str, 
        description: str,
        strength: int = 5
    ) -> None:
        """Add a relationship with another character."""
        relationship = CharacterRelationship(
            character_name, relationship_type, description, strength
        )
        self.relationships.append(relationship)
        self.modified_at = datetime.now()
    
    def get_relationships_by_type(self, relationship_type: str) -> List[CharacterRelationship]:
        """Get all relationships of a specific type."""
        return [
            rel for rel in self.relationships 
            if rel.relationship_type.lower() == relationship_type.lower()
        ]
    
    def add_appearance(self, chapter: int) -> None:
        """Record character appearance in a chapter."""
        if chapter not in self.chapter_appearances:
            self.chapter_appearances.append(chapter)
            self.chapter_appearances.sort()
            
            if self.first_appearance_chapter is None or chapter < self.first_appearance_chapter:
                self.first_appearance_chapter = chapter
            
            if self.last_appearance_chapter is None or chapter > self.last_appearance_chapter:
                self.last_appearance_chapter = chapter
            
            self.modified_at = datetime.now()
    
    def appears_in_chapter(self, chapter: int) -> bool:
        """Check if character appears in a specific chapter."""
        return chapter in self.chapter_appearances
    
    def get_major_traits(self, min_importance: int = 7) -> List[CharacterTrait]:
        """Get traits with importance above threshold."""
        return [trait for trait in self.traits if trait.importance >= min_importance]
    
    def get_character_arc_summary(self) -> str:
        """Generate a summary of the character's arc."""
        arc_parts = []
        
        if self.first_appearance_chapter and self.last_appearance_chapter:
            arc_parts.append(
                f"Appears from Chapter {self.first_appearance_chapter} "
                f"to Chapter {self.last_appearance_chapter}"
            )
        
        if self.goals:
            arc_parts.append(f"Goals: {', '.join(self.goals)}")
        
        if self.fears:
            arc_parts.append(f"Fears: {', '.join(self.fears)}")
        
        major_traits = self.get_major_traits()
        if major_traits:
            trait_names = [trait.name for trait in major_traits]
            arc_parts.append(f"Key traits: {', '.join(trait_names)}")
        
        return " | ".join(arc_parts) if arc_parts else "No arc information available"
    
    def set_appearance(self, feature: str, description: str) -> None:
        """Set a physical appearance feature."""
        self.appearance[feature] = description
        self.modified_at = datetime.now()
    
    def set_personality(self, aspect: str, description: str) -> None:
        """Set a personality aspect."""
        self.personality[aspect] = description
        self.modified_at = datetime.now()
    
    def add_speech_pattern(self, pattern: str) -> None:
        """Add a speech pattern or verbal tic."""
        if pattern not in self.speech_patterns:
            self.speech_patterns.append(pattern)
            self.modified_at = datetime.now()
    
    def get_full_profile(self) -> str:
        """Get a complete character profile as text."""
        profile_lines = [
            f"Character: {self.name}",
            f"Role: {self.role.value}",
            f"Age: {self.age if self.age else 'Unknown'}",
            "",
            f"Description: {self.description}",
            "",
        ]
        
        if self.backstory:
            profile_lines.extend(["Backstory:", self.backstory, ""])
        
        if self.traits:
            profile_lines.append("Traits:")
            for trait in self.traits:
                profile_lines.append(f"  - {trait}")
            profile_lines.append("")
        
        if self.goals:
            profile_lines.append("Goals:")
            for goal in self.goals:
                profile_lines.append(f"  - {goal}")
            profile_lines.append("")
        
        if self.fears:
            profile_lines.append("Fears:")
            for fear in self.fears:
                profile_lines.append(f"  - {fear}")
            profile_lines.append("")
        
        if self.relationships:
            profile_lines.append("Relationships:")
            for rel in self.relationships:
                profile_lines.append(f"  - {rel}")
            profile_lines.append("")
        
        if self.appearance:
            profile_lines.append("Appearance:")
            for feature, desc in self.appearance.items():
                profile_lines.append(f"  - {feature}: {desc}")
            profile_lines.append("")
        
        if self.speech_patterns:
            profile_lines.append("Speech Patterns:")
            for pattern in self.speech_patterns:
                profile_lines.append(f"  - {pattern}")
            profile_lines.append("")
        
        profile_lines.append(self.get_character_arc_summary())
        
        return "\n".join(profile_lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert character to dictionary for serialization."""
        return {
            "name": self.name,
            "role": self.role.value,
            "description": self.description,
            "age": self.age,
            "traits": [
                {
                    "name": trait.name,
                    "description": trait.description,
                    "importance": trait.importance,
                }
                for trait in self.traits
            ],
            "relationships": [
                {
                    "character_name": rel.character_name,
                    "relationship_type": rel.relationship_type,
                    "description": rel.description,
                    "strength": rel.strength,
                }
                for rel in self.relationships
            ],
            "backstory": self.backstory,
            "goals": self.goals,
            "fears": self.fears,
            "secrets": self.secrets,
            "appearance": self.appearance,
            "personality": self.personality,
            "speech_patterns": self.speech_patterns,
            "first_appearance_chapter": self.first_appearance_chapter,
            "last_appearance_chapter": self.last_appearance_chapter,
            "chapter_appearances": self.chapter_appearances,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Character":
        """Create character from dictionary."""
        character = cls(
            name=data["name"],
            role=CharacterRole(data.get("role", "minor")),
            description=data.get("description", ""),
            age=data.get("age"),
        )
        
        # Load traits
        for trait_data in data.get("traits", []):
            character.add_trait(
                trait_data["name"],
                trait_data["description"],
                trait_data.get("importance", 1),
            )
        
        # Load relationships
        for rel_data in data.get("relationships", []):
            character.add_relationship(
                rel_data["character_name"],
                rel_data["relationship_type"],
                rel_data["description"],
                rel_data.get("strength", 5),
            )
        
        # Load other attributes
        character.backstory = data.get("backstory", "")
        character.goals = data.get("goals", [])
        character.fears = data.get("fears", [])
        character.secrets = data.get("secrets", [])
        character.appearance = data.get("appearance", {})
        character.personality = data.get("personality", {})
        character.speech_patterns = data.get("speech_patterns", [])
        character.first_appearance_chapter = data.get("first_appearance_chapter")
        character.last_appearance_chapter = data.get("last_appearance_chapter")
        character.chapter_appearances = data.get("chapter_appearances", [])
        
        if "created_at" in data:
            character.created_at = datetime.fromisoformat(data["created_at"])
        if "modified_at" in data:
            character.modified_at = datetime.fromisoformat(data["modified_at"])
        
        return character


class CharacterManager:
    """Manages all characters in a novel project."""
    
    def __init__(self):
        self.characters: Dict[str, Character] = {}
    
    def add_character(self, character: Character) -> None:
        """Add a character to the manager."""
        self.characters[character.name.lower()] = character
    
    def get_character(self, name: str) -> Optional[Character]:
        """Get a character by name (case insensitive)."""
        return self.characters.get(name.lower())
    
    def remove_character(self, name: str) -> bool:
        """Remove a character by name."""
        key = name.lower()
        if key in self.characters:
            del self.characters[key]
            return True
        return False
    
    def get_all_characters(self) -> List[Character]:
        """Get all characters."""
        return list(self.characters.values())
    
    def get_characters_by_role(self, role: CharacterRole) -> List[Character]:
        """Get all characters with a specific role."""
        return [char for char in self.characters.values() if char.role == role]
    
    def get_characters_in_chapter(self, chapter: int) -> List[Character]:
        """Get all characters that appear in a specific chapter."""
        return [
            char for char in self.characters.values() 
            if char.appears_in_chapter(chapter)
        ]
    
    def find_character_conflicts(self) -> List[str]:
        """Find potential character conflicts or inconsistencies."""
        conflicts = []
        
        # Check for duplicate names
        names = [char.name for char in self.characters.values()]
        duplicates = set([name for name in names if names.count(name) > 1])
        if duplicates:
            conflicts.append(f"Duplicate character names: {', '.join(duplicates)}")
        
        # Check for conflicting relationships
        for char in self.characters.values():
            for rel in char.relationships:
                other_char = self.get_character(rel.character_name)
                if other_char:
                    # Check if the relationship is mutual
                    reverse_rels = other_char.get_relationships_by_type(rel.relationship_type)
                    if not any(r.character_name.lower() == char.name.lower() for r in reverse_rels):
                        conflicts.append(
                            f"One-way relationship between {char.name} and {rel.character_name}"
                        )
        
        return conflicts
    
    def generate_character_network(self) -> Dict[str, List[str]]:
        """Generate a network of character relationships."""
        network = {}
        for char in self.characters.values():
            connections = [rel.character_name for rel in char.relationships]
            network[char.name] = connections
        return network
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert character manager to dictionary."""
        return {
            "characters": {
                name: char.to_dict() 
                for name, char in self.characters.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterManager":
        """Create character manager from dictionary."""
        manager = cls()
        for char_data in data.get("characters", {}).values():
            character = Character.from_dict(char_data)
            manager.add_character(character)
        return manager