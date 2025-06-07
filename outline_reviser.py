#!/usr/bin/env python3
"""
outline_reviser.py - AI-Powered Novel Outline Reviser

This script uses Claude API to analyze and revise novel outlines for better
structure, pacing, narrative effectiveness, and CONSISTENCY. It identifies
and fixes continuity errors, timeline issues, and character inconsistencies.

Features:
- Detects and fixes consistency/continuity issues
- Analyzes existing outline for structural issues
- Expands scene-level details
- Ensures proper story arc and pacing
- Adds character development tracking
- Integrates themes throughout
- Windows-compatible with proper encoding
"""

import os
import re
import json
import argparse
import datetime
import sys
import time
import random
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import anthropic

# Set UTF-8 encoding for Windows
if sys.platform.startswith('win'):
    import locale
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass

class AIOutlineReviser:
    """AI-powered outline reviser using Claude API."""
    
    # Token limits for different operations
    MAX_TOKENS_STANDARD = 30000
    MAX_TOKENS_LARGE = 60000
    MAX_TOKENS_ANALYSIS = 10000
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.project_dir = None
        self.outline_content = ""
        self.synopsis_content = ""
        self.character_content = ""
        self.chapters = {}
        self.act_structure = {}
        
    def _safe_read_file(self, file_path: str) -> str:
        """Safely read a file with multiple encoding attempts."""
        encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1', 'ascii']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # Last resort
        try:
            with open(file_path, 'rb') as f:
                raw_content = f.read()
                return raw_content.decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return ""
    
    def _safe_write_file(self, file_path: str, content: str) -> bool:
        """Safely write a file with UTF-8 encoding."""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            cleaned_content = content.encode('utf-8', errors='replace').decode('utf-8')
            
            with open(file_path, 'w', encoding='utf-8', errors='replace', newline='\n') as f:
                f.write(cleaned_content)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return False
    
    def _make_api_request_with_retry(self, request_func, max_retries=3):
        """Make API request with retry logic for overloaded errors."""
        for attempt in range(max_retries):
            try:
                return request_func()
            except Exception as e:
                error_str = str(e).lower()
                if ("overloaded" in error_str or "timeout" in error_str) and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    print(f"\nAPI overloaded/timeout, waiting {wait_time:.1f} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
        
        raise Exception("Max retries exceeded")
    
    def _chunk_content(self, content: str, max_size: int = 15000) -> List[str]:
        """Split content into chunks for processing."""
        # Split by chapters first
        chapter_pattern = r'^(#{1,3}\s*Chapter\s+\d+.*?)$'
        parts = re.split(chapter_pattern, content, flags=re.MULTILINE)
        
        chunks = []
        current_chunk = ""
        
        for part in parts:
            if len(current_chunk) + len(part) < max_size:
                current_chunk += part
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = part
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else [content]
    
    def load_project(self, project_dir: str, chapters_to_analyze: List[int] = None):
        """Load project files including outline, synopsis, and optional chapters."""
        self.project_dir = project_dir
        print(f"Loading project from: {project_dir}")
        
        # Load outline (required)
        outline_files = ['outline.md', 'outline.txt', 'Outline.md', 'Outline.txt']
        for fname in outline_files:
            fpath = os.path.join(project_dir, fname)
            if os.path.exists(fpath):
                self.outline_content = self._safe_read_file(fpath)
                print(f"  Found outline: {fname}")
                break
        
        if not self.outline_content:
            raise ValueError("No outline file found - outline is required")
        
        # Load synopsis
        synopsis_files = ['synopsis.md', 'synopsis.txt']
        for fname in synopsis_files:
            fpath = os.path.join(project_dir, fname)
            if os.path.exists(fpath):
                self.synopsis_content = self._safe_read_file(fpath)
                print(f"  Found synopsis: {fname}")
                break
        
        # Load character file
        character_files = ['characters.md', 'characterList.md', 'characters.txt', 'characterList.txt']
        for fname in character_files:
            fpath = os.path.join(project_dir, fname)
            if os.path.exists(fpath):
                self.character_content = self._safe_read_file(fpath)
                print(f"  Found characters: {fname}")
                break
        
        # Load specific chapters if requested
        if chapters_to_analyze:
            self._load_chapters(chapters_to_analyze)
    
    def _load_chapters(self, chapter_numbers: List[int]):
        """Load specific chapters for analysis."""
        chapters_dir = os.path.join(self.project_dir, "chapters")
        if not os.path.exists(chapters_dir):
            print("  No chapters directory found")
            return
        
        for num in chapter_numbers:
            patterns = [
                f"{num:02d}_chapter_{num}.md",
                f"chapter_{num}.md",
                f"chapter{num}.md",
                f"ch_{num}.md",
                f"Chapter {num}.md"
            ]
            
            for pattern in patterns:
                fpath = os.path.join(chapters_dir, pattern)
                if os.path.exists(fpath):
                    content = self._safe_read_file(fpath)
                    if content:
                        self.chapters[num] = content
                        print(f"  Loaded Chapter {num}")
                        break
    
    def analyze_outline_structure(self) -> Dict[str, Any]:
        """Analyze the existing outline for structure and completeness."""
        print("\nAnalyzing outline structure and consistency...")
        
        # First, try to parse act structure
        self.act_structure = self._parse_act_structure(self.outline_content)
        
        # Check for consistency issues
        consistency_issues = self._check_consistency()
        
        chapters_text = ""
        if self.chapters:
            chapters_text = "\n\nSAMPLE CHAPTERS FOR REFERENCE:\n"
            for num, content in sorted(self.chapters.items()):
                excerpt = ' '.join(content.split()[:500])
                chapters_text += f"\nChapter {num} excerpt:\n{excerpt}...\n"
        
        # Truncate content if too long
        outline_excerpt = self.outline_content[:20000] if len(self.outline_content) > 20000 else self.outline_content
        
        prompt = f"""Analyze this novel outline for structural effectiveness and consistency:

OUTLINE:
{outline_excerpt}

SYNOPSIS:
{self.synopsis_content[:5000] if self.synopsis_content else "Not provided"}

CHARACTERS:
{self.character_content[:5000] if self.character_content else "Not provided"}

{chapters_text}

Analyze and evaluate:

1. **CONSISTENCY AND CONTINUITY** (PRIORITY)
   - Timeline consistency (dates, ages, durations)
   - Character consistency (names, traits, relationships)
   - Location/setting consistency
   - Plot event consistency (cause and effect)
   - Technology/world rules consistency
   - Character knowledge consistency (who knows what when)

2. **STRUCTURAL INTEGRITY**
   - Three-act structure clarity
   - Chapter/scene progression logic
   - Pacing and rhythm
   - Balance between acts

3. **STORY ARC EFFECTIVENESS**
   - Inciting incident placement
   - Rising action development
   - Climax positioning and impact
   - Resolution satisfaction

4. **CHARACTER ARCS**
   - Protagonist journey clarity
   - Supporting character development
   - Character motivation tracking
   - Relationship dynamics

5. **PLOT COHERENCE**
   - Cause-and-effect relationships
   - Plot holes or logic gaps
   - Subplot integration
   - Foreshadowing and payoffs

6. **CONTINUITY ERRORS**
   - List ALL continuity issues found
   - Timeline contradictions
   - Character inconsistencies
   - Setting/location errors
   - Plot logic problems

7. **SCENE-LEVEL DETAIL**
   - Which chapters/scenes need expansion
   - Missing scenes or transitions
   - Redundant or unnecessary scenes

8. **SPECIFIC WEAKNESSES**
   - List top 5 areas needing improvement
   - Focus especially on consistency issues
   - Suggest concrete solutions

Provide detailed, actionable analysis with special attention to ANY inconsistencies or continuity errors."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=self.MAX_TOKENS_ANALYSIS,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            analysis = response.content[0].text
            
            return {
                "analysis": analysis,
                "act_count": len(self.act_structure),
                "chapter_count": self._count_chapters_in_outline(),
                "has_synopsis": bool(self.synopsis_content),
                "has_characters": bool(self.character_content),
                "consistency_issues": consistency_issues
            }
            
        except Exception as e:
            print(f"Error analyzing outline: {e}")
            return {"error": str(e)}
    
    def _parse_act_structure(self, outline: str) -> Dict[str, str]:
        """Parse the outline into acts."""
        acts = {}
        
        # Find act markers
        act_pattern = r'(?:Act|ACT)\s+(\d+|[IVX]+)(?:\s*[-:]?\s*([^\n]*))?'
        lines = outline.split('\n')
        
        current_act = None
        current_content = []
        
        for line in lines:
            act_match = re.match(act_pattern, line, re.IGNORECASE)
            if act_match:
                # Save previous act
                if current_act:
                    acts[current_act] = '\n'.join(current_content).strip()
                
                # Start new act
                act_num = act_match.group(1)
                current_act = f"Act {act_num}"
                current_content = []
                
                # Include act title if present
                if act_match.group(2):
                    current_content.append(act_match.group(2).strip())
            elif current_act:
                current_content.append(line)
        
        # Save final act
        if current_act:
            acts[current_act] = '\n'.join(current_content).strip()
        
        return acts
    
    def _count_chapters_in_outline(self) -> int:
        """Count chapters mentioned in outline."""
        chapter_pattern = r'(?:Chapter|CHAPTER|Ch\.|ch\.)\s*(\d+)'
        matches = re.findall(chapter_pattern, self.outline_content, re.IGNORECASE)
        
        if matches:
            return max(int(m) for m in matches)
        
        # Try counting scenes
        scene_pattern = r'(?:Scene|SCENE)\s*(\d+)'
        scene_matches = re.findall(scene_pattern, self.outline_content, re.IGNORECASE)
        
        return len(scene_matches) if scene_matches else 0
    
    def _check_consistency(self) -> Dict[str, List[str]]:
        """Check for basic consistency issues in the outline."""
        issues = {
            "timeline": [],
            "characters": [],
            "locations": [],
            "plot_logic": []
        }
        
        content_lower = self.outline_content.lower()
        
        # Check for Operation Glasshouse date inconsistencies
        if "operation glasshouse" in content_lower:
            # Find all year references near "operation glasshouse"
            pattern = r'operation glasshouse.*?(\d{4})|(\d{4}).*?operation glasshouse'
            matches = re.findall(pattern, content_lower, re.IGNORECASE | re.DOTALL)
            
            years_found = set()
            for match in matches:
                year = match[0] or match[1]
                if year:
                    years_found.add(year)
            
            if len(years_found) > 1:
                issues["timeline"].append(
                    f"Operation Glasshouse date inconsistency: found years {', '.join(sorted(years_found))}"
                )
        
        # Check character name consistency
        char_names = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', self.outline_content)
        name_counts = {}
        for name in char_names:
            # Check for similar names that might be typos
            base_name = name.split()[1] if len(name.split()) > 1 else name
            if base_name in name_counts:
                name_counts[base_name].append(name)
            else:
                name_counts[base_name] = [name]
        
        # Flag potential inconsistencies
        for base, variations in name_counts.items():
            if len(set(variations)) > 1:
                issues["characters"].append(f"Possible name inconsistency: {', '.join(set(variations))}")
        
        return issues
    
    def create_revision_plan(self, analysis: Dict) -> str:
        """Create a detailed revision plan based on analysis."""
        print("\nCreating outline revision plan with consistency focus...")
        
        consistency_context = ""
        if analysis.get('consistency_issues'):
            consistency_context = f"\nIDENTIFIED CONSISTENCY ISSUES:\n"
            for issue_type, issues in analysis['consistency_issues'].items():
                if issues:
                    consistency_context += f"\n{issue_type.upper()}:\n"
                    for issue in issues:
                        consistency_context += f"- {issue}\n"
        
        # Truncate analysis if too long
        analysis_text = analysis.get('analysis', '')[:10000] if analysis.get('analysis') else ''
        
        prompt = f"""Based on this outline analysis, create a detailed revision plan that PRIORITIZES fixing consistency and continuity issues:

ANALYSIS:
{analysis_text}

{consistency_context}

CURRENT OUTLINE STRUCTURE:
- Acts identified: {analysis.get('act_count', 'Unknown')}
- Chapters/scenes identified: {analysis.get('chapter_count', 'Unknown')}
- Has synopsis: {analysis.get('has_synopsis', False)}
- Has character profiles: {analysis.get('has_characters', False)}

Create a SPECIFIC revision plan that includes:

1. **CONSISTENCY FIXES (HIGHEST PRIORITY)**
   - Timeline corrections needed
   - Character name/trait standardization
   - Location/setting consistency
   - Plot logic fixes
   - Character knowledge tracking fixes
   - Technology/world rules standardization

2. **CONTINUITY IMPROVEMENTS**
   - Scene transition logic
   - Cause-and-effect chains
   - Character journey continuity
   - Information revelation order

3. **STRUCTURAL IMPROVEMENTS**
   - Specific act restructuring needed
   - Chapter/scene reordering recommendations
   - Pacing adjustments by section

4. **SCENE EXPANSION TASKS**
   List specific scenes/chapters that need:
   - Additional conflict
   - Character development moments
   - World-building details
   - Dialogue opportunities

5. **NEW SCENES TO ADD**
   - What's missing from the narrative
   - Where to insert new scenes
   - Purpose of each addition

6. **CHARACTER ARC TRACKING**
   - How to better track character growth
   - Key moments to highlight transformation
   - Relationship development milestones

7. **PRIORITY ORDER**
   Number the top 10 most important revisions, with consistency issues first

Be extremely specific with:
- What needs to be fixed
- Where the inconsistency occurs
- How to fix it
- What the corrected version should be"""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=self.MAX_TOKENS_ANALYSIS,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            plan = response.content[0].text
            
            return plan
            
        except Exception as e:
            print(f"Error creating revision plan: {e}")
            return ""
    
    def revise_outline(self, revision_type: str = "expand", 
                      revision_plan: str = None,
                      focus_areas: List[str] = None,
                      chunk_processing: bool = True) -> str:
        """Revise the outline based on type and plan."""
        
        print(f"\nRevising outline ({revision_type} mode)...")
        
        # For large outlines, process in chunks
        if chunk_processing and len(self.outline_content) > 20000:
            return self._revise_outline_chunked(revision_type, revision_plan, focus_areas)
        
        # Build focus context
        focus_context = ""
        if focus_areas:
            focus_context = f"\nFOCUS ESPECIALLY ON: {', '.join(focus_areas)}\n"
        
        # Different prompts for different revision types
        if revision_type == "expand":
            prompt = self._create_expansion_prompt(revision_plan, focus_context)
        elif revision_type == "restructure":
            prompt = self._create_restructure_prompt(revision_plan, focus_context)
        elif revision_type == "scene-detail":
            prompt = self._create_scene_detail_prompt(revision_plan, focus_context)
        elif revision_type == "consistency":
            prompt = self._create_consistency_prompt(revision_plan, focus_context)
        else:
            prompt = self._create_general_revision_prompt(revision_plan, focus_context)
        
        # Add professional formatting requirements to ALL revision types
        if not focus_areas or "no-format" not in focus_areas:
            prompt += self._add_professional_formatting_requirements()
        
        try:
            # Use appropriate token limit based on revision type
            max_tokens = self.MAX_TOKENS_LARGE if revision_type in ["expand", "scene-detail"] else self.MAX_TOKENS_STANDARD
            
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            full_response = response.content[0].text
            
            print("\n  Revision complete")
            
            # Always post-process for professional format
            if not focus_areas or "no-format" not in focus_areas:
                full_response = self.post_process_outline(full_response)
            
            return self._clean_outline(full_response)
            
        except Exception as e:
            print(f"Error revising outline: {e}")
            return self.outline_content
    
    def _revise_outline_chunked(self, revision_type: str, revision_plan: str, focus_areas: List[str]) -> str:
        """Process large outlines in chunks to avoid API limits."""
        print("  Processing large outline in chunks...")
        
        # Split outline into chunks
        chunks = self._chunk_content(self.outline_content, max_size=15000)
        revised_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"  Processing chunk {i+1}/{len(chunks)}...")
            
            # Create a mini revision for this chunk
            chunk_prompt = self._create_chunk_revision_prompt(
                chunk, revision_type, revision_plan, focus_areas, i, len(chunks)
            )
            
            try:
                def make_request():
                    return self.client.messages.create(
                        model="claude-3-5-sonnet-latest",
                        max_tokens=self.MAX_TOKENS_STANDARD,
                        messages=[{"role": "user", "content": chunk_prompt}]
                    )
                
                response = self._make_api_request_with_retry(make_request)
                revised_chunk = response.content[0].text
                revised_chunks.append(revised_chunk)
                
            except Exception as e:
                print(f"  Error processing chunk {i+1}: {e}")
                revised_chunks.append(chunk)  # Keep original if revision fails
        
        # Combine chunks
        combined = "\n\n".join(revised_chunks)
        
        # Do a final consistency pass
        return self._ensure_chunk_consistency(combined, revision_type)
    
    def _create_chunk_revision_prompt(self, chunk: str, revision_type: str, 
                                     revision_plan: str, focus_areas: List[str], 
                                     chunk_num: int, total_chunks: int) -> str:
        """Create a revision prompt for a specific chunk."""
        focus_context = ""
        if focus_areas:
            focus_context = f"\nFOCUS ESPECIALLY ON: {', '.join(focus_areas)}\n"
        
        return f"""Revise this section of a novel outline (chunk {chunk_num + 1} of {total_chunks}):

OUTLINE SECTION:
{chunk}

REVISION TYPE: {revision_type}
{focus_context}

REVISION PLAN EXCERPT:
{revision_plan[:2000] if revision_plan else "General improvement"}

IMPORTANT:
- This is part of a larger outline, maintain consistency
- Focus on the specific revision type requested
- Keep character names and key plot points consistent
- Do not add chapter numbers that might conflict with other sections

Revise this section according to the revision type and focus areas."""
    
    def _ensure_chunk_consistency(self, combined_outline: str, revision_type: str) -> str:
        """Ensure consistency across chunks after combining."""
        print("  Ensuring consistency across chunks...")
        
        # For now, just clean up the outline
        # In a more sophisticated version, this could do a consistency check
        return self._clean_outline(combined_outline)
    
    def post_process_outline(self, outline: str, ensure_professional: bool = True) -> str:
        """Post-process outline to ensure professional formatting."""
        if not ensure_professional:
            return outline
        
        # Check if outline already has professional formatting
        has_manuscript_summary = "## Manuscript Summary" in outline
        has_thematic_logline = "## Thematic Logline" in outline or "Thematic Logline" in outline
        has_dramatis_personae = "## Dramatis Personae" in outline or "Dramatis Personae" in outline
        
        # If missing key professional elements, add them
        if not all([has_manuscript_summary, has_thematic_logline, has_dramatis_personae]):
            print("  Adding professional formatting elements...")
            outline = self._ensure_professional_format(outline)
        
        return outline
    
    def _ensure_professional_format(self, outline: str) -> str:
        """Ensure outline has all professional formatting elements."""
        
        # Extract components if missing
        title = self._extract_title_from_content()
        genre = self._identify_genre()
        word_count = self._estimate_word_count_from_outline()
        
        # Build professional outline
        professional_parts = []
        
        # Add manuscript summary if missing
        if "## Manuscript Summary" not in outline:
            professional_parts.append(f"""## Manuscript Summary
**Title**: *{title}*
**Genre**: {genre}
**Word Count**: {word_count:,}
**Status**: Complete""")
        
        # Add thematic logline if missing
        if "Thematic Logline" not in outline:
            theme = self._generate_thematic_statement()
            professional_parts.append(f"## Thematic Logline\n{theme}")
        
        # Add the main outline content
        # Clean chapter headings if needed
        cleaned_outline = self._clean_chapter_headings(outline)
        professional_parts.append(cleaned_outline)
        
        # Add dramatis personae if missing
        if "Dramatis Personae" not in outline:
            dramatis = self._generate_dramatis_personae()
            if dramatis:
                professional_parts.append(dramatis)
        
        return "\n\n".join(professional_parts)
    
    def _extract_title_from_content(self) -> str:
        """Extract title from content or use default."""
        # Look for title in first few lines
        lines = self.outline_content.split('\n')[:10]
        for line in lines:
            if line.strip().startswith('#') and not line.lower().startswith('# outline'):
                return line.strip('#').strip()
        return "Untitled Novel"
    
    def _identify_genre(self) -> str:
        """Identify genre from content."""
        content = (self.outline_content + self.synopsis_content).lower()
        
        if "spy" in content or "intelligence" in content or "mi6" in content:
            return "Literary Espionage"
        elif "mystery" in content or "murder" in content:
            return "Mystery/Thriller"
        elif "historical" in content:
            return "Historical Fiction"
        
        return "Literary Fiction"
    
    def _estimate_word_count_from_outline(self) -> int:
        """Estimate word count from outline."""
        chapter_count = self._count_chapters_in_outline()
        return max(chapter_count * 4000, 80000)  # Minimum 80k for adult fiction
    
    def _generate_thematic_statement(self) -> str:
        """Generate a brief thematic statement."""
        themes = self._extract_themes()
        if "betrayal" in themes.lower() or "espionage" in self.outline_content.lower():
            return "*This novel explores how institutions built to protect society can become corrupted by the very secrecy they require, and how the truth, once buried, demands to be unearthed across generations.*"
        return f"*A literary exploration of {themes.lower()} in contemporary society.*"
    
    def _clean_chapter_headings(self, outline: str) -> str:
        """Ensure consistent chapter heading format."""
        # Replace various chapter formats with consistent ## Chapter X
        patterns = [
            (r'^#+\s*Chapter\s+(\d+)', r'## Chapter \1'),
            (r'^Chapter\s+(\d+)', r'## Chapter \1'),
            (r'^#+\s*Ch\.\s*(\d+)', r'## Chapter \1'),
            (r'^Ch\.\s*(\d+)', r'## Chapter \1')
        ]
        
        lines = outline.split('\n')
        cleaned_lines = []
        
        for line in lines:
            cleaned_line = line
            for pattern, replacement in patterns:
                if re.match(pattern, line):
                    cleaned_line = re.sub(pattern, replacement, line)
                    break
            cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)
    
    def _generate_dramatis_personae(self) -> str:
        """Generate character list from available information."""
        if not self.character_content:
            return ""
        
        # Extract character names and descriptions
        characters = []
        
        # Simple extraction based on common patterns
        lines = self.character_content.split('\n')
        current_char = None
        
        for line in lines:
            # Look for character names (usually bold or headers)
            if re.match(r'^#+\s*(.+)', line) or re.match(r'^\*\*(.+)\*\*', line):
                name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', line)
                if name_match:
                    current_char = name_match.group(1)
            elif current_char and line.strip() and len(characters) < 8:
                # Use first descriptive line as character description
                desc = line.strip()[:100]  # Limit length
                characters.append(f"**{current_char}** – {desc}")
                current_char = None
        
        if characters:
            return "## Dramatis Personae\n\n" + '\n'.join(characters[:8])  # Max 8 characters
        
        return ""
    
    def _add_professional_formatting_requirements(self) -> str:
        """Add professional formatting requirements to any revision type."""
        return """

PROFESSIONAL FORMATTING REQUIREMENTS (APPLY TO ALL OUTPUT):

1. **START WITH MANUSCRIPT SUMMARY**:
## Manuscript Summary
**Title**: *[Extract from content or use "Untitled Novel"]*
**Genre**: [Identify from content]
**Word Count**: [Estimate based on chapter count x 4000]
**Status**: Complete

2. **ADD THEMATIC LOGLINE**:
## Thematic Logline
*[2-3 sentences about what the novel explores thematically - universal themes and literary merit]*

3. **CHAPTER FORMATTING**:
- Use clear ## Chapter X or ## Chapters X-Y headings
- Group chapters if more than 20 (e.g., "Chapters 1-3: The Discovery")
- Each chapter/group summary: 3-5 sentences maximum
- Active voice: "Henry discovers", "Elena reveals", "Tom uncovers"
- Focus on plot progression, not atmosphere
- Remove ALL poetic language unless plot-critical

4. **END WITH DRAMATIS PERSONAE**:
## Dramatis Personae
[5-8 major characters only]
**[Name]** – [Role/profession], [age if relevant], [defining trait]. [One sentence about story role].

5. **PROFESSIONAL TONE**:
- Direct, clear prose
- No atmospheric descriptions
- Plot-focused summaries
- Industry-standard formatting

Apply these formatting rules to create a submission-ready outline."""
    
    def _create_consistency_prompt(self, revision_plan: str, focus_context: str) -> str:
        """Create prompt specifically for fixing consistency issues."""
        
        # Truncate content if too long
        outline_excerpt = self.outline_content[:20000] if len(self.outline_content) > 20000 else self.outline_content
        
        return f"""Fix all consistency and continuity issues in this outline:

CURRENT OUTLINE:
{outline_excerpt}

REVISION PLAN (CONSISTENCY FOCUS):
{revision_plan[:5000] if revision_plan else "Fix all consistency and continuity issues"}

SYNOPSIS (for fact-checking):
{self.synopsis_content[:3000] if self.synopsis_content else "Not provided"}

CHARACTERS (for consistency):
{self.character_content[:3000] if self.character_content else "Not provided"}

{focus_context}

CONSISTENCY REQUIREMENTS:

1. **TIMELINE CONSISTENCY**
   - Verify all dates and time references align
   - Check character ages throughout
   - Ensure event sequences are logical
   - Fix any temporal contradictions
   - CRITICAL: Operation Glasshouse MUST be 1991, not 1985

2. **CHARACTER CONSISTENCY**
   - Standardize all character names
   - Verify character traits remain consistent
   - Check relationship statuses throughout
   - Ensure character knowledge is tracked properly
   - Fix any character behavior contradictions

3. **LOCATION/SETTING CONSISTENCY**
   - Standardize location names
   - Verify geographical logic
   - Check travel times and distances
   - Ensure setting details don't contradict

4. **PLOT CONSISTENCY**
   - Verify cause-and-effect chains
   - Check that all setups have payoffs
   - Ensure no plot threads disappear
   - Fix any logical contradictions
   - Verify character motivations remain clear

5. **WORLD CONSISTENCY**
   - Technology/magic rules consistent
   - Social/cultural rules maintained
   - Physical laws respected
   - Historical facts accurate

6. **INFORMATION TRACKING**
   Create a clear tracking of:
   - Who knows what information when
   - When secrets are revealed
   - How information spreads
   - What the reader knows vs. characters

FORMAT: After each fix, add a note:
[CONSISTENCY FIX: Explanation of what was corrected]

Return the complete outline with ALL consistency issues resolved."""
    
    def _create_expansion_prompt(self, revision_plan: str, focus_context: str) -> str:
        """Create prompt for expanding outline with more detail."""
        
        # Truncate content if too long
        outline_excerpt = self.outline_content[:20000] if len(self.outline_content) > 20000 else self.outline_content
        
        return f"""Expand this outline with rich scene-level detail:

CURRENT OUTLINE:
{outline_excerpt}

REVISION PLAN:
{revision_plan[:5000] if revision_plan else "Expand all scenes with specific details"}

SYNOPSIS (for consistency):
{self.synopsis_content[:3000] if self.synopsis_content else "Not provided"}

CHARACTERS:
{self.character_content[:3000] if self.character_content else "Not provided"}

{focus_context}

EXPANSION REQUIREMENTS:

1. **MAINTAIN CONSISTENCY**
   - Keep all character names exact
   - Preserve timeline references
   - Maintain location names
   - Don't introduce contradictions

2. **For Each Chapter/Scene Add:**
   - Setting details (time, place, atmosphere)
   - Character objectives and obstacles
   - Key dialogue beats or exchanges
   - Emotional arc within scene
   - How it advances plot
   - Specific conflict/tension

3. **Scene Structure Format:**
   Chapter X: [Title]
   - Setting: [Specific location and time]
   - POV: [Character perspective]
   - Scene Goal: [What must be accomplished]
   - Conflict: [What prevents the goal]
   - Key Moments: [2-3 specific beats]
   - Outcome: [How scene ends, leading to next]
   - Character Development: [What changes]

4. **Consistency Checks:**
   - Verify character ages/states
   - Check timeline progression
   - Confirm location logistics
   - Track information flow

5. **Maintain:**
   - Original story structure
   - All existing plot points
   - Character consistency
   - Thematic elements

6. **Add:**
   - Transition notes between scenes
   - Subplot weaving points
   - Foreshadowing opportunities
   - Character relationship beats

Return the complete expanded outline with all original content enhanced."""
    
    def _create_restructure_prompt(self, revision_plan: str, focus_context: str) -> str:
        """Create prompt for restructuring outline."""
        
        # Truncate content if too long
        outline_excerpt = self.outline_content[:20000] if len(self.outline_content) > 20000 else self.outline_content
        
        return f"""Restructure this outline for better narrative flow WITHOUT adding any new story elements:

CURRENT OUTLINE:
{outline_excerpt}

REVISION PLAN:
{revision_plan[:5000] if revision_plan else "Restructure for optimal pacing and impact"}

{focus_context}

CRITICAL RESTRICTIONS:

1. **ABSOLUTELY DO NOT ADD:**
   - NO new characters
   - NO new plot events
   - NO new locations
   - NO new subplots
   - NO new backstory
   - NO new revelations not already present

2. **YOU MAY ONLY:**
   - Reorder existing scenes and chapters
   - Adjust where chapter breaks occur
   - Move existing content between acts
   - Improve transitions using existing information
   - Group related scenes together
   - Adjust pacing by repositioning content

3. **PRESERVE EXACTLY:**
   - Every character name as written
   - Every plot event as described
   - Every location mentioned
   - All dates and timeline references
   - All relationships as stated

4. **Restructuring Goals:**
   - Better sequence existing scenes
   - Group thematically related content
   - Improve dramatic build
   - Create smoother transitions
   - Position revelations for impact

Return the restructured outline using ONLY existing story elements."""
    
    def _create_scene_detail_prompt(self, revision_plan: str, focus_context: str) -> str:
        """Create prompt for adding scene-level details."""
        
        # Truncate content if too long
        outline_excerpt = self.outline_content[:20000] if len(self.outline_content) > 20000 else self.outline_content
        
        return f"""Add detailed scene breakdowns to this outline:

CURRENT OUTLINE:
{outline_excerpt}

{focus_context}

SCENE DETAIL REQUIREMENTS:

For each chapter, provide:

**Chapter [X]: [Title]**
Word Count Target: [X,000 words]

Scene 1: [Scene Title]
- Location: [Specific setting]
- Time: [When it occurs]
- POV: [Character perspective]
- Characters Present: [List]
- Scene Objective: [What must happen]
- Key Dialogue: [Important exchanges]
- Action Beats: [Physical moments]
- Emotional Beat: [Feeling shift]
- Revelation/Info: [What's learned]
- Closing: [Final moment/hook]

[Repeat for each scene in chapter]

Chapter Notes:
- Subplot threads in this chapter
- Character development moments
- Thematic elements
- Foreshadowing planted

Add this level of detail while maintaining readability."""
    
    def _create_general_revision_prompt(self, revision_plan: str, focus_context: str) -> str:
        """Create general revision prompt."""
        
        # Truncate content if too long
        outline_excerpt = self.outline_content[:20000] if len(self.outline_content) > 20000 else self.outline_content
        
        return f"""Revise this outline for clarity and effectiveness:

CURRENT OUTLINE:
{outline_excerpt}

REVISION PLAN:
{revision_plan[:5000] if revision_plan else "General improvement for clarity and impact"}

{focus_context}

REVISION GOALS:

1. **Clarity Improvements:**
   - Clear chapter/scene divisions
   - Consistent formatting
   - Logical progression
   - Remove ambiguity

2. **Story Effectiveness:**
   - Strengthen conflict in each scene
   - Clarify character motivations
   - Enhance dramatic moments
   - Improve hooks and cliffhangers

3. **Professional Format:**
   - Industry-standard structure
   - Clear act divisions
   - Proper scene headings
   - Consistent detail level

Return the revised outline."""
    
    def _clean_outline(self, text: str) -> str:
        """Clean up outline text."""
        # Remove any AI commentary
        lines = text.split('\n')
        cleaned_lines = []
        
        skip_patterns = [
            r'^note:',
            r'^comment:',
            r'^ai note:',
            r'^\[.*\]$'
        ]
        
        for line in lines:
            # Skip lines that match skip patterns
            if any(re.match(pattern, line.lower().strip()) for pattern in skip_patterns):
                continue
            cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines)
        
        # Clean up excessive spacing
        cleaned = re.sub(r'\n\s*\n\s*\n\s*\n', '\n\n\n', cleaned)
        
        return cleaned.strip()
    
    def add_character_tracking(self, outline: str) -> str:
        """Add character arc tracking to outline."""
        print("\nAdding character arc tracking...")
        
        # Process in chunks if outline is too long
        if len(outline) > 20000:
            return self._add_tracking_chunked(outline, "character")
        
        prompt = f"""Add character development tracking to this outline:

OUTLINE:
{outline[:20000]}

CHARACTERS:
{self.character_content[:3000] if self.character_content else "Not provided"}

For each act and major scene, add:

1. **Character State Tracking:**
   - Protagonist's emotional/mental state
   - Key relationships status
   - Character knowledge/beliefs
   - Skills/abilities development

2. **Arc Milestones:**
   - Where character growth occurs
   - Relationship turning points
   - Belief system challenges
   - Decision points that show change

3. **Format:**
   After each chapter/scene, add:
   [Character Note: Brief description of character state/development]

Return the outline with character tracking integrated."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=self.MAX_TOKENS_LARGE,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return self._clean_outline(response.content[0].text)
            
        except Exception as e:
            print(f"Error adding character tracking: {e}")
            return outline
    
    def add_theme_integration(self, outline: str) -> str:
        """Add thematic element tracking to outline."""
        print("\nAdding thematic integration...")
        
        # Extract themes from synopsis or outline
        themes = self._extract_themes()
        
        # Process in chunks if outline is too long
        if len(outline) > 20000:
            return self._add_tracking_chunked(outline, "theme", themes)
        
        prompt = f"""Integrate thematic elements throughout this outline:

OUTLINE:
{outline[:20000]}

THEMES IDENTIFIED:
{themes}

Add thematic integration:

1. **Symbol/Motif Placement:**
   - Where to introduce key symbols
   - How symbols evolve/transform
   - Symbolic moments/actions

2. **Thematic Scenes:**
   - Scenes that explore theme directly
   - Character discussions of theme
   - Actions that embody theme

3. **Format:**
   After relevant scenes, add:
   [Theme Note: How this scene connects to [specific theme]]

4. **Progressive Development:**
   - Show how understanding deepens
   - Track thematic questions
   - Build to thematic climax

Return outline with thematic elements woven throughout."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=self.MAX_TOKENS_LARGE,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return self._clean_outline(response.content[0].text)
            
        except Exception as e:
            print(f"Error adding theme integration: {e}")
            return outline
    
    def _add_tracking_chunked(self, outline: str, tracking_type: str, themes: str = None) -> str:
        """Add tracking to outline in chunks to avoid API limits."""
        chunks = self._chunk_content(outline, max_size=15000)
        tracked_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"  Processing chunk {i+1}/{len(chunks)} for {tracking_type} tracking...")
            
            if tracking_type == "character":
                prompt = f"""Add character tracking to this outline section:
{chunk}

Add [Character Note: ...] annotations after key scenes."""
            else:  # theme
                prompt = f"""Add theme tracking to this outline section:
{chunk}

THEMES: {themes}

Add [Theme Note: ...] annotations after relevant scenes."""
            
            try:
                def make_request():
                    return self.client.messages.create(
                        model="claude-3-5-sonnet-latest",
                        max_tokens=self.MAX_TOKENS_STANDARD,
                        messages=[{"role": "user", "content": prompt}]
                    )
                
                response = self._make_api_request_with_retry(make_request)
                tracked_chunks.append(response.content[0].text)
                
            except Exception as e:
                print(f"  Error processing chunk {i+1}: {e}")
                tracked_chunks.append(chunk)
        
        return "\n\n".join(tracked_chunks)
    
    def _extract_themes(self) -> str:
        """Extract themes from available content."""
        content = self.synopsis_content + "\n" + self.outline_content
        
        # Look for explicit theme mentions
        theme_pattern = r'[Tt]heme[s]?:([^\n]+)'
        matches = re.findall(theme_pattern, content)
        
        if matches:
            return "\n".join(matches)
        
        # Common theme keywords to search for
        theme_keywords = [
            'identity', 'betrayal', 'loyalty', 'love', 'power',
            'redemption', 'sacrifice', 'truth', 'family', 'duty',
            'freedom', 'justice', 'survival', 'corruption'
        ]
        
        found_themes = []
        content_lower = content.lower()
        
        for keyword in theme_keywords:
            if keyword in content_lower:
                found_themes.append(keyword.capitalize())
        
        return ", ".join(found_themes) if found_themes else "Identity, Truth, Moral Ambiguity"
    
    def check_detailed_consistency(self, outline: str = None) -> Dict[str, Any]:
        """Perform detailed consistency check on outline."""
        if not outline:
            outline = self.outline_content
            
        print("\nPerforming detailed consistency check...")
        
        # Truncate if too long
        outline_excerpt = outline[:20000] if len(outline) > 20000 else outline
        
        prompt = f"""Perform a comprehensive consistency check on this outline:

OUTLINE:
{outline_excerpt}

SYNOPSIS (for cross-reference):
{self.synopsis_content[:3000] if self.synopsis_content else "Not provided"}

CHARACTERS (for verification):
{self.character_content[:3000] if self.character_content else "Not provided"}

Check for ALL of the following:

1. **TIMELINE CONSISTENCY**
   - List all time references chronologically
   - Identify any contradictions
   - Check character ages at each point
   - Verify event sequence logic

2. **CHARACTER CONSISTENCY**
   - Track each character's name variations
   - Check personality traits
   - Verify relationships
   - Track knowledge/beliefs
   - Flag any contradictions

3. **LOCATION CONSISTENCY**
   - Map all locations mentioned
   - Check travel times/distances
   - Verify geography makes sense

4. **PLOT LOGIC**
   - Verify cause precedes effect
   - Check all setups have payoffs
   - Ensure no threads vanish
   - Validate character motivations

5. **INFORMATION FLOW**
   - Track what each character knows
   - When they learn it
   - How information spreads

Format output as:
## Consistency Report
### Issues Found:
[List each issue with location]

### Recommended Fixes:
[Specific solutions]

### Consistency Score: X/10"""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=self.MAX_TOKENS_ANALYSIS,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            report = response.content[0].text
            
            # Save consistency report
            report_path = os.path.join(self.project_dir, "outline_consistency_report.md")
            self._safe_write_file(report_path, report)
            print(f"Consistency report saved to: outline_consistency_report.md")
            
            return {"report": report, "saved_to": report_path}
            
        except Exception as e:
            print(f"Error checking consistency: {e}")
            return {"error": str(e)}
    
    def format_for_submission(self, outline: str, title: str = None, 
                            word_count: int = None, status: str = "Complete") -> str:
        """Format outline for professional agent submission."""
        print("\nFormatting outline for agent submission...")
        
        # Extract key information if not provided
        if not title:
            title = self._suggest_title()
        
        if not word_count:
            word_count = self._estimate_word_count()
        
        # Create dramatis personae
        dramatis_personae = self._create_character_summary()
        
        # Extract themes for thematic statement
        thematic_statement = self._create_thematic_statement()
        
        prompt = f"""Format this outline for professional agent submission:

CURRENT OUTLINE:
{outline[:20000]}

TITLE: {title}
WORD COUNT: {word_count:,}
STATUS: {status}

SYNOPSIS:
{self.synopsis_content[:3000] if self.synopsis_content else "Not provided"}

CHARACTERS:
{self.character_content[:3000] if self.character_content else "Not provided"}

FORMAT REQUIREMENTS:

1. **MANUSCRIPT SUMMARY BLOCK**
Create professional header:
## Manuscript Summary
**Title**: *{title}*
**Genre**: [Identify from content]
**Word Count**: {word_count:,}
**Status**: {status}

2. **THEMATIC LOGLINE**
Write a compelling 2-3 sentence thematic statement that positions the work's deeper meaning.

3. **OUTLINE FORMATTING**
- Use clear ## Chapter X headings
- Remove overly poetic descriptions
- Tighten prose to narrative beats
- Use active voice: "Henry discovers", "Elena reveals"
- Focus on plot progression
- Group early chapters if beneficial (e.g., "Chapters 1-3: The Discovery")

4. **CHAPTER SUMMARIES**
- Keep to 3-5 sentences per chapter
- Focus on: What happens, who's involved, what changes
- Remove atmospheric details unless plot-critical
- Maintain professional but engaging tone

5. **DRAMATIS PERSONAE**
Create character list with format:
**[Name]** – [Role/profession], [key trait]. [One sentence backstory/motivation].

6. **CONSISTENCY**
- Ensure all character names match throughout
- Verify timeline references align
- Check location continuity

Return the professionally formatted outline ready for agent submission."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=self.MAX_TOKENS_STANDARD,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            formatted = response.content[0].text
            
            # Add dramatis personae if not included
            if dramatis_personae and "dramatis personae" not in formatted.lower():
                formatted = formatted + "\n\n---\n\n" + dramatis_personae
            
            return self._clean_outline(formatted)
            
        except Exception as e:
            print(f"Error formatting for submission: {e}")
            return outline
    
    def _suggest_title(self) -> str:
        """Suggest a title based on outline content."""
        prompt = f"""Based on this outline, suggest a compelling title:

OUTLINE EXCERPT:
{self.outline_content[:2000]}...

SYNOPSIS:
{self.synopsis_content[:1000] if self.synopsis_content else "Not provided"}

Suggest 5 possible titles that:
- Capture the essence of the story
- Work for the genre
- Are memorable and marketable
- Avoid clichés

Return ONLY the best title, no explanation."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=100,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return response.content[0].text.strip().strip('*').strip('"')
            
        except Exception as e:
            return "Untitled Novel"
    
    def _estimate_word_count(self) -> int:
        """Estimate final word count based on outline."""
        chapter_count = self._count_chapters_in_outline()
        if chapter_count > 0:
            # Typical chapter length 3000-5000 words for literary fiction
            return chapter_count * 4000
        return 90000  # Default for literary novel
    
    def _create_character_summary(self) -> str:
        """Create dramatis personae from character information."""
        if not self.character_content:
            return ""
        
        prompt = f"""Create a professional dramatis personae (character list) from this information:

CHARACTERS:
{self.character_content[:3000]}

OUTLINE CONTEXT:
{self.outline_content[:2000]}...

Format each character as:
**[Full Name]** – [Role/profession], [defining trait]. [One sentence about their role in the story].

Include only major characters (5-8 maximum).
Order by importance to the story.
Keep descriptions concise and plot-relevant.

Example:
**Henry Millbank** – Retired MI6 officer, haunted by past failures. Drawn back into espionage when a decades-old operation resurfaces.

Return ONLY the formatted character list."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return "## Dramatis Personae\n\n" + response.content[0].text.strip()
            
        except Exception as e:
            return ""
    
    def _create_thematic_statement(self) -> str:
        """Create a thematic statement for the work."""
        themes = self._extract_themes()
        
        prompt = f"""Write a compelling thematic logline for this novel:

THEMES IDENTIFIED: {themes}

SYNOPSIS:
{self.synopsis_content[:1500] if self.synopsis_content else "Not provided"}

OUTLINE EXCERPT:
{self.outline_content[:1500]}...

Write a 2-3 sentence thematic statement that:
- Positions the work's deeper meaning
- Shows literary merit
- Connects personal and universal themes
- Avoids clichés

Format as a single paragraph, italicized.
Focus on what the novel explores about the human condition.

Return ONLY the thematic statement."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return response.content[0].text.strip()
            
        except Exception as e:
            return ""
    
    def condense_outline_chapters(self, outline: str, group_size: int = 3) -> str:
        """Condense outline by grouping chapters."""
        print(f"\nCondensing outline (grouping {group_size} chapters)...")
        
        prompt = f"""Condense this outline by grouping chapters for easier readability:

OUTLINE:
{outline[:20000]}

REQUIREMENTS:
1. Group every {group_size} chapters into single entries
2. Title each group based on its narrative arc
3. Summarize the key progression across grouped chapters
4. Maintain all crucial plot points
5. Keep character development clear
6. Preserve story momentum

Format:
## Chapters X-Y: [Arc Title]
[Concise summary of what happens across these chapters]

Return the condensed outline."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=20000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return self._clean_outline(response.content[0].text)
            
        except Exception as e:
            print(f"Error condensing outline: {e}")
            return outline
    
    def tighten_prose(self, outline: str) -> str:
        """Tighten prose for professional submission."""
        print("\nTightening prose for submission...")
        
        prompt = f"""Tighten this outline's prose for agent submission:

OUTLINE:
{outline[:20000]}

REQUIREMENTS:
1. Remove poetic/atmospheric descriptions unless plot-critical
2. Use active voice: "Henry discovers", "Elena reveals", "Tom uncovers"
3. Focus on narrative beats: what happens, who acts, what changes
4. Cut redundant phrases
5. Maintain professional but engaging tone
6. Keep chapter summaries to 3-5 sentences
7. Preserve all plot information

Example transformation:
BEFORE: "The morning mist clings to Cambridge's ancient spires as Henry, lost in memories of Prague winters, discovers a note that will shatter his carefully constructed retirement."
AFTER: "Henry discovers a coded note in a library book that references Operation Glasshouse, the failed mission that haunts him."

Return the tightened outline."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=self.MAX_TOKENS_STANDARD,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return self._clean_outline(response.content[0].text)
            
        except Exception as e:
            print(f"Error tightening prose: {e}")
            return outline
    
    def generate_comparison(self, original: str, revised: str) -> str:
        """Generate a comparison report between original and revised outlines."""
        
        prompt = f"""Compare these two outline versions:

ORIGINAL (excerpt):
{original[:3000]}...

REVISED (excerpt):
{revised[:3000]}...

Analyze:
1. **Structural improvements made**
2. **Enhanced detail level**
3. **Better character integration**
4. **Improved pacing**
5. **Clearer scene objectives**
6. **Overall effectiveness gain**

Provide specific examples of improvements."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=5000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return response.content[0].text
            
        except Exception as e:
            return f"Comparison analysis failed: {e}"
    
    def save_outline(self, outline: str, filename: str = None, revision_type: str = "") -> str:
        """Save revised outline to file."""
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = f"_{revision_type}" if revision_type else ""
            filename = f"outline_revised{suffix}_{timestamp}.md"
        
        output_path = os.path.join(self.project_dir, filename)
        
        # Create formatted content
        content = f"""# Revised Outline

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Revision Type:** {revision_type or 'General'}
**Generator:** AI Outline Reviser v1.0

---

{outline}

---

*This outline was revised using AI assistance for improved structure and detail.*
"""
        
        if self._safe_write_file(output_path, content):
            print(f"Outline saved to: {filename}")
            return output_path
        else:
            print("Failed to save outline")
            return ""
    
    def generate_revision_report(self, analysis: Dict, revision_plan: str, 
                               original_outline: str, revised_outline: str,
                               revision_type: str) -> str:
        """Generate a comprehensive revision report."""
        
        # Calculate metrics
        original_lines = len(original_outline.split('\n'))
        revised_lines = len(revised_outline.split('\n'))
        original_words = len(original_outline.split())
        revised_words = len(revised_outline.split())
        
        # Get comparison
        comparison = self.generate_comparison(original_outline, revised_outline)
        
        report = f"""# Outline Revision Report

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Revision Type:** {revision_type}
**Project:** {os.path.basename(self.project_dir)}

---

## Metrics

| Metric | Original | Revised | Change |
|--------|----------|---------|--------|
| Lines | {original_lines} | {revised_lines} | {revised_lines - original_lines:+d} |
| Words | {original_words:,} | {revised_words:,} | {revised_words - original_words:+,} |
| Detail Level | Basic | {"Expanded" if revision_type == "expand" else "Enhanced"} | Improved |

---

## Analysis Summary

{analysis.get('analysis', 'No analysis available')[:1500]}...

---

## Revision Plan Summary

{revision_plan[:1500]}...

---

## Comparison Analysis

{comparison}

---

## Files Generated

1. `{os.path.basename(self.project_dir)}/outline_analysis.md` - Detailed structural analysis
2. `{os.path.basename(self.project_dir)}/outline_revision_plan.md` - Specific revision recommendations  
3. `{os.path.basename(self.project_dir)}/outline_revised_[timestamp].md` - The revised outline
4. `{os.path.basename(self.project_dir)}/outline_revision_report.md` - This summary report

---

## Next Steps

1. Review the revised outline for accuracy
2. Verify character arcs are properly tracked
3. Ensure all plot points are covered
4. Check pacing and chapter balance
5. Validate against synopsis for consistency

---

*Report generated by AI Outline Reviser v1.0*
"""
        
        # Save report
        report_path = os.path.join(self.project_dir, "outline_revision_report.md")
        self._safe_write_file(report_path, report)
        
        return report

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="AI-Powered Novel Outline Reviser",
        epilog="""
Examples:
  # Basic outline expansion
  python outline_reviser.py glasshouse
  
  # Fix consistency issues
  python outline_reviser.py glasshouse --type consistency
  
  # Restructure for better pacing
  python outline_reviser.py glasshouse --type restructure
  
  # Add detailed scene breakdowns
  python outline_reviser.py glasshouse --type scene-detail
  
  # Focus on specific areas
  python outline_reviser.py glasshouse --focus "character arcs,pacing"
  
  # Add character and theme tracking
  python outline_reviser.py glasshouse --add-tracking
  
  # Format for agent submission
  python outline_reviser.py glasshouse --format-submission --title "The Orpheus Protocol"
  
  # Full submission prep
  python outline_reviser.py glasshouse --format-submission --condense 3 --tighten-prose
  
  # Just analyze without revising
  python outline_reviser.py glasshouse --analyze-only
  
  # Perform consistency check
  python outline_reviser.py glasshouse --consistency-check --analyze-only
        """
    )
    
    parser.add_argument(
        "project_dir",
        help="Novel project directory containing outline.md"
    )
    parser.add_argument(
        "--type",
        choices=["expand", "restructure", "scene-detail", "consistency", "general"],
        default="expand",
        help="Type of revision (default: expand)"
    )
    parser.add_argument(
        "--chapters",
        type=str,
        help="Comma-separated chapter numbers to analyze (e.g., '1,2,3')"
    )
    parser.add_argument(
        "--focus",
        type=str,
        help="Focus areas for revision (e.g., 'character arcs,pacing,conflict')"
    )
    parser.add_argument(
        "--add-tracking",
        action="store_true",
        help="Add character arc and theme tracking"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze outline without revising"
    )
    parser.add_argument(
        "--consistency-check",
        action="store_true",
        help="Perform detailed consistency check"
    )
    parser.add_argument(
        "--output",
        help="Output filename (default: outline_revised_[timestamp].md)"
    )
    parser.add_argument(
        "--format-submission",
        action="store_true",
        help="Format outline for agent submission"
    )
    parser.add_argument(
        "--title",
        help="Novel title (for submission formatting)"
    )
    parser.add_argument(
        "--word-count",
        type=int,
        help="Target word count (for submission formatting)"
    )
    parser.add_argument(
        "--condense",
        type=int,
        metavar="N",
        help="Condense outline by grouping N chapters together"
    )
    parser.add_argument(
        "--tighten-prose",
        action="store_true",
        help="Tighten prose for professional submission"
    )
    parser.add_argument(
        "--no-format",
        action="store_true",
        help="Skip professional formatting (use raw revision output)"
    )
    
    args = parser.parse_args()
    
    # Set console encoding for Windows
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass
    
    # Parse chapters if provided
    chapters_to_analyze = None
    if args.chapters:
        try:
            chapters_to_analyze = [int(x.strip()) for x in args.chapters.split(',')]
        except ValueError:
            print("Error: Invalid chapters format. Use comma-separated numbers like '1,2,3'")
            return 1
    
    # Parse focus areas
    focus_areas = None
    if args.focus:
        focus_areas = [x.strip() for x in args.focus.split(',')]
    
    # Add no-format to focus areas if requested
    if args.no_format and focus_areas:
        focus_areas.append("no-format")
    elif args.no_format:
        focus_areas = ["no-format"]
    
    # Initialize reviser
    try:
        reviser = AIOutlineReviser()
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        # Load project
        reviser.load_project(args.project_dir, chapters_to_analyze)
        
        # Analyze outline structure
        analysis = reviser.analyze_outline_structure()
        
        # Save analysis
        analysis_path = os.path.join(args.project_dir, "outline_analysis.md")
        reviser._safe_write_file(analysis_path, analysis.get('analysis', 'No analysis'))
        print(f"Analysis saved to: outline_analysis.md")
        
        if args.analyze_only:
            print("\nOutline Analysis Complete")
            print("="*50)
            print(f"Acts found: {analysis.get('act_count', 'Unknown')}")
            print(f"Chapters/scenes found: {analysis.get('chapter_count', 'Unknown')}")
            print(f"See outline_analysis.md for detailed analysis")
            
            # Add consistency check option
            if args.consistency_check:
                print("\nPerforming consistency check...")
                consistency_report = reviser.check_detailed_consistency()
                print(f"Consistency report saved to: outline_consistency_report.md")
            
            return 0
        
        # Create revision plan
        revision_plan = reviser.create_revision_plan(analysis)
        
        # Save revision plan
        plan_path = os.path.join(args.project_dir, "outline_revision_plan.md")
        reviser._safe_write_file(plan_path, revision_plan)
        print(f"Revision plan saved to: outline_revision_plan.md")
        
        # Revise outline
        print(f"\nStarting {args.type} revision...")
        revised_outline = reviser.revise_outline(
            revision_type=args.type,
            revision_plan=revision_plan,
            focus_areas=focus_areas
        )
        
        # Add tracking if requested
        if args.add_tracking:
            print("\nAdding tracking elements...")
            revised_outline = reviser.add_character_tracking(revised_outline)
            revised_outline = reviser.add_theme_integration(revised_outline)
        
        # Handle submission formatting
        if args.format_submission:
            print("\nFormatting for submission...")
            revised_outline = reviser.format_for_submission(
                revised_outline, 
                title=args.title,
                word_count=args.word_count
            )
        
        # Condense if requested
        if args.condense:
            print(f"\nCondensing outline (grouping {args.condense} chapters)...")
            revised_outline = reviser.condense_outline_chapters(revised_outline, args.condense)
        
        # Tighten prose if requested
        if args.tighten_prose:
            print("\nTightening prose...")
            revised_outline = reviser.tighten_prose(revised_outline)
        
        # Save revised outline
        output_path = reviser.save_outline(
            revised_outline,
            args.output,
            args.type
        )
        
        # Generate report
        report = reviser.generate_revision_report(
            analysis,
            revision_plan,
            reviser.outline_content,
            revised_outline,
            args.type
        )
        
        print("\nOutline Revision Complete")
        print("="*50)
        print(f"Revision type: {args.type}")
        print(f"Original words: {len(reviser.outline_content.split()):,}")
        print(f"Revised words: {len(revised_outline.split()):,}")
        print(f"Professional formatting: {'Applied' if args.format_submission else ('Skipped' if args.no_format else 'Standard')}")
        print(f"Files created:")
        print(f"  - outline_analysis.md")
        print(f"  - outline_revision_plan.md")
        print(f"  - {os.path.basename(output_path)}")
        print(f"  - outline_revision_report.md")
        
        return 0
        
    except Exception as e:
        print(f"Error during outline revision: {e}")
        return 1

if __name__ == "__main__":
    exit(main())