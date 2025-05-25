#!/usr/bin/env python3
"""
character_manager.py - Standalone Character List Creator & Editor

This script creates and modifies characters_revised.md files for novel projects.
It can analyze existing manuscripts to discover characters or work from user input.
"""

import os
import re
import glob
import json
import argparse
import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import anthropic

class CharacterManager:
    """Manages character creation and editing for novel projects."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.project_dir = None
        self.genre = "Literary Fiction"
        self.inspirations = ""
        self.chapters = {}
        self.project_context = {}
        self.existing_characters = ""
    
    def load_project(self, project_dir: str):
        """Load project files and context."""
        self.project_dir = project_dir
        print(f"📖 Loading project from: {project_dir}")
        
        # Load project context
        self.project_context = self._load_project_files()
        
        # Load inspirations
        self.inspirations = self._load_inspirations()
        
        # Load chapters
        self.chapters = self._load_all_chapters()
        
        # Load existing character list
        self.existing_characters = self._load_existing_characters()
        
        # Extract project metadata
        self._extract_project_metadata()
        
        print(f"✅ Loaded {len(self.chapters)} chapters")
        print(f"📚 Genre: {self.genre}")
        print(f"🎭 Existing characters: {'Found' if self.existing_characters else 'None'}")
    
    def _load_project_files(self) -> Dict[str, str]:
        """Load synopsis, outline files."""
        files = {}
        
        project_files = {
            'synopsis': ['synopsis.md', 'synopsis.txt', 'synopsis_revised.md'],
            'outline': ['outline.md', 'outline.txt', 'Outline.md', 'outline_revised.md']
        }
        
        for file_type, possible_names in project_files.items():
            for name in possible_names:
                file_path = os.path.join(self.project_dir, name)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        files[file_type] = f.read()
                    print(f"  ✓ {file_type}: {name}")
                    break
            else:
                files[file_type] = ""
        
        return files
    
    def _load_inspirations(self) -> str:
        """Load literary inspirations."""
        inspiration_file = os.path.join(self.project_dir, "inspiration.md")
        if os.path.exists(inspiration_file):
            with open(inspiration_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def _load_existing_characters(self) -> str:
        """Load existing character files."""
        character_files = ['characters_revised.md', 'characters.md', 'characterList.md', 'characters.txt']
        
        for filename in character_files:
            file_path = os.path.join(self.project_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                print(f"  ✓ existing characters: {filename}")
                # Extract content after metadata separator if present
                if "---" in content:
                    return content.split("---")[-1].strip()
                return content
        
        return ""
    
    def _load_all_chapters(self) -> Dict[int, Dict[str, str]]:
        """Load all chapter files."""
        chapters = {}
        
        # Look for chapters in various directories
        chapter_dirs = ['chapters', 'content', 'manuscript', 'revised', '.']
        
        for chapter_dir in chapter_dirs:
            search_dir = os.path.join(self.project_dir, chapter_dir)
            if not os.path.exists(search_dir):
                continue
            
            # Find chapter files
            patterns = ['chapter_*.md', 'chapter*.md', 'ch_*.md']
            for pattern in patterns:
                files = glob.glob(os.path.join(search_dir, pattern))
                for file_path in files:
                    # Skip backup files but include revised files
                    if any(skip in file_path.lower() for skip in ['backup']):
                        continue
                    
                    # Extract chapter number
                    chapter_num = self._extract_chapter_number(file_path)
                    if chapter_num and chapter_num not in chapters:  # Prefer first found
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        chapters[chapter_num] = {
                            'file_path': file_path,
                            'content': content,
                            'word_count': len(content.split())
                        }
        
        return chapters
    
    def _extract_chapter_number(self, file_path: str) -> Optional[int]:
        """Extract chapter number from filename."""
        filename = os.path.basename(file_path)
        patterns = [r'chapter[_\s]*(\d+)', r'ch[_\s]*(\d+)', r'(\d+)']
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
    
    def _extract_project_metadata(self):
        """Extract project metadata from context."""
        # Try to determine genre from project files
        if self.project_context.get('synopsis'):
            synopsis = self.project_context['synopsis']
            if any(word in synopsis.lower() for word in ['spy', 'intelligence', 'espionage']):
                self.genre = "Literary Spy Fiction"
            elif any(word in synopsis.lower() for word in ['mystery', 'detective']):
                self.genre = "Literary Mystery"
            elif any(word in synopsis.lower() for word in ['romance']):
                self.genre = "Literary Romance"
            elif any(word in synopsis.lower() for word in ['fantasy', 'magic']):
                self.genre = "Literary Fantasy"
    
    def discover_characters_from_manuscript(self) -> Dict[str, int]:
        """Analyze manuscript to discover character names and frequency."""
        print("🔍 Analyzing manuscript for characters...")
        
        character_mentions = {}
        dialogue_speakers = {}
        
        for chapter_num, chapter in self.chapters.items():
            content = chapter['content']
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for dialogue patterns
                dialogue_patterns = [
                    r'^"[^"]*"\s*,?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|asked|replied|whispered|shouted)',
                    r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|asked|replied|whispered|shouted)\s*,?\s*"',
                    r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*:\s*"',  # Name: "dialogue"
                ]
                
                for pattern in dialogue_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        name = match.strip()
                        if len(name) < 25 and not any(word in name.lower() for word in ['chapter', 'said']):
                            dialogue_speakers[name] = dialogue_speakers.get(name, 0) + 1
                
                # Look for capitalized names (potential characters)
                name_pattern = r'\b([A-Z][a-z]{2,12}(?:\s+[A-Z][a-z]{2,12})?)\b'
                matches = re.findall(name_pattern, line)
                for match in matches:
                    name = match.strip()
                    # Filter out common words that aren't names
                    if (len(name) < 25 and 
                        not any(word in name.lower() for word in [
                            'chapter', 'the', 'and', 'but', 'when', 'where', 'what', 'who',
                            'how', 'why', 'this', 'that', 'these', 'those', 'cambridge',
                            'prague', 'london', 'england', 'russia', 'soviet', 'british'
                        ])):
                        character_mentions[name] = character_mentions.get(name, 0) + 1
        
        # Combine and prioritize dialogue speakers
        all_characters = {}
        for name, count in dialogue_speakers.items():
            all_characters[name] = count * 3  # Weight dialogue speakers higher
        
        for name, count in character_mentions.items():
            if name in all_characters:
                all_characters[name] += count
            else:
                all_characters[name] = count
        
        # Filter to likely main characters (mentioned frequently)
        main_characters = {name: count for name, count in all_characters.items() 
                          if count >= 3}  # Mentioned at least 3 times
        
        # Sort by frequency
        sorted_characters = dict(sorted(main_characters.items(), key=lambda x: x[1], reverse=True))
        
        print(f"  Found {len(sorted_characters)} potential main characters")
        return sorted_characters
    
    def create_character_list_from_analysis(self, discovered_characters: Dict[str, int]) -> str:
        """Create character list using AI analysis of discovered characters."""
        print("🤖 Creating character list from manuscript analysis...")
        
        # Prepare character evidence
        char_evidence = []
        for name, count in list(discovered_characters.items())[:12]:  # Top 12 characters
            char_evidence.append(f"- {name}: mentioned {count} times")
        
        # Prepare sample content from chapters
        sample_content = []
        for chapter_num in sorted(list(self.chapters.keys())[:5]):  # First 5 chapters
            chapter = self.chapters[chapter_num]
            content_sample = chapter['content'][:800] + "..." if len(chapter['content']) > 800 else chapter['content']
            sample_content.append(f"Chapter {chapter_num} excerpt:\n{content_sample}")
        
        prompt = f"""Create a comprehensive character list for this {self.genre} novel based on manuscript analysis.

NOVEL CONTEXT:
Genre: {self.genre}
Total Chapters: {len(self.chapters)}

LITERARY INSPIRATIONS:
{self.inspirations if self.inspirations else "Literary fiction with genre elements"}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', 'Not available')}
OUTLINE: {self.project_context.get('outline', 'Not available')}

EXISTING CHARACTER LIST:
{self.existing_characters if self.existing_characters else 'None - creating new list'}

DISCOVERED CHARACTERS FROM MANUSCRIPT:
{chr(10).join(char_evidence)}

MANUSCRIPT SAMPLES:
{chr(10).join(sample_content)}

Create a detailed character list that includes ALL major characters found in the manuscript. For each character, provide:

## CHARACTER NAME
**Role in Story:** [Primary/Secondary/Supporting - their function in the narrative]
**Character Description:** [Physical and personality traits as shown in manuscript]
**Character Arc:** [Development journey, growth, and changes]
**Key Relationships:** [Important connections with other characters]
**Voice & Dialogue Style:** [How they speak, distinctive traits]
**Motivations & Goals:** [What drives them, internal/external conflicts]
**Background & History:** [Relevant past, profession, circumstances]
**Thematic Function:** [How they serve the novel's themes]
**Development Notes:** [Areas for consistency and improvement]

REQUIREMENTS:
- Include at least the top 8-10 most significant characters
- Base descriptions on what actually appears in the manuscript
- Provide substantial detail (150-200 words per major character)
- Address character consistency and development needs
- Ensure characters serve the {self.genre} genre and literary goals
- Include both protagonists and antagonists
- Note any character relationships and dynamics

Focus on characters that actually appear in the written chapters with speaking roles or significant presence."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error creating character list: {e}"
    
    def create_character_list_from_outline(self) -> str:
        """Create character list based on outline and synopsis when no manuscript exists."""
        print("🤖 Creating character list from outline and synopsis...")
        
        prompt = f"""Create a detailed character list for this {self.genre} novel based on the project outline and synopsis.

NOVEL CONTEXT:
Genre: {self.genre}

LITERARY INSPIRATIONS:
{self.inspirations if self.inspirations else "Literary fiction with genre elements"}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', 'Not available')}
OUTLINE: {self.project_context.get('outline', 'Not available')}

EXISTING CHARACTER LIST (if any):
{self.existing_characters if self.existing_characters else 'None - creating new list'}

Create a comprehensive character list that serves this {self.genre} story. For each character, provide:

## CHARACTER NAME
**Role in Story:** [Primary/Secondary/Supporting - their function in the narrative]
**Character Description:** [Physical and personality traits]
**Character Arc:** [Development journey, growth, and changes planned]
**Key Relationships:** [Important connections with other characters]
**Voice & Dialogue Style:** [How they should speak, distinctive traits]
**Motivations & Goals:** [What drives them, internal/external conflicts]
**Background & History:** [Relevant past, profession, circumstances]
**Thematic Function:** [How they serve the novel's themes]
**Development Notes:** [Writing considerations and character consistency notes]

REQUIREMENTS:
- Create 6-10 well-developed characters appropriate for {self.genre}
- Include protagonists, antagonists, and key supporting characters
- Ensure character diversity and complexity
- Each major character should have 150-200 words of detail
- Characters should serve both plot and thematic purposes
- Consider character relationships and dynamics
- Make characters appropriate for literary fiction standards

Base the characters on the synopsis and outline provided, creating rich, complex individuals suitable for {self.genre}."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022", 
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error creating character list: {e}"
    
    def enhance_existing_characters(self) -> str:
        """Enhance and improve existing character list."""
        print("🤖 Enhancing existing character list...")
        
        discovered_characters = {}
        if self.chapters:
            discovered_characters = self.discover_characters_from_manuscript()
        
        char_evidence = []
        if discovered_characters:
            for name, count in list(discovered_characters.items())[:10]:
                char_evidence.append(f"- {name}: appears {count} times in manuscript")
        
        prompt = f"""Enhance and improve this existing character list for a {self.genre} novel.

CURRENT CHARACTER LIST:
{self.existing_characters}

NOVEL CONTEXT:
Genre: {self.genre}
Chapters Written: {len(self.chapters)}

LITERARY INSPIRATIONS:
{self.inspirations if self.inspirations else "Literary fiction"}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', 'Not available')}
OUTLINE: {self.project_context.get('outline', 'Not available')}

CHARACTER EVIDENCE FROM MANUSCRIPT:
{chr(10).join(char_evidence) if char_evidence else 'No manuscript analysis available'}

ENHANCEMENT REQUIREMENTS:
1. Expand and deepen existing character descriptions
2. Add any missing major characters found in the manuscript
3. Improve character consistency and development notes
4. Strengthen character relationships and dynamics
5. Ensure characters serve {self.genre} themes effectively
6. Add specific dialogue voice guidance
7. Include character arc development plans
8. Address any gaps or inconsistencies

STRUCTURE FOR EACH CHARACTER:
## CHARACTER NAME
**Role in Story:** [Function and importance]
**Character Description:** [Physical and personality traits]
**Character Arc:** [Development and growth journey]
**Key Relationships:** [Dynamics with other characters]
**Voice & Dialogue Style:** [Speaking patterns and personality in dialogue]
**Motivations & Goals:** [Driving forces and conflicts]
**Background & History:** [Relevant past and circumstances]
**Thematic Function:** [How they serve the novel's themes]
**Development Notes:** [Consistency and improvement guidance]

Provide comprehensive, detailed profiles (150-200 words per major character) that will serve as a definitive character bible for the novel."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error enhancing characters: {e}"
    
    def interactive_character_creation(self) -> str:
        """Interactive character creation with user input."""
        print("\n🎭 Interactive Character Creation")
        print("=" * 50)
        
        characters = []
        
        while True:
            print(f"\nCreating character #{len(characters) + 1}")
            
            name = input("Character name (or 'done' to finish): ").strip()
            if name.lower() == 'done':
                break
            
            role = input("Role (protagonist/antagonist/supporting): ").strip()
            description = input("Brief description: ").strip()
            
            character = {
                'name': name,
                'role': role,
                'description': description
            }
            characters.append(character)
            
            print(f"✓ Added {name}")
        
        if not characters:
            print("No characters created.")
            return ""
        
        # Create character list from user input
        char_descriptions = []
        for char in characters:
            char_descriptions.append(f"- {char['name']}: {char['role']} - {char['description']}")
        
        prompt = f"""Create a detailed character list based on user input for a {self.genre} novel.

USER-PROVIDED CHARACTERS:
{chr(10).join(char_descriptions)}

NOVEL CONTEXT:
Genre: {self.genre}
Literary Inspirations: {self.inspirations if self.inspirations else "Literary fiction"}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', 'Not available')}

For each character provided, create a comprehensive profile:

## CHARACTER NAME
**Role in Story:** [Expand on their function]
**Character Description:** [Detailed physical and personality traits]
**Character Arc:** [Potential development journey]
**Key Relationships:** [How they relate to other characters]
**Voice & Dialogue Style:** [Speaking patterns]
**Motivations & Goals:** [What drives them]
**Background & History:** [Relevant past]
**Thematic Function:** [How they serve the story themes]
**Development Notes:** [Writing guidance]

Expand each character into a full 150-200 word profile suitable for {self.genre}."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error creating interactive characters: {e}"
    
    def save_character_list(self, character_content: str) -> str:
        """Save character list to file."""
        output_path = os.path.join(self.project_dir, "characters_revised.md")
        
        # Create backup if file exists
        if os.path.exists(output_path):
            backup_path = f"{output_path}.backup"
            os.rename(output_path, backup_path)
            print(f"📄 Previous file backed up to: {os.path.basename(backup_path)}")
        
        # Write new file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Revised Character List\n\n")
            f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Project:** {os.path.basename(self.project_dir)}\n")
            f.write(f"**Genre:** {self.genre}\n\n")
            f.write("---\n\n")
            f.write(character_content)
        
        print(f"✅ Character list saved to: {os.path.basename(output_path)}")
        return output_path

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Create and manage character lists for novel projects",
        epilog="""
Examples:
  # Analyze manuscript and create character list
  python character_manager.py glasshouse --from-manuscript
  
  # Create from outline/synopsis only
  python character_manager.py glasshouse --from-outline
  
  # Enhance existing character list
  python character_manager.py glasshouse --enhance
  
  # Interactive character creation
  python character_manager.py glasshouse --interactive
  
  # Show discovered characters without creating list
  python character_manager.py glasshouse --discover-only
        """
    )
    parser.add_argument(
        "project_dir",
        help="Project directory containing the novel"
    )
    parser.add_argument(
        "--from-manuscript",
        action="store_true",
        help="Create character list by analyzing existing manuscript"
    )
    parser.add_argument(
        "--from-outline", 
        action="store_true",
        help="Create character list from synopsis and outline"
    )
    parser.add_argument(
        "--enhance",
        action="store_true",
        help="Enhance existing character list"
    )
    parser.add_argument(
        "--interactive",
        action="store_true", 
        help="Create characters interactively with user input"
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Only show discovered characters, don't create file"
    )
    parser.add_argument(
        "--output",
        help="Custom output filename (default: characters_revised.md)"
    )
    
    args = parser.parse_args()
    
    # Initialize character manager
    try:
        manager = CharacterManager()
    except Exception as e:
        print(f"❌ Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        print(f"🎭 Character Manager - {os.path.basename(args.project_dir)}")
        print("=" * 60)
        
        # Load project
        manager.load_project(args.project_dir)
        
        # Determine action
        if args.discover_only:
            discovered = manager.discover_characters_from_manuscript()
            print(f"\n🔍 Discovered Characters:")
            print("=" * 30)
            for name, count in discovered.items():
                print(f"  {name}: {count} mentions")
            return 0
        
        # Create or enhance character list
        character_content = ""
        
        if args.from_manuscript:
            if not manager.chapters:
                print("❌ No chapters found for manuscript analysis")
                return 1
            discovered = manager.discover_characters_from_manuscript()
            character_content = manager.create_character_list_from_analysis(discovered)
            
        elif args.from_outline:
            character_content = manager.create_character_list_from_outline()
            
        elif args.enhance:
            if not manager.existing_characters:
                print("❌ No existing character list found to enhance")
                return 1
            character_content = manager.enhance_existing_characters()
            
        elif args.interactive:
            character_content = manager.interactive_character_creation()
            
        else:
            # Auto-detect best approach
            if manager.existing_characters:
                print("📝 Enhancing existing character list...")
                character_content = manager.enhance_existing_characters()
            elif manager.chapters:
                print("📖 Creating character list from manuscript...")
                discovered = manager.discover_characters_from_manuscript()
                character_content = manager.create_character_list_from_analysis(discovered)
            else:
                print("📋 Creating character list from outline...")
                character_content = manager.create_character_list_from_outline()
        
        if character_content and "Error" not in character_content:
            # Save character list
            output_path = manager.save_character_list(character_content)
            
            print(f"\n✅ Character list creation complete!")
            print(f"📁 File: {output_path}")
            print(f"📊 Ready for use in novel revision workflows")
        else:
            print(f"❌ Failed to create character list: {character_content}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())