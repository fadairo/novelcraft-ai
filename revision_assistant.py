#!/usr/bin/env python3
"""
revision_assistant.py - AI-powered revision tool based on alignment analysis

This tool takes findings from alignment_report.md and helps you systematically
improve and rewrite chapters to better align with your synopsis and outline.
"""

import os
import re
import argparse
from typing import List, Dict, Tuple
import anthropic

class RevisionAssistant:
    """Helps revise chapters based on alignment report findings."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
    
    def load_alignment_report(self, report_path: str) -> str:
        """Load the alignment report for analysis."""
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"Alignment report not found: {report_path}")
        
        with open(report_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def load_chapter(self, chapter_path: str) -> str:
        """Load chapter content for revision."""
        # Smart chapter finding (reuse logic from inspiration.py)
        possible_paths = [
            chapter_path,
            os.path.join("chapters", chapter_path),
            os.path.join("chapters", f"{chapter_path}.md"),
            os.path.join("content", chapter_path),
            os.path.join("manuscript", chapter_path)
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        
        raise FileNotFoundError(f"Chapter not found: {chapter_path}")
    
    def load_project_context(self, project_dir: str = ".") -> Dict[str, str]:
        """Load synopsis, outline, and characters for context."""
        files = {}
        
        project_files = {
            'synopsis': ['synopsis.md', 'synopsis.txt'],
            'outline': ['outline.md', 'outline.txt', 'Outline.md'],
            'characters': ['characters.md', 'characterList.md', 'characters.txt']
        }
        
        for file_type, possible_names in project_files.items():
            for name in possible_names:
                file_path = os.path.join(project_dir, name)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        files[file_type] = f.read()
                    break
            else:
                files[file_type] = ""
        
        return files
    
    def extract_chapter_issues(self, alignment_report: str, chapter_name: str) -> str:
        """Extract specific issues for a chapter from the alignment report."""
        # Look for the chapter section in the report
        chapter_pattern = rf"###?\s*{re.escape(chapter_name)}.*?(?=###|\Z)"
        match = re.search(chapter_pattern, alignment_report, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(0)
        
        # If no specific section found, return general recommendations
        general_pattern = r"## OVERALL ASSESSMENT.*?(?=##|\Z)"
        general_match = re.search(general_pattern, alignment_report, re.DOTALL)
        
        if general_match:
            return f"General guidance for {chapter_name}:\n{general_match.group(0)}"
        
        return f"No specific issues found for {chapter_name} in alignment report."
    
    def create_revision_plan(self, chapter_content: str, chapter_issues: str, 
                           project_context: Dict[str, str], chapter_name: str) -> str:
        """Create a detailed revision plan for the chapter."""
        
        prompt = f"""You are creating a detailed revision plan for a chapter in "A Season of Spies" based on alignment analysis.

PROJECT CONTEXT:
SYNOPSIS: {project_context['synopsis']}
OUTLINE: {project_context['outline']}
CHARACTERS: {project_context['characters']}

CURRENT CHAPTER: {chapter_name}
{chapter_content}

ALIGNMENT ISSUES IDENTIFIED:
{chapter_issues}

Create a comprehensive revision plan that addresses the specific issues found. Structure your response as:

## REVISION PRIORITIES
List the top 3-5 most important issues to address, ranked by impact.

## PLOT ADJUSTMENTS
Specific changes needed to align with synopsis/outline:
- What plot points need to be added, modified, or removed?
- How should the chapter's role in the overall arc be strengthened?

## CHARACTER IMPROVEMENTS
Character-specific revisions needed:
- Dialogue enhancements for voice consistency
- Character motivation clarifications
- Relationship dynamic improvements

## STRUCTURAL CHANGES
Pacing and structure modifications:
- Scene reorganization needs
- Five-act structure improvements (Inciting Incident, Rising Action, Crisis, Climax, Resolution)
- Tension and suspense adjustments

## THEMATIC ENHANCEMENTS
Ways to better serve the novel's themes:
- Moral ambiguity elements to strengthen
- Cold War atmosphere improvements
- Family/generational conflict development

## CONTINUITY FIXES
Specific consistency issues to resolve:
- Timeline corrections needed
- Factual consistency with other chapters
- Character knowledge/behavior alignment

## ACTIONABLE TASKS
Concrete, specific tasks for revision:
1. [Specific task with clear instructions]
2. [Another specific task]
[Continue with numbered, actionable items]

Focus on practical, implementable suggestions that will measurably improve the chapter's alignment with the planned story."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Error creating revision plan: {e}"
    
    def revise_chapter(self, chapter_content: str, revision_plan: str, 
                      project_context: Dict[str, str], chapter_name: str,
                      target_word_count: int = None) -> str:
        """Revise the chapter based on the revision plan."""
        
        original_word_count = len(chapter_content.split())
        if target_word_count is None:
            target_word_count = int(original_word_count * 1.2)  # Default 20% expansion
        
        prompt = f"""You are revising a chapter from "A Season of Spies" based on a detailed revision plan.

PROJECT CONTEXT:
SYNOPSIS: {project_context['synopsis']}
OUTLINE: {project_context['outline']}
CHARACTERS: {project_context['characters']}

REVISION PLAN TO IMPLEMENT:
{revision_plan}

CURRENT CHAPTER TO REVISE: {chapter_name}
{chapter_content}

TARGET WORD COUNT: Approximately {target_word_count} words (original: {original_word_count} words)

REVISION REQUIREMENTS:
1. Implement ALL recommendations from the revision plan
2. Maintain the five-act structure in each scene (Inciting Incident, Rising Action, Crisis, Climax, Resolution)
3. Ensure plot alignment with synopsis and outline
4. Strengthen character consistency and development
5. Improve thematic elements and atmospheric details
6. Fix any continuity issues identified
7. Enhance literary quality while maintaining spy fiction genre conventions

CRITICAL INSTRUCTIONS:
- You must revise the ENTIRE chapter from beginning to end
- Do NOT include any commentary, questions, or notes in your response
- Return ONLY the complete revised chapter text
- Implement every point from the revision plan
- Maintain or improve the literary quality of the prose
- Ensure the chapter serves its role in the overall narrative arc

This is literary spy fiction focusing on:
- Psychological complexity and moral ambiguity
- Atmospheric tension (Cambridge academia, Cold War shadows)
- Character relationships and family dynamics
- Beautiful, precise prose that serves the story

Return the complete revised chapter ready for publication."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            revised_text = response.content[0].text
            
            # Clean any potential AI commentary
            revised_text = self._clean_ai_commentary(revised_text)
            
            return revised_text
            
        except Exception as e:
            return f"Error revising chapter: {e}"
    
    def _clean_ai_commentary(self, text: str) -> str:
        """Remove any AI commentary from revised text."""
        import re
        
        patterns_to_remove = [
            r'\[.*?\]',  # Square brackets
            r'Would you like.*?\?',  # Questions
            r'I can .*?\.', # AI statements
            r'Note:.*?\.', # Notes
        ]
        
        cleaned_text = text
        for pattern in patterns_to_remove:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)
        return cleaned_text.strip()
    
    def save_revised_chapter(self, content: str, original_path: str, suffix: str = "_revised"):
        """Save revised chapter in revised folder with backup of original."""
        # Determine output path - always save to revised/ folder
        filename = os.path.basename(original_path)
        base, ext = os.path.splitext(filename)
        
        # Create revised folder if it doesn't exist
        revised_dir = "revised"
        if not os.path.exists(revised_dir):
            os.makedirs(revised_dir)
            print(f"Created directory: {revised_dir}")
        
        # Determine output filename
        if suffix:
            output_filename = f"{base}{suffix}{ext}"
        else:
            output_filename = filename
        
        output_path = os.path.join(revised_dir, output_filename)
        
        # Create backup if we're overwriting an existing revised file
        if os.path.exists(output_path):
            backup_base, backup_ext = os.path.splitext(output_path)
            backup_path = f"{backup_base}_backup{backup_ext}"
            os.rename(output_path, backup_path)
            print(f"Previous revision backed up to: {backup_path}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Revised chapter saved to: {output_path}")
        return output_path

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Revise chapters based on alignment report findings",
        epilog="""
Examples:
  # Create revision plan for a chapter
  python revision_assistant.py chapter_01.md --plan-only
  
  # Revise chapter based on alignment report
  python revision_assistant.py chapter_01.md --report alignment_report.md
  
  # Revise with specific word count target
  python revision_assistant.py chapter_01.md --report alignment_report.md --words 3000
  
  # Save with custom suffix
  python revision_assistant.py chapter_01.md --report alignment_report.md --suffix "_v2"
        """
    )
    parser.add_argument(
        "chapter", 
        help="Chapter file to revise"
    )
    parser.add_argument(
        "--report", 
        default="alignment_report.md",
        help="Path to alignment report (default: alignment_report.md)"
    )
    parser.add_argument(
        "--words", 
        type=int,
        help="Target word count for revised chapter"
    )
    parser.add_argument(
        "--plan-only", 
        action="store_true",
        help="Only create revision plan, don't revise chapter"
    )
    parser.add_argument(
        "--suffix", 
        default="_revised",
        help="Suffix for revised chapter filename (default: _revised)"
    )
    parser.add_argument(
        "--project", 
        default=".",
        help="Project directory (default: current directory)"
    )
    
    args = parser.parse_args()
    
    try:
        assistant = RevisionAssistant()
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        # Load project context
        print(f"Loading project context from: {args.project}")
        project_context = assistant.load_project_context(args.project)
        
        # Load alignment report
        print(f"Loading alignment report: {args.report}")
        alignment_report = assistant.load_alignment_report(args.report)
        
        # Load chapter
        chapter_name = os.path.basename(args.chapter)
        print(f"Loading chapter: {chapter_name}")
        chapter_content = assistant.load_chapter(args.chapter)
        
        original_word_count = len(chapter_content.split())
        print(f"Original chapter: {original_word_count} words")
        
        # Extract chapter-specific issues
        print("Extracting chapter-specific issues from alignment report...")
        chapter_issues = assistant.extract_chapter_issues(alignment_report, chapter_name)
        
        # Create revision plan
        print("Creating revision plan...")
        revision_plan = assistant.create_revision_plan(
            chapter_content, chapter_issues, project_context, chapter_name
        )
        
        if args.plan_only:
            print("\n" + "="*60)
            print(f"REVISION PLAN FOR {chapter_name}")
            print("="*60)
            print(revision_plan)
            return 0
        
        # Revise chapter
        print("Revising chapter based on plan...")
        revised_content = assistant.revise_chapter(
            chapter_content, revision_plan, project_context, chapter_name,
            target_word_count=args.words
        )
        
        revised_word_count = len(revised_content.split())
        print(f"Revised chapter: {revised_word_count} words")
        
        # Save revised chapter
        output_path = assistant.save_revised_chapter(
            revised_content, args.chapter, args.suffix
        )
        
        print(f"\nRevision complete!")
        print(f"Word count: {original_word_count} → {revised_word_count}")
        print(f"Revised chapter: {output_path}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())