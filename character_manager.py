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
        
        self.project_context = self._load_project_files()
        self.inspirations = self._load_inspirations()
        self.chapters = self._load_all_chapters()
        self.existing_characters = self._load_existing_characters()
        self._extract_project_metadata()
    
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
                if "---" in content:
                    return content.split("---")[-1].strip()
                return content
        
        return ""
    
    def _load_all_chapters(self) -> Dict[int, Dict[str, str]]:
        """Load all chapter files."""
        chapters = {}
        
        chapter_dirs = ['chapters', 'content', 'manuscript', 'revised', '.']
        
        for chapter_dir in chapter_dirs:
            search_dir = os.path.join(self.project_dir, chapter_dir)
            if not os.path.exists(search_dir):
                continue
            
            patterns = ['chapter_*.md', 'chapter*.md', 'ch_*.md']
            for pattern in patterns:
                files = glob.glob(os.path.join(search_dir, pattern))
                for file_path in files:
                    if any(skip in file_path.lower() for skip in ['backup']):
                        continue
                    
                    chapter_num = self._extract_chapter_number(file_path)
                    if chapter_num and chapter_num not in chapters:
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
        character_mentions = {}
        dialogue_speakers = {}
        
        for chapter_num, chapter in self.chapters.items():
            content = chapter['content']
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                dialogue_patterns = [
                    r'^"[^"]*"\s*,?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|asked|replied|whispered|shouted)',
                    r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|asked|replied|whispered|shouted)\s*,?\s*"',
                    r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*:\s*"',
                ]
                
                for pattern in dialogue_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        name = match.strip()
                        if len(name) < 25 and not any(word in name.lower() for word in ['chapter', 'said']):
                            dialogue_speakers[name] = dialogue_speakers.get(name, 0) + 1
                
                name_pattern = r'\b([A-Z][a-z]{2,12}(?:\s+[A-Z][a-z]{2,12})?)\b'
                matches = re.findall(name_pattern, line)
                for match in matches:
                    name = match.strip()
                    if (len(name) < 25 and 
                        not any(word in name.lower() for word in [
                            'chapter', 'the', 'and', 'but', 'when', 'where', 'what', 'who',
                            'how', 'why', 'this', 'that', 'these', 'those', 'cambridge',
                            'prague', 'london', 'england', 'russia', 'soviet', 'british'
                        ])):
                        character_mentions[name] = character_mentions.get(name, 0) + 1
        
        all_characters = {}
        for name, count in dialogue_speakers.items():
            all_characters[name] = count * 3
        
        for name, count in character_mentions.items():
            if name in all_characters:
                all_characters[name] += count
            else:
                all_characters[name] = count
        
        main_characters = {name: count for name, count in all_characters.items() 
                          if count >= 3}
        
        sorted_characters = dict(sorted(main_characters.items(), key=lambda x: x[1], reverse=True))
        
        return sorted_characters
    
    def create_character_list_from_analysis(self, discovered_characters: Dict[str, int]) -> str:
        """Create character list using AI analysis of discovered characters."""
        char_evidence = []
        for name, count in list(discovered_characters.items())[:12]:
            char_evidence.append(f"- {name}: mentioned {count} times")
        
        sample_content = []
        for chapter_num in sorted(list(self.chapters.keys())[:5]):
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
        discovered_characters = {}
        if self.chapters:
            discovered_characters = self.discover_characters_from_manuscript()
        
        char_evidence = []
        if discovered_characters:
            for name, count in list(discovered_characters.items())[:10]:
                char_evidence.append(f"- {name}: appears {count} times in manuscript")
        
        # Extract character names from existing list for batch processing
        character_names = self._extract_character_names_from_list(self.existing_characters)
        
        if len(character_names) > 6:
            # Process in batches to avoid token limits
            return self._enhance_characters_in_batches(character_names, char_evidence)
        else:
            # Process all at once for smaller lists
            return self._enhance_all_characters(char_evidence)
    
    def _extract_character_names_from_list(self, character_list: str) -> List[str]:
        """Extract character names from existing character list."""
        names = []
        lines = character_list.split('\n')
        for line in lines:
            # Look for character headers (## CHARACTER NAME or similar)
            if line.startswith('##') or line.startswith('#'):
                # Extract name, cleaning up markdown and common prefixes
                name = re.sub(r'^#+\s*', '', line).strip()
                name = re.sub(r'\*\*.*?\*\*', '', name).strip()  # Remove bold formatting
                if name and len(name) < 50:  # Reasonable name length
                    names.append(name)
        return names
    
    def _enhance_characters_in_batches(self, character_names: List[str], char_evidence: List[str]) -> str:
        """Process characters in batches to avoid token limits."""
        batch_size = 3
        enhanced_characters = []
        
        for i in range(0, len(character_names), batch_size):
            batch_names = character_names[i:i+batch_size]
            
            # Extract relevant sections from existing character list
            batch_content = self._extract_character_sections(batch_names)
            
            enhanced_batch = self._enhance_character_batch(batch_content, char_evidence, batch_names)
            if enhanced_batch and "Error" not in enhanced_batch:
                enhanced_characters.append(enhanced_batch)
        
        return "\n\n".join(enhanced_characters)
    
    def _extract_character_sections(self, character_names: List[str]) -> str:
        """Extract sections for specific characters from existing list."""
        sections = []
        current_section = ""
        current_char = None
        lines = self.existing_characters.split('\n')
        
        for line in lines:
            if line.startswith('##') or line.startswith('#'):
                # Save previous section
                if current_char and current_section:
                    sections.append(current_section.strip())
                
                # Check if this is one of our target characters
                header_name = re.sub(r'^#+\s*', '', line).strip()
                header_name = re.sub(r'\*\*.*?\*\*', '', header_name).strip()
                
                current_char = None
                for target_name in character_names:
                    if target_name.lower() in header_name.lower() or header_name.lower() in target_name.lower():
                        current_char = target_name
                        current_section = line + "\n"
                        break
                
                if not current_char:
                    current_section = ""
            elif current_char:
                current_section += line + "\n"
        
        # Don't forget the last section
        if current_char and current_section:
            sections.append(current_section.strip())
        
        return "\n\n".join(sections)
    
    def _enhance_character_batch(self, batch_content: str, char_evidence: List[str], batch_names: List[str]) -> str:
        """Enhance a batch of characters."""
        prompt = f"""Enhance these specific characters for a {self.genre} novel. Complete ALL characters fully with no truncation.

CHARACTERS TO ENHANCE:
{batch_content}

CHARACTER EVIDENCE FROM MANUSCRIPT:
{chr(10).join(char_evidence) if char_evidence else 'No manuscript analysis available'}

GENRE: {self.genre}
LITERARY INSPIRATIONS: {self.inspirations[:500] if self.inspirations else "Literary fiction"}

For each character, provide a complete enhanced profile:

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

CRITICAL: Complete ALL {len(batch_names)} characters fully. Do not truncate or summarize. Each character needs 150-200 words of detailed development."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=6000,  # Increased for batch processing
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error enhancing character batch: {e}"
    
    def _enhance_all_characters(self, char_evidence: List[str]) -> str:
        """Enhance all characters at once for smaller lists."""
        prompt = f"""Enhance and improve this complete character list for a {self.genre} novel. Process ALL characters fully.

CURRENT CHARACTER LIST:
{self.existing_characters}

NOVEL CONTEXT:
Genre: {self.genre}
Chapters Written: {len(self.chapters)}

LITERARY INSPIRATIONS:
{self.inspirations if self.inspirations else "Literary fiction"}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', 'Not available')[:800]}
OUTLINE: {self.project_context.get('outline', 'Not available')[:800]}

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

CRITICAL: Provide comprehensive, detailed profiles (150-200 words per character) for ALL characters. Complete every character fully without truncation."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8000,  # Increased token limit
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error enhancing characters: {e}"
    
    def create_characters_auto(self) -> str:
        """Automatically determine best approach and create character list."""
        if self.existing_characters:
            return self.enhance_existing_characters()
        elif self.chapters:
            discovered = self.discover_characters_from_manuscript()
            return self.create_character_list_from_analysis(discovered)
        else:
            return self.create_character_list_from_outline()
    
    def save_character_list(self, character_content: str) -> str:
        """Save character list to file."""
        output_path = os.path.join(self.project_dir, "characters_revised.md")
        
        if os.path.exists(output_path):
            backup_path = f"{output_path}.backup"
            os.rename(output_path, backup_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Revised Character List\n\n")
            f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Project:** {os.path.basename(self.project_dir)}\n")
            f.write(f"**Genre:** {self.genre}\n\n")
            f.write("---\n\n")
            f.write(character_content)
        
        return output_path

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Create and manage character lists for novel projects"
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
        "--discover-only",
        action="store_true",
        help="Only show discovered characters, don't create file"
    )
    
    args = parser.parse_args()
    
    try:
        manager = CharacterManager()
    except Exception as e:
        return 1
    
    try:
        manager.load_project(args.project_dir)
        
        if args.discover_only:
            discovered = manager.discover_characters_from_manuscript()
            for name, count in discovered.items():
                print(f"{name}: {count}")
            return 0
        
        character_content = ""
        
        if args.from_manuscript:
            if not manager.chapters:
                return 1
            discovered = manager.discover_characters_from_manuscript()
            character_content = manager.create_character_list_from_analysis(discovered)
            
        elif args.from_outline:
            character_content = manager.create_character_list_from_outline()
            
        elif args.enhance:
            if not manager.existing_characters:
                return 1
            character_content = manager.enhance_existing_characters()
            
        else:
            character_content = manager.create_characters_auto()
        
        if character_content and "Error" not in character_content:
            output_path = manager.save_character_list(character_content)
            print(output_path)
        else:
            return 1
        
        return 0
        
    except Exception as e:
        return 1

if __name__ == "__main__":
    exit(main())