#!/usr/bin/env python3
"""
revision_assistant.py - AI-powered revision tool based on alignment analysis.

This tool takes findings from alignment_report.md and helps you systematically
improve and rewrite chapters to better align with your synopsis and outline.
"""

import os
import re
import glob
import argparse
import datetime
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
        # Smart chapter finding for project root usage
        possible_paths = [
            chapter_path,  # Exact path as provided
            # Try different project structures
            os.path.join("glasshouse", "chapters", os.path.basename(chapter_path)),
            os.path.join("glasshouse", os.path.basename(chapter_path)),
            # Try other common novel directories
            os.path.join("*", "chapters", os.path.basename(chapter_path)),
            os.path.join("*", os.path.basename(chapter_path)),
        ]
        
        # Handle wildcard paths by searching subdirectories
        expanded_paths = []
        for path in possible_paths:
            if "*" in path:
                expanded_paths.extend(glob.glob(path))
            else:
                expanded_paths.append(path)
        
        for path in expanded_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        
        raise FileNotFoundError(f"Chapter not found: {chapter_path}\nSearched: {expanded_paths[:5]}...")
    
    def load_project_context(self, project_dir: str = ".") -> Dict[str, str]:
        """Load synopsis, outline, and characters for context."""
        files = {}
        
        # For project root usage, we need to find the actual project directory
        project_paths = [project_dir]
        
        # If we're in project root, look for novel directories
        if project_dir == ".":
            subdirs = [d for d in os.listdir(".") if os.path.isdir(d) and not d.startswith(".")]
            project_paths.extend(subdirs)
        
        project_files = {
            'synopsis': ['synopsis.md', 'synopsis.txt'],
            'outline': ['outline.md', 'outline.txt', 'Outline.md'],
            'characters': ['characters.md', 'characterList.md', 'characters.txt']
        }
        
        for search_dir in project_paths:
            found_any = False
            temp_files = {}
            
            for file_type, possible_names in project_files.items():
                for name in possible_names:
                    file_path = os.path.join(search_dir, name)
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            temp_files[file_type] = f.read()
                        found_any = True
                        break
                else:
                    temp_files[file_type] = ""
            
            # If we found project files in this directory, use them
            if found_any:
                files = temp_files
                if search_dir != ".":
                    print(f"Found project files in: {search_dir}")
                break
        
        # If no files found, initialize empty
        if not files:
            for file_type in project_files.keys():
                files[file_type] = ""
        
        return files
    
    def load_novelcraft_analysis(self, chapter_number: int, project_dir: str = ".") -> str:
        """Load NovelCraft AI analysis results for a specific chapter."""
        # Try various possible locations and formats for NovelCraft AI output
        possible_locations = [
            f"analysis/chapter_{chapter_number}_analysis.md",
            f"analysis/chapter_{chapter_number}.md", 
            f"analysis/chapter_{chapter_number}_analysis.txt",
            f"reports/chapter_{chapter_number}_analysis.json",
            f"reports/chapter_{chapter_number}.json",
            f"output/chapter_{chapter_number}_analysis.txt",
            f"output/analysis_chapter_{chapter_number}.txt",
            f"chapter_{chapter_number}_analysis.md",
            f"analysis_chapter_{chapter_number}.md",
            # Padded numbers
            f"analysis/chapter_{chapter_number:02d}_analysis.md",
            f"reports/chapter_{chapter_number:02d}.json",
            # Alternative naming
            f"novelcraft_analysis_ch{chapter_number}.md",
            f"ai_analysis_chapter_{chapter_number}.txt"
        ]
        
        analysis_content = ""
        found_files = []
        
        for location in possible_locations:
            full_path = os.path.join(project_dir, location)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content.strip():  # Only use non-empty files
                            analysis_content += f"\n\n=== FROM {location} ===\n{content}"
                            found_files.append(location)
                except Exception as e:
                    print(f"Warning: Could not read {full_path}: {e}")
        
        if found_files:
            print(f"✓ Loaded NovelCraft AI analysis from: {', '.join(found_files)}")
            return analysis_content
        else:
            print(f"⚠ No saved NovelCraft AI analysis found for chapter {chapter_number}")
            print(f"  💡 Tip: Run 'novelcraft ai analyze-chapter project.json --chapter {chapter_number}' first")
            print(f"  Or manually save the analysis output to: analysis/chapter_{chapter_number}_analysis.md")
            return ""
    
    def run_novelcraft_analysis(self, chapter_number: int, project_dir: str = ".") -> str:
        """Run NovelCraft AI analysis and capture output."""
        import subprocess
        import os
        
        try:
            # Create analysis directory if it doesn't exist
            analysis_dir = os.path.join(project_dir, "analysis")
            if not os.path.exists(analysis_dir):
                os.makedirs(analysis_dir)
                print(f"Created directory: {analysis_dir}")
            
            # Use absolute path to project.json - NovelCraft AI should handle this
            project_json_path = os.path.abspath(os.path.join(project_dir, "project.json"))
            
            if not os.path.exists(project_json_path):
                print(f"⚠ Warning: No project.json found at {project_json_path}")
                print(f"Current working directory: {os.getcwd()}")
                print(f"Files in {project_dir}: {os.listdir(project_dir) if os.path.exists(project_dir) else 'directory not found'}")
                return ""
            
            print(f"🤖 Running NovelCraft AI analysis for chapter {chapter_number}...")
            print(f"Using project file: {project_json_path}")
            
            # Execute the command from project root with absolute path
            cmd = ["novelcraft", "ai", "analyze-chapter", project_json_path, "--chapter", str(chapter_number)]
            print(f"Command: {' '.join(cmd)}")
            print(f"Running from: {os.getcwd()}")
            
            # Set environment variables to handle Unicode properly on Windows
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONLEGACYWINDOWSSTDIO'] = '0'
            
            # Fix encoding issues for Windows
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            if result.returncode == 0:
                # Clean up any problematic Unicode characters before saving
                clean_output = result.stdout.encode('utf-8', errors='replace').decode('utf-8')
                
                # Save the output to analysis file
                output_file = os.path.join(analysis_dir, f"chapter_{chapter_number}_analysis.md")
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"# NovelCraft AI Analysis - Chapter {chapter_number}\n\n")
                    f.write(clean_output)
                
                print(f"✓ NovelCraft AI analysis saved to: {output_file}")
                return clean_output
            else:
                # Handle Unicode in error messages too
                clean_stdout = result.stdout.encode('utf-8', errors='replace').decode('utf-8') if result.stdout else ""
                clean_stderr = result.stderr.encode('utf-8', errors='replace').decode('utf-8') if result.stderr else ""
                
                print(f"❌ NovelCraft AI analysis failed:")
                print(f"STDOUT: {clean_stdout}")
                print(f"STDERR: {clean_stderr}")
                
                # The error is coming from NovelCraft AI itself - suggest workaround
                print(f"\n💡 This appears to be a Unicode encoding issue in NovelCraft AI.")
                print(f"   Try setting your console to UTF-8 first:")
                print(f"   chcp 65001")
                print(f"   Then run: novelcraft ai analyze-chapter \"{project_json_path}\" --chapter {chapter_number}")
                print(f"\n   Continuing without NovelCraft AI analysis...")
                return ""
                
        except FileNotFoundError:
            print("❌ NovelCraft AI command not found. Make sure it's installed and in PATH.")
            return ""
        except Exception as e:
            print(f"❌ Error running NovelCraft AI analysis: {e}")
            return ""
    
    def parse_chapter_number(self, chapter_path: str) -> int:
        """Extract chapter number from chapter filename."""
        filename = os.path.basename(chapter_path)
        
        # Try various patterns to extract chapter number
        patterns = [
            r'chapter[_\s]*(\d+)',
            r'ch[_\s]*(\d+)', 
            r'(\d+)[_\s]*chapter',
            r'(\d+)'  # Just any number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        # Fallback: ask user or default to 1
        print(f"Warning: Could not extract chapter number from '{filename}'")
        return 1
    
    def load_saved_revision_plan(self, chapter_name: str, project_dir: str = ".") -> str:
        """Load a previously saved revision plan for the chapter."""
        plan_filename = f"{os.path.splitext(chapter_name)[0]}_revision_plan.md"
        possible_plan_paths = [
            os.path.join(project_dir, "revision_plans", plan_filename),
            os.path.join("revision_plans", plan_filename),
            plan_filename
        ]
        
        for plan_path in possible_plan_paths:
            if os.path.exists(plan_path):
                with open(plan_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Extract just the plan content (skip the header metadata)
                    if "---" in content:
                        plan_content = content.split("---", 1)[1].strip()
                    else:
                        plan_content = content
                print(f"✓ Using saved revision plan: {plan_path}")
                return plan_content
        
        print(f"⚠ No saved revision plan found for {chapter_name}")
        return ""
    
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
                           project_context: Dict[str, str], chapter_name: str,
                           novelcraft_analysis: str = "") -> str:
        """Create a detailed revision plan for the chapter."""
        
        # Combine alignment issues with NovelCraft AI analysis
        combined_analysis = chapter_issues
        if novelcraft_analysis:
            combined_analysis += f"\n\nNOVELCRAFT AI ANALYSIS:\n{novelcraft_analysis}"
        
        prompt = f"""You are creating a detailed revision plan for a chapter in "A Season of Spies" based on multiple analysis sources.

PROJECT CONTEXT:
SYNOPSIS: {project_context['synopsis']}
OUTLINE: {project_context['outline']}
CHARACTERS: {project_context['characters']}

CURRENT CHAPTER: {chapter_name}
{chapter_content}

ALIGNMENT ISSUES IDENTIFIED:
{combined_analysis}

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
        """Save revised chapter in project's revised folder with backup of original."""
        # Determine which project directory we're working with
        project_dir = "."
        
        # If original path has directory structure, extract project info
        if "/" in original_path or "\\" in original_path:
            path_parts = original_path.replace("\\", "/").split("/")
            if len(path_parts) > 1:
                # Assume first part is project directory (e.g., "glasshouse/chapters/file.md")
                project_dir = path_parts[0]
        
        filename = os.path.basename(original_path)
        base, ext = os.path.splitext(filename)
        
        # Create revised folder in the project directory
        revised_dir = os.path.join(project_dir, "revised")
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
  # From project root, revise any novel's chapter
  python revision_assistant.py glasshouse/chapters/chapter_01.md --plan-only
  
  # Revise with NovelCraft AI integration
  python revision_assistant.py glasshouse/chapters/chapter_01.md --run-novelcraft --words 3000
  
  # Quick chapter reference (will search for it)
  python revision_assistant.py chapter_01.md --project glasshouse
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
        "--run-novelcraft", 
        action="store_true",
        help="Run NovelCraft AI analysis first before revision"
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
        # Determine the actual project directory from the chapter path
        chapter_path_parts = args.chapter.replace("\\", "/").split("/")
        if len(chapter_path_parts) > 1 and chapter_path_parts[0] != "." and os.path.isdir(chapter_path_parts[0]):
            # Extract project directory from chapter path (e.g., "glasshouse/chapters/file.md" -> "glasshouse")
            detected_project = chapter_path_parts[0]
            print(f"Detected project directory: {detected_project}")
        else:
            detected_project = args.project
        
        # Load project context
        print(f"Loading project context...")
        project_context = assistant.load_project_context(detected_project)
        
        # Load alignment report (look in multiple locations, including chapter-specific)
        chapter_num = assistant.parse_chapter_number(args.chapter)
        chapter_name = os.path.basename(args.chapter)
        
        possible_report_paths = [
            args.report,  # Exact path as specified
            os.path.join(detected_project, args.report),  # In detected project directory
            # Chapter-specific reports
            os.path.join(detected_project, f"chapter_{chapter_num}_alignment.md"),
            os.path.join(detected_project, f"{chapter_name}_alignment.md"),
            os.path.join(detected_project, f"alignment_chapter_{chapter_num}.md"),
            # General reports
            os.path.join(detected_project, "alignment_report.md"),
            os.path.join(args.project, args.report),  # In specified project directory
            "alignment_report.md"  # Current directory
        ]
        
        # Find the alignment report
        found_report = None
        for potential_path in possible_report_paths:
            if os.path.exists(potential_path):
                found_report = potential_path
                break
        
        if found_report:
            print(f"Loading alignment report: {found_report}")
            alignment_report = assistant.load_alignment_report(found_report)
        else:
            print(f"⚠ Warning: No alignment report found")
            print(f"  Searched: {[p for p in possible_report_paths if not p.startswith('.')]}")
            print(f"  💡 Tip: Run alignment checker for just this chapter:")
            print(f"     python alignment_checker.py --project {detected_project} --chapter {chapter_name} --detailed --output {detected_project}/chapter_{chapter_num}_alignment.md")
            print(f"  Continuing without alignment report...")
            alignment_report = "No alignment report available."
        
        # Load chapter
        chapter_name = os.path.basename(args.chapter)
        print(f"Loading chapter: {chapter_name}")
        chapter_content = assistant.load_chapter(args.chapter)
        
        original_word_count = len(chapter_content.split())
        print(f"Original chapter: {original_word_count} words")
        
        # Extract chapter-specific issues
        print("Extracting chapter-specific issues from alignment report...")
        chapter_issues = assistant.extract_chapter_issues(alignment_report, chapter_name)
        
        # Optionally run NovelCraft AI analysis
        novelcraft_analysis = ""
        if args.run_novelcraft:
            chapter_num = assistant.parse_chapter_number(args.chapter)
            novelcraft_analysis = assistant.run_novelcraft_analysis(chapter_num, detected_project)
        else:
            # Try to load existing NovelCraft analysis
            chapter_num = assistant.parse_chapter_number(args.chapter)
            novelcraft_analysis = assistant.load_novelcraft_analysis(chapter_num, detected_project)
        
        # Create revision plan (or load existing one)
        print("Creating revision plan...")
        
        # First check if we have a saved revision plan
        saved_plan = assistant.load_saved_revision_plan(chapter_name, detected_project)
        
        if saved_plan and not args.plan_only:
            # Use the saved plan for revision
            revision_plan = saved_plan
            print("✓ Using previously saved revision plan")
        else:
            # Create a new revision plan
            revision_plan = assistant.create_revision_plan(
                chapter_content, chapter_issues, project_context, chapter_name,
                novelcraft_analysis
            )
        
        if args.plan_only:
            print("\n" + "="*60)
            print(f"REVISION PLAN FOR {chapter_name}")
            print("="*60)
            print(revision_plan)
            
            # Save the revision plan to a file for reference
            plan_output_dir = os.path.join(detected_project, "revision_plans")
            if not os.path.exists(plan_output_dir):
                os.makedirs(plan_output_dir)
                print(f"\nCreated directory: {plan_output_dir}")
            
            plan_filename = f"{os.path.splitext(chapter_name)[0]}_revision_plan.md"
            plan_output_path = os.path.join(plan_output_dir, plan_filename)
            
            with open(plan_output_path, 'w', encoding='utf-8') as f:
                f.write(f"# REVISION PLAN FOR {chapter_name}\n\n")
                f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Original word count:** {original_word_count} words\n\n")
                f.write("---\n\n")
                f.write(revision_plan)
            
            print(f"\n📋 Revision plan saved to: {plan_output_path}")
            print(f"💡 Use this plan to guide your manual revision or run without --plan-only to auto-revise")
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