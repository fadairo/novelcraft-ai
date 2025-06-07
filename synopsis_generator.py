#!/usr/bin/env python3
"""
ai_synopsis_generator.py - AI-Powered Novel Synopsis Generator

This script uses Claude API to generate optimized novel synopses following
Curtis Brown Creative guidelines. It analyzes existing synopsis, outline,
and optional chapters to craft compelling, professional synopses.

Features:
- Analyzes existing synopsis and outline
- Follows industry best practices for synopsis writing
- Supports multiple synopsis lengths (short/medium/full)
- Integrates character and thematic analysis
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

class AISynopsisGenerator:
    """AI-powered synopsis generator using Claude API."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.project_dir = None
        self.synopsis_content = ""
        self.outline_content = ""
        self.character_content = ""
        self.chapters = {}
        
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
                if "overloaded" in error_str and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    print(f"API overloaded, waiting {wait_time:.1f} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
        
        raise Exception("Max retries exceeded")
    
    def load_project(self, project_dir: str, chapters_to_analyze: List[int] = None):
        """Load project files including synopsis, outline, and optional chapters."""
        self.project_dir = project_dir
        print(f"Loading project from: {project_dir}")
        
        # Load synopsis
        synopsis_files = ['synopsis.md', 'synopsis.txt']
        for fname in synopsis_files:
            fpath = os.path.join(project_dir, fname)
            if os.path.exists(fpath):
                self.synopsis_content = self._safe_read_file(fpath)
                print(f"  Found synopsis: {fname}")
                break
        
        if not self.synopsis_content:
            print("  Warning: No synopsis file found")
        
        # Load outline
        outline_files = ['outline.md', 'outline.txt', 'Outline.md', 'Outline.txt']
        for fname in outline_files:
            fpath = os.path.join(project_dir, fname)
            if os.path.exists(fpath):
                self.outline_content = self._safe_read_file(fpath)
                print(f"  Found outline: {fname}")
                break
        
        if not self.outline_content:
            raise ValueError("No outline file found - outline is required")
        
        # Load character file if available
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
    
    def analyze_existing_synopsis(self) -> Dict[str, Any]:
        """Analyze the existing synopsis for strengths and weaknesses."""
        if not self.synopsis_content:
            return {"has_synopsis": False}
        
        print("\nAnalyzing existing synopsis...")
        
        prompt = f"""Analyze this existing synopsis according to Curtis Brown Creative guidelines:

SYNOPSIS:
{self.synopsis_content}

Evaluate:
1. **Hook effectiveness** - Does it grab attention immediately?
2. **Character introduction** - Is the protagonist compelling with clear stakes?
3. **Central conflict clarity** - Is the main conflict clear and engaging?
4. **Plot progression** - Does it focus on main plot without subplots?
5. **Ending reveal** - Is the ending clearly stated?
6. **Theme integration** - Are themes naturally woven in?
7. **Prose quality** - Is it clear, engaging, and professional?
8. **Length appropriateness** - Is it the right length (typically 500-800 words)?

Provide specific strengths and areas for improvement."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=5000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            analysis = response.content[0].text
            
            return {
                "has_synopsis": True,
                "analysis": analysis,
                "original_length": len(self.synopsis_content.split())
            }
            
        except Exception as e:
            print(f"Error analyzing synopsis: {e}")
            return {"has_synopsis": True, "error": str(e)}
    
    def extract_key_elements(self) -> Dict[str, Any]:
        """Extract key story elements from outline and chapters."""
        print("\nExtracting key story elements...")
        
        chapters_text = ""
        if self.chapters:
            chapters_text = "\n\nSAMPLE CHAPTERS:\n"
            for num, content in sorted(self.chapters.items()):
                # Include first 1000 words of each chapter
                excerpt = ' '.join(content.split()[:1000])
                chapters_text += f"\nChapter {num} excerpt:\n{excerpt}...\n"
        
        prompt = f"""Extract key story elements for synopsis writing:

OUTLINE:
{self.outline_content}

CHARACTERS:
{self.character_content if self.character_content else "Not provided"}

{chapters_text}

Extract and organize:

1. **PROTAGONIST**
   - Name and defining characteristics
   - Core motivation/goal
   - What's at stake for them personally

2. **CENTRAL CONFLICT**
   - Main antagonistic force
   - Core dramatic question
   - Stakes if protagonist fails

3. **KEY PLOT POINTS**
   - Inciting incident (specific)
   - 3-4 major turning points
   - Climax
   - Resolution

4. **THEMES**
   - Primary theme
   - Secondary themes (max 2)
   - How themes connect to plot

5. **SETTING**
   - Time period
   - Location(s)
   - How setting impacts story

6. **GENRE/TONE**
   - Primary genre
   - Tone/mood
   - Comparable titles (if apparent)

Be specific and extract actual details, not generic descriptions."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            elements = response.content[0].text
            
            return {"elements": elements, "success": True}
            
        except Exception as e:
            print(f"Error extracting elements: {e}")
            return {"elements": "", "success": False, "error": str(e)}
    
    def generate_synopsis(self, length_type: str = "standard", 
                         existing_analysis: Dict = None,
                         key_elements: Dict = None) -> str:
        """Generate a new synopsis following best practices."""
        
        # Define word count targets
        word_targets = {
            "short": 300,
            "standard": 500,
            "full": 800
        }
        
        target_words = word_targets.get(length_type, 500)
        
        print(f"\nGenerating {length_type} synopsis (~{target_words} words)...")
        
        # Build context from analysis
        analysis_context = ""
        if existing_analysis and existing_analysis.get("has_synopsis"):
            analysis_context = f"""
EXISTING SYNOPSIS ANALYSIS:
{existing_analysis.get('analysis', '')}

The new synopsis should address the weaknesses identified while maintaining the strengths.
"""
        
        elements_context = ""
        if key_elements and key_elements.get("success"):
            elements_context = f"""
KEY STORY ELEMENTS:
{key_elements.get('elements', '')}
"""
        
        prompt = f"""Write a compelling novel synopsis following Curtis Brown Creative guidelines.

{analysis_context}

{elements_context}

OUTLINE:
{self.outline_content}

CHARACTERS:
{self.character_content if self.character_content else "Not provided"}

SYNOPSIS REQUIREMENTS:

1. **Opening Hook** (1-2 sentences)
   - Start with intrigue or compelling situation
   - Establish genre/tone immediately
   - No clichés or generic openings

2. **Protagonist Introduction** (2-3 sentences)
   - Name and essential characteristics
   - Clear personal stakes
   - Why we should care about them

3. **Central Conflict** (2-3 sentences)
   - What kicks off the story (inciting incident)
   - Main antagonistic force/obstacle
   - What the protagonist must do

4. **Plot Development** (main body)
   - Focus ONLY on main plot line
   - Show cause and effect progression
   - Include 3-4 major turning points
   - Build tension toward climax

5. **Climax and Resolution** (2-3 sentences)
   - Reveal how story climaxes
   - State the ending clearly
   - Show protagonist's transformation

6. **Style Guidelines**
   - Present tense throughout
   - Third person
   - Clear, engaging prose
   - No rhetorical questions
   - No subplots or minor characters
   - Natural theme integration

TARGET LENGTH: {target_words} words (be precise)

Write the synopsis now:"""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=5000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            synopsis = response.content[0].text
            
            # Clean up any AI artifacts
            synopsis = self._clean_synopsis(synopsis)
            
            return synopsis
            
        except Exception as e:
            print(f"Error generating synopsis: {e}")
            return ""
    
    def _clean_synopsis(self, text: str) -> str:
        """Clean up synopsis text."""
        # Remove any markdown headers
        text = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE)
        
        # Remove any instructional text
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip lines that look like instructions or headers
            if any(marker in line.lower() for marker in ['synopsis:', 'word count:', 'note:', 'title:']):
                continue
            cleaned_lines.append(line)
        
        # Join and clean up spacing
        cleaned = '\n'.join(cleaned_lines)
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
        
        return cleaned.strip()
    
    def refine_synopsis(self, synopsis: str, specific_feedback: str = None) -> str:
        """Refine a generated synopsis based on feedback."""
        print("\nRefining synopsis...")
        
        feedback_context = ""
        if specific_feedback:
            feedback_context = f"\nSPECIFIC FEEDBACK TO ADDRESS:\n{specific_feedback}\n"
        
        prompt = f"""Refine this synopsis to make it even more compelling:

CURRENT SYNOPSIS:
{synopsis}

{feedback_context}

REFINEMENT GOALS:
1. Strengthen the opening hook
2. Clarify protagonist motivation and stakes
3. Tighten prose for maximum impact
4. Ensure smooth flow between paragraphs
5. Verify all major plot points are clear
6. Polish language for professional submission

Maintain the same length and all key information. Return only the refined synopsis."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=5000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            refined = response.content[0].text
            
            return self._clean_synopsis(refined)
            
        except Exception as e:
            print(f"Error refining synopsis: {e}")
            return synopsis
    
    def generate_multiple_versions(self, count: int = 3) -> List[Dict[str, str]]:
        """Generate multiple synopsis versions for comparison."""
        print(f"\nGenerating {count} synopsis versions...")
        
        versions = []
        styles = ["dramatic", "character-focused", "mystery-emphasis"]
        
        for i in range(min(count, len(styles))):
            style = styles[i]
            print(f"  Generating {style} version...")
            
            # Extract elements once
            if i == 0:
                elements = self.extract_key_elements()
            
            # Generate with style variation
            synopsis = self._generate_styled_synopsis(style, elements)
            
            if synopsis:
                versions.append({
                    "style": style,
                    "synopsis": synopsis,
                    "word_count": len(synopsis.split())
                })
        
        return versions
    
    def _generate_styled_synopsis(self, style: str, elements: Dict) -> str:
        """Generate synopsis with specific style emphasis."""
        
        style_instructions = {
            "dramatic": "Emphasize high stakes, tension, and dramatic moments. Start with action or danger.",
            "character-focused": "Lead with character depth and emotional journey. Emphasize internal conflict.",
            "mystery-emphasis": "Create intrigue and questions. Build suspense about what will be revealed."
        }
        
        instruction = style_instructions.get(style, "Write in a compelling, professional style.")
        
        prompt = f"""Write a {style} synopsis with this emphasis: {instruction}

KEY ELEMENTS:
{elements.get('elements', '')}

OUTLINE:
{self.outline_content}

Requirements:
- 500 words
- Follow Curtis Brown Creative guidelines
- {instruction}
- Include all major plot points
- Reveal the ending

Write the synopsis:"""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=5000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return self._clean_synopsis(response.content[0].text)
            
        except Exception as e:
            print(f"Error generating {style} synopsis: {e}")
            return ""
    
    def save_synopsis(self, synopsis: str, filename: str = None) -> str:
        """Save synopsis to file."""
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"synopsis_generated_{timestamp}.md"
        
        output_path = os.path.join(self.project_dir, filename)
        
        # Create formatted content
        word_count = len(synopsis.split())
        content = f"""# Generated Synopsis

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Word Count:** {word_count}
**Generator:** AI Synopsis Generator v1.0

---

{synopsis}

---

*This synopsis was generated following Curtis Brown Creative guidelines for professional submission.*
"""
        
        if self._safe_write_file(output_path, content):
            print(f"Synopsis saved to: {filename}")
            return output_path
        else:
            print("Failed to save synopsis")
            return ""
    
    def generate_comparison_report(self, versions: List[Dict[str, str]]) -> str:
        """Generate a comparison report for multiple synopsis versions."""
        
        report = f"""# Synopsis Comparison Report

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Versions Generated:** {len(versions)}

---

## Synopsis Versions

"""
        
        for i, version in enumerate(versions, 1):
            report += f"""### Version {i}: {version['style'].title()}

**Word Count:** {version['word_count']}

{version['synopsis']}

---

"""
        
        # Add AI comparison
        if len(versions) > 1:
            comparison = self._compare_versions(versions)
            report += f"""## AI Analysis

{comparison}
"""
        
        # Save report
        report_path = os.path.join(self.project_dir, "synopsis_comparison_report.md")
        self._safe_write_file(report_path, report)
        
        return report
    
    def _compare_versions(self, versions: List[Dict[str, str]]) -> str:
        """Compare multiple synopsis versions."""
        
        versions_text = ""
        for i, v in enumerate(versions, 1):
            versions_text += f"\nVERSION {i} ({v['style']}):\n{v['synopsis']}\n"
        
        prompt = f"""Compare these synopsis versions and recommend the best one:

{versions_text}

Analyze:
1. Which has the strongest hook?
2. Which best clarifies the central conflict?
3. Which maintains best pacing?
4. Which would be most compelling to agents/publishers?

Provide specific reasoning for your recommendation."""

        try:
            def make_request():
                return self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=3000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            return response.content[0].text
            
        except Exception as e:
            return f"Comparison analysis failed: {e}"

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="AI-Powered Novel Synopsis Generator",
        epilog="""
Examples:
  # Generate standard synopsis
  python ai_synopsis_generator.py glasshouse
  
  # Generate short synopsis with chapter analysis
  python ai_synopsis_generator.py glasshouse --length short --chapters 1,2,3
  
  # Generate multiple versions for comparison
  python ai_synopsis_generator.py glasshouse --versions 3
  
  # Analyze existing synopsis only
  python ai_synopsis_generator.py glasshouse --analyze-only
        """
    )
    
    parser.add_argument(
        "project_dir",
        help="Novel project directory containing synopsis.md and outline.md"
    )
    parser.add_argument(
        "--length",
        choices=["short", "standard", "full"],
        default="standard",
        help="Synopsis length (default: standard ~500 words)"
    )
    parser.add_argument(
        "--chapters",
        type=str,
        help="Comma-separated chapter numbers to analyze (e.g., '1,2,3')"
    )
    parser.add_argument(
        "--versions",
        type=int,
        help="Generate multiple versions for comparison"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze existing synopsis without generating new one"
    )
    parser.add_argument(
        "--output",
        help="Output filename (default: synopsis_generated_[timestamp].md)"
    )
    parser.add_argument(
        "--feedback",
        help="Specific feedback to address in refinement"
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
    
    # Initialize generator
    try:
        generator = AISynopsisGenerator()
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        # Load project
        generator.load_project(args.project_dir, chapters_to_analyze)
        
        # Analyze existing synopsis
        existing_analysis = generator.analyze_existing_synopsis()
        
        if args.analyze_only:
            print("\nSynopsis Analysis Complete")
            print("="*50)
            if existing_analysis.get("has_synopsis"):
                print(existing_analysis.get("analysis", "No analysis available"))
            else:
                print("No existing synopsis found to analyze")
            return 0
        
        # Extract key elements
        key_elements = generator.extract_key_elements()
        
        if args.versions:
            # Generate multiple versions
            versions = generator.generate_multiple_versions(args.versions)
            
            if versions:
                # Generate comparison report
                report = generator.generate_comparison_report(versions)
                print("\nGenerated Synopsis Versions")
                print("="*50)
                print(f"Created {len(versions)} versions")
                print("See synopsis_comparison_report.md for full comparison")
                
                # Save best version
                if versions:
                    best = versions[0]  # Could be enhanced with AI selection
                    generator.save_synopsis(best["synopsis"], args.output)
            
        else:
            # Generate single synopsis
            synopsis = generator.generate_synopsis(
                args.length,
                existing_analysis,
                key_elements
            )
            
            if synopsis and args.feedback:
                # Refine based on feedback
                synopsis = generator.refine_synopsis(synopsis, args.feedback)
            
            if synopsis:
                # Save synopsis
                output_path = generator.save_synopsis(synopsis, args.output)
                
                word_count = len(synopsis.split())
                print("\nSynopsis Generation Complete")
                print("="*50)
                print(f"Word count: {word_count}")
                print(f"Saved to: {output_path}")
                print("\nFirst paragraph:")
                print("-"*50)
                print(synopsis.split('\n\n')[0])
            else:
                print("Failed to generate synopsis")
                return 1
        
        return 0
        
    except Exception as e:
        print(f"Error during synopsis generation: {e}")
        return 1

if __name__ == "__main__":
    exit(main())