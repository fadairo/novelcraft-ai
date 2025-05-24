#!/usr/bin/env python3
"""
alignment_checker.py - Manuscript alignment verification tool

This tool checks if your written chapters align with your synopsis and detailed outline,
ensuring story consistency and tracking progress against your planned structure.
"""

import os
import glob
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import anthropic

class AlignmentChecker:
    """Checks manuscript alignment with synopsis and outline."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
    
    def load_project_files(self, project_dir: str = ".") -> Dict[str, str]:
        """Load synopsis, outline, and character files from project directory."""
        files = {}
        
        # Resolve absolute path to handle relative references correctly
        project_path = os.path.abspath(project_dir)
        print(f"Looking for project files in: {project_path}")
        
        # Look for key project files
        project_files = {
            'synopsis': ['synopsis.md', 'synopsis.txt', 'summary.md', 'summary.txt', 'Synopsis.md', 'Synopsis.txt'],
            'outline': ['outline.md', 'outline.txt', 'Outline.md', 'Outline.txt'],
            'characters': ['characters.md', 'characterList.md', 'characters.txt', 'characterList.txt']
        }
        
        for file_type, possible_names in project_files.items():
            found = False
            for name in possible_names:
                file_path = os.path.join(project_path, name)
                print(f"  Checking: {file_path}")
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        files[file_type] = f.read()
                    print(f"✓ Loaded {file_type}: {name}")
                    found = True
                    break
            
            if not found:
                print(f"✗ Warning: No {file_type} file found")
                files[file_type] = ""
        
        return files
    
    def find_chapters(self, project_dir: str = ".") -> List[Tuple[str, str]]:
        """Find all chapter files in the project."""
        project_path = os.path.abspath(project_dir)
        chapter_dirs = ['chapters', 'content', 'manuscript', '.']
        chapter_files = []
        found_files = set()  # Track found files to avoid duplicates
        
        print(f"Looking for chapters in: {project_path}")
        
        for chapter_dir in chapter_dirs:
            search_dir = os.path.join(project_path, chapter_dir)
            print(f"  Checking directory: {search_dir}")
            
            if not os.path.exists(search_dir):
                print(f"    Directory does not exist: {search_dir}")
                continue
                
            # Look for chapter files with various patterns
            patterns = [
                'chapter_*.md', 'chapter_*.txt',
                'ch_*.md', 'ch_*.txt'
            ]
            
            for pattern in patterns:
                search_pattern = os.path.join(search_dir, pattern)
                files = glob.glob(search_pattern)
                matching_files = [f for f in files if f not in found_files]
                print(f"    Pattern {pattern}: found {len(matching_files)} new files")
                
                for file_path in matching_files:
                    # Skip enhanced/backup files
                    filename = os.path.basename(file_path)
                    if any(skip in filename.lower() for skip in ['enhanced', 'backup', 'characters', 'synopsis', 'outline']):
                        print(f"      Skipping: {filename} (non-chapter file)")
                        continue
                    
                    # Only include files that look like chapters
                    if not any(chapter_indicator in filename.lower() for chapter_indicator in ['chapter', 'ch_']):
                        print(f"      Skipping: {filename} (doesn't match chapter pattern)")
                        continue
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        chapter_files.append((file_path, content))
                        found_files.add(file_path)
                        print(f"      ✓ Added: {filename}")
                    except Exception as e:
                        print(f"      ✗ Error reading {file_path}: {e}")
        
        # Sort by filename for logical order
        chapter_files.sort(key=lambda x: x[0])
        print(f"Total unique chapters found: {len(chapter_files)}")
        return chapter_files
    
    def analyze_chapter_alignment(self, chapter_content: str, chapter_path: str, 
                                 project_files: Dict[str, str]) -> str:
        """Analyze how well a chapter aligns with the planned story."""
        
        prompt = f"""You are analyzing a chapter from "A Season of Spies" for alignment with the planned story structure.

PROJECT SYNOPSIS:
{project_files['synopsis']}

DETAILED OUTLINE:
{project_files['outline']}

CHARACTER INFORMATION:
{project_files['characters']}

CHAPTER TO ANALYZE:
File: {chapter_path}
Content: {chapter_content}

ALIGNMENT ANALYSIS REQUIRED:

1. PLOT ADHERENCE:
- Does this chapter follow the planned plot points from the outline?
- Are key story beats present and executed as planned?
- Any major deviations from the intended narrative?

2. CHARACTER CONSISTENCY:
- Do characters behave according to their established personalities?
- Are character arcs progressing as outlined?
- Any inconsistencies with character backgrounds or motivations?

3. PACING AND STRUCTURE:
- Does the chapter maintain appropriate pacing for its position in the story?
- Are the five-act elements (Inciting Incident, Rising Action, Crisis, Climax, Resolution) present?
- How does this chapter serve the overall narrative structure?

4. THEMATIC ALIGNMENT:
- Are the planned themes being explored effectively?
- Does the chapter contribute to the overall thematic goals?

5. CONTINUITY CHECK:
- Any plot holes or logical inconsistencies?
- Timeline and factual consistency with previous chapters?

6. SUGGESTIONS:
- Specific recommendations for better alignment
- Areas that need development or revision
- Missing elements that should be included

Provide a clear, actionable analysis focusing on story consistency and adherence to the planned narrative."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            print(f"Error analyzing chapter {chapter_path}: {e}")
            return f"Error analyzing chapter: {e}"
    
    def create_overall_alignment_report(self, chapter_analyses: List[str], 
                                      project_files: Dict[str, str]) -> str:
        """Create an overall manuscript alignment report."""
        
        combined_analyses = "\n\n".join([f"CHAPTER {i+1} ANALYSIS:\n{analysis}" 
                                       for i, analysis in enumerate(chapter_analyses)])
        
        prompt = f"""Based on individual chapter analyses, create an overall manuscript alignment report.

PROJECT SYNOPSIS:
{project_files['synopsis']}

OUTLINE STRUCTURE:
{project_files['outline']}

INDIVIDUAL CHAPTER ANALYSES:
{combined_analyses}

OVERALL MANUSCRIPT ASSESSMENT:

1. STORY PROGRESSION:
- How well does the overall manuscript follow the planned story arc?
- Are major plot points being hit in the right order?
- Any significant gaps or rushed sections?

2. CHARACTER DEVELOPMENT:
- Are character arcs developing consistently across chapters?
- Any characters being neglected or over-emphasized?

3. STRUCTURAL INTEGRITY:
- Does the manuscript maintain good pacing throughout?
- Are act divisions clear and effective?
- How well does the structure serve the story?

4. THEMATIC CONSISTENCY:
- Are themes being developed consistently?
- Any thematic confusion or contradictions?

5. CONTINUITY AND LOGIC:
- Overall story logic and consistency
- Major continuity issues to address

6. COMPLETION STATUS:
- What percentage of the planned story has been written?
- Which planned elements are missing?
- Priority areas for development

7. ACTIONABLE RECOMMENDATIONS:
- Top 3 priority fixes for better alignment
- Specific chapters that need revision
- Missing scenes or elements to add

Provide a comprehensive but concise report suitable for guiding revision efforts."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            print(f"Error creating overall report: {e}")
            return f"Error creating overall report: {e}"

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Check manuscript alignment with synopsis and outline",
        epilog="""
Examples:
  # Check alignment for current project
  python alignment_checker.py
  
  # Check specific project directory
  python alignment_checker.py --project glasshouse
  
  # Generate detailed report
  python alignment_checker.py --detailed
  
  # Save report to file
  python alignment_checker.py --output alignment_report.md
        """
    )
    parser.add_argument(
        "--project", 
        default=".",
        help="Project directory path (default: current directory)"
    )
    parser.add_argument(
        "--output", 
        help="Save report to specified file"
    )
    parser.add_argument(
        "--detailed", 
        action="store_true",
        help="Include detailed chapter-by-chapter analysis in output"
    )
    parser.add_argument(
        "--chapter", 
        help="Check alignment for specific chapter only"
    )
    
    args = parser.parse_args()
    
    # Initialize checker
    try:
        checker = AlignmentChecker()
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        # Load project files
        print(f"Loading project files from: {args.project}")
        
        # Handle different ways of specifying project path
        if args.project == "." or (args.project == os.path.basename(os.getcwd())):
            # We're already in the target directory, or target matches current dir name
            project_path = "."
            print(f"Using current directory: {os.getcwd()}")
        else:
            project_path = args.project
            print(f"Using specified project path: {os.path.abspath(project_path)}")
        
        project_files = checker.load_project_files(project_path)
        
        if not project_files['synopsis'] and not project_files['outline']:
            print("Error: No synopsis or outline found. Cannot perform alignment check.")
            return 1
        
        # Find chapters
        chapter_files = checker.find_chapters(project_path)
        if not chapter_files:
            print("Error: No chapter files found.")
            return 1
        
        print(f"Found {len(chapter_files)} chapters to analyze")
        
        # Filter to specific chapter if requested
        if args.chapter:
            chapter_files = [(path, content) for path, content in chapter_files 
                           if args.chapter in os.path.basename(path)]
            if not chapter_files:
                print(f"Error: Chapter '{args.chapter}' not found")
                return 1
        
        # Analyze each chapter
        print("\nAnalyzing chapters...")
        chapter_analyses = []
        
        for i, (chapter_path, chapter_content) in enumerate(chapter_files):
            print(f"  Analyzing: {os.path.basename(chapter_path)}")
            analysis = checker.analyze_chapter_alignment(
                chapter_content, chapter_path, project_files
            )
            chapter_analyses.append(analysis)
        
        # Create overall report
        if not args.chapter:  # Only create overall report for full analysis
            print("\nCreating overall alignment report...")
            overall_report = checker.create_overall_alignment_report(
                chapter_analyses, project_files
            )
        else:
            overall_report = ""
        
        # Prepare output
        report_content = []
        
        report_content.append("# MANUSCRIPT ALIGNMENT REPORT")
        report_content.append(f"Project: {os.path.basename(os.path.abspath(args.project))}")
        report_content.append(f"Chapters analyzed: {len(chapter_files)}")
        report_content.append("")
        
        if overall_report:
            report_content.append("## OVERALL ASSESSMENT")
            report_content.append(overall_report)
            report_content.append("")
        
        if args.detailed or args.chapter:
            report_content.append("## DETAILED CHAPTER ANALYSIS")
            for i, (chapter_path, _) in enumerate(chapter_files):
                report_content.append(f"### {os.path.basename(chapter_path)}")
                report_content.append(chapter_analyses[i])
                report_content.append("")
        
        final_report = "\n".join(report_content)
        
        # Output report
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(final_report)
            print(f"Report saved to: {args.output}")
        else:
            print("\n" + "="*60)
            print(final_report)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())