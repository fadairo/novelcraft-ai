"""Character management for NovelCraft AI."""

from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


class CharacterRole(Enum):
    """Character role in the story."""
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"


@dataclass
class Character:
    """Represents a character in the novel."""
    
    name: str
    age: int = 0
    role: CharacterRole = CharacterRole.SUPPORTING
    description: str = ""
    backstory: str = ""
    traits: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    appearance: str = ""
    personality: str = ""
    motivation: str = ""
    conflict: str = ""
    arc: str = ""
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_trait(self, trait: str) -> None:
        """Add a character trait."""
        if trait not in self.traits:
            self.traits.append(trait)
    
    def remove_trait(self, trait: str) -> None:
        """Remove a character trait."""
        if trait in self.traits:
            self.traits.remove(trait)
    
    def add_goal(self, goal: str) -> None:
        """Add a character goal."""
        if goal not in self.goals:
            self.goals.append(goal)
    
    def remove_goal(self, goal: str) -> None:
        """Remove a character goal."""
        if goal in self.goals:
            self.goals.remove(goal)
    
    def add_relationship(self, character_name: str, relationship: str) -> None:
        """Add a relationship with another character."""
        self.relationships[character_name] = relationship
    
    def remove_relationship(self, character_name: str) -> None:
        """Remove a relationship with another character."""
        if character_name in self.relationships:
            del self.relationships[character_name]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert character to dictionary for serialization."""
        return {
            "name": self.name,
            "age": self.age,
            "role": self.role.value,
            "description": self.description,
            "backstory": self.backstory,
            "traits": self.traits,
            "goals": self.goals,
            "relationships": self.relationships,
            "appearance": self.appearance,
            "personality": self.personality,
            "motivation": self.motivation,
            "conflict": self.conflict,
            "arc": self.arc,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Character":
        """Create character from dictionary."""
        character = cls(
            name=data["name"],
            age=data.get("age", 0),
            role=CharacterRole(data.get("role", "supporting")),
            description=data.get("description", ""),
            backstory=data.get("backstory", ""),
            traits=data.get("traits", []),
            goals=data.get("goals", []),
            relationships=data.get("relationships", {}),
            appearance=data.get("appearance", ""),
            personality=data.get("personality", ""),
            motivation=data.get("motivation", ""),
            conflict=data.get("conflict", ""),
            arc=data.get("arc", ""),
            notes=data.get("notes", ""),
        )
        
        if "created_at" in data:
            character.created_at = datetime.fromisoformat(data["created_at"])
        
        return character
    
    def __str__(self) -> str:
        """String representation of character."""
        return f"{self.name} ({self.role.value}, age {self.age})"


class CharacterManager:
    """Manages all characters in a project."""
    
    def __init__(self):
        self.characters: Dict[str, Character] = {}
    
    def add_character(self, character: Character) -> None:
        """Add a character to the manager."""
        self.characters[character.name] = character
    
    def remove_character(self, name: str) -> None:
        """Remove a character by name."""
        if name in self.characters:
            del self.characters[name]
    
    def get_character(self, name: str) -> Optional[Character]:
        """Get a character by name."""
        return self.characters.get(name)
    
    def list_characters(self) -> List[Character]:
        """Get all characters as a list."""
        return list(self.characters.values())
    
    def get_characters_by_role(self, role: CharacterRole) -> List[Character]:
        """Get characters by their role."""
        return [char for char in self.characters.values() if char.role == role]
    
    def get_protagonists(self) -> List[Character]:
        """Get all protagonist characters."""
        return self.get_characters_by_role(CharacterRole.PROTAGONIST)
    
    def get_antagonists(self) -> List[Character]:
        """Get all antagonist characters."""
        return self.get_characters_by_role(CharacterRole.ANTAGONIST)
    
    def search_characters(self, query: str) -> List[Character]:
        """Search characters by name, description, or traits."""
        query_lower = query.lower()
        results = []
        
        for character in self.characters.values():
            if (query_lower in character.name.lower() or
                query_lower in character.description.lower() or
                any(query_lower in trait.lower() for trait in character.traits) or
                query_lower in character.backstory.lower()):
                results.append(character)
        
        return results
    
    def get_character_relationships(self, character_name: str) -> Dict[str, str]:
        """Get all relationships for a specific character."""
        character = self.get_character(character_name)
        if character:
            return character.relationships
        return {}
    
    def add_relationship(self, char1_name: str, char2_name: str, relationship: str) -> None:
        """Add a bidirectional relationship between two characters."""
        char1 = self.get_character(char1_name)
        char2 = self.get_character(char2_name)
        
        if char1 and char2:
            char1.add_relationship(char2_name, relationship)
            # You might want to add the reverse relationship too
            # char2.add_relationship(char1_name, f"related to {char1_name}")
    
    def generate_character_summary(self) -> str:
        """Generate a summary of all characters for AI context."""
        if not self.characters:
            return "No characters defined in this project."
        
        summary = "CHARACTER INFORMATION:\n\n"
        
        for role in CharacterRole:
            chars = self.get_characters_by_role(role)
            if chars:
                summary += f"{role.value.title()} Characters:\n"
                for char in chars:
                    summary += f"• {char.name}"
                    if char.age:
                        summary += f" (age {char.age})"
                    if char.description:
                        summary += f": {char.description}"
                    summary += "\n"
                    
                    if char.traits:
                        summary += f"  Traits: {', '.join(char.traits)}\n"
                    if char.goals:
                        summary += f"  Goals: {', '.join(char.goals)}\n"
                    if char.backstory:
                        summary += f"  Background: {char.backstory[:200]}{'...' if len(char.backstory) > 200 else ''}\n"
                    summary += "\n"
                summary += "\n"
        
        return summary.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert character manager to dictionary for serialization."""
        return {
            "characters": {name: char.to_dict() for name, char in self.characters.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterManager":
        """Create character manager from dictionary."""
        manager = cls()
        
        if "characters" in data:
            for name, char_data in data["characters"].items():
                character = Character.from_dict(char_data)
                manager.add_character(character)
        
        return manager


@dataclass
class CharacterSheet:
    """Detailed character sheet for in-depth character development."""
    
    character: Character
    
    # Physical characteristics
    height: str = ""
    weight: str = ""
    hair_color: str = ""
    eye_color: str = ""
    distinguishing_marks: str = ""
    
    # Background
    birthplace: str = ""
    family: str = ""
    education: str = ""
    occupation: str = ""
    social_class: str = ""
    
    # Psychological profile
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    fears: List[str] = field(default_factory=list)
    secrets: List[str] = field(default_factory=list)
    
    # Story elements
    introduction_scene: str = ""
    character_voice: str = ""
    dialogue_style: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert character sheet to dictionary."""
        return {
            "character": self.character.to_dict(),
            "height": self.height,
            "weight": self.weight,
            "hair_color": self.hair_color,
            "eye_color": self.eye_color,
            "distinguishing_marks": self.distinguishing_marks,
            "birthplace": self.birthplace,
            "family": self.family,
            "education": self.education,
            "occupation": self.occupation,
            "social_class": self.social_class,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "fears": self.fears,
            "secrets": self.secrets,
            "introduction_scene": self.introduction_scene,
            "character_voice": self.character_voice,
            "dialogue_style": self.dialogue_style,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterSheet":
        """Create character sheet from dictionary."""
        character = Character.from_dict(data["character"])
        
        return cls(
            character=character,
            height=data.get("height", ""),
            weight=data.get("weight", ""),
            hair_color=data.get("hair_color", ""),
            eye_color=data.get("eye_color", ""),
            distinguishing_marks=data.get("distinguishing_marks", ""),
            birthplace=data.get("birthplace", ""),
            family=data.get("family", ""),
            education=data.get("education", ""),
            occupation=data.get("occupation", ""),
            social_class=data.get("social_class", ""),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            fears=data.get("fears", []),
            secrets=data.get("secrets", []),
            introduction_scene=data.get("introduction_scene", ""),
            character_voice=data.get("character_voice", ""),
            dialogue_style=data.get("dialogue_style", ""),
        )