"""
Command-line interface for NovelCraft AI.
"""

import asyncio
import click
from pathlib import Path
from typing import Optional
import logging

from ..core import Project, SnowflakeMethod
from ..ai import ClaudeClient, ContentGenerator
from ..io import ProjectLoader, FileHandler
from ..editor import ConsistencyChecker

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """NovelCraft AI - AI-assisted novel writing tool."""
    pass


@cli.command()
@click.argument("project_path", type=click.Path())
@click.option("--title", "-t", help="Novel title")
@click.option("--author", "-a", help="Author name")
@click.option("--genre", "-g", help="Genre")
def init(project_path: str, title: Optional[str], author: Optional[str], genre: Optional[str]):
    """Initialize a new novel project."""
    project_dir = Path(project_path)
    
    if project_dir.exists():
        click.echo(f"Error: Directory {project_path} already exists.")
        return
    
    # Create project structure
    project_dir.mkdir(parents=True)
    (project_dir / "manuscripts").mkdir()
    (project_dir / "characters").mkdir()
    (project_dir / "outlines").mkdir()
    (project_dir / "generated").mkdir()
    
    # Create project file
    project = Project(
        title=title or "Untitled Novel",
        author=author or "Unknown Author",
        project_path=project_dir,
        metadata={"genre": genre} if genre else {}
    )
    
    loader = ProjectLoader()
    loader.save_project(project, project_dir / "project.json")
    
    # Create initial files
    (project_dir / "synopsis.md").write_text("# Synopsis\n\nWrite your novel synopsis here.\n")
    (project_dir / "outline.md").write_text("# Outline\n\n## Chapter 1\n- Write chapter outline here\n")
    (project_dir / "characters.md").write_text("# Characters\n\n## Main Characters\n\n### Character Name\n- Description\n- Role\n- Goals\n")
    
    click.echo(f"✅ Created new novel project: {project_path}")
    click.echo(f"📝 Title: {project.title}")
    click.echo(f"👤 Author: {project.author}")
    click.echo("\n📁 Project structure:")
    click.echo("  project.json       - Project configuration")
    click.echo("  synopsis.md        - Story synopsis")
    click.echo("  outline.md         - Chapter outlines")
    click.echo("  characters.md      - Character profiles")
    click.echo("  manuscripts/       - Your manuscript files")
    click.echo("  generated/         - AI-generated content")


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.option("--chapter", "-c", type=int, help="Specific chapter to generate")
@click.option("--from-outline", "-o", is_flag=True, help="Generate from outline")
@click.option("--word-count", "-w", type=int, default=2000, help="Target word count")
def generate(project_path: str, chapter: Optional[int], from_outline: bool, word_count: int):
    """Generate content for the novel."""
    asyncio.run(_generate_content(project_path, chapter, from_outline, word_count))


async def _generate_content(project_path: str, chapter: Optional[int], from_outline: bool, word_count: int):
    """Async function to generate content."""
    project_dir = Path(project_path)
    
    # Load project
    loader = ProjectLoader()
    try:
        project = loader.load_project(project_dir / "project.json")
    except FileNotFoundError:
        click.echo("Error: No project.json found. Run 'novelcraft init' first.")
        return
    
    # Initialize AI client
    try:
        claude_client = ClaudeClient()
        generator = ContentGenerator(claude_client)
    except ValueError as e:
        click.echo(f"Error: {e}")
        click.echo("Please set your ANTHROPIC_API_KEY environment variable.")
        return
    
    # Load supporting materials
    file_handler = FileHandler()
    
    synopsis = ""
    if (project_dir / "synopsis.md").exists():
        synopsis = file_handler.read_file(project_dir / "synopsis.md")
    
    outline = ""
    if (project_dir / "outline.md").exists():
        outline = file_handler.read_file(project_dir / "outline.md")
    
    characters = ""
    if (project_dir / "characters.md").exists():
        characters = file_handler.read_file(project_dir / "characters.md")
    
    if not synopsis:
        click.echo("Warning: No synopsis found. Consider adding synopsis.md for better results.")
    
    if chapter:
        click.echo(f"🤖 Generating Chapter {chapter}...")
        
        try:
            content = await generator.generate_chapter(
                chapter_number=chapter,
                title=f"Chapter {chapter}",
                outline=outline,
                synopsis=synopsis,
                character_info=characters,
                word_count_target=word_count
            )
            
            # Save generated content
            output_file = project_dir / "generated" / f"chapter_{chapter}.md"
            file_handler.write_file(output_file, content)
            
            click.echo(f"✅ Generated Chapter {chapter}")
            click.echo(f"📄 Saved to: {output_file}")
            
        except Exception as e:
            click.echo(f"Error generating chapter: {e}")
    else:
        click.echo("🤖 Analyzing project for missing content...")
        
        # Find missing chapters based on outline
        missing_chapters = await generator.find_missing_chapters(
            outline, project.document.chapters.keys()
        )
        
        if missing_chapters:
            click.echo(f"Found {len(missing_chapters)} missing chapters: {missing_chapters}")
            
            for ch_num in missing_chapters[:3]:  # Limit to 3 to avoid rate limiting
                click.echo(f"🤖 Generating Chapter {ch_num}...")
                
                try:
                    content = await generator.generate_chapter(
                        chapter_number=ch_num,
                        title=f"Chapter {ch_num}",
                        outline=outline,
                        synopsis=synopsis,
                        character_info=characters,
                        word_count_target=word_count
                    )
                    
                    output_file = project_dir / "generated" / f"chapter_{ch_num}.md"
                    file_handler.write_file(output_file, content)
                    
                    click.echo(f"✅ Generated Chapter {ch_num}")
                    
                except Exception as e:
                    click.echo(f"Error generating Chapter {ch_num}: {e}")
                    continue
        else:
            click.echo("✅ No missing chapters found.")


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.argument("manuscript_file", type=click.Path(exists=True))
def check(project_path: str, manuscript_file: str):
    """Check manuscript for consistency and continuity issues."""
    asyncio.run(_check_manuscript(project_path, manuscript_file))


async def _check_manuscript(project_path: str, manuscript_file: str):
    """Async function to check manuscript."""
    project_dir = Path(project_path)
    manuscript_path = Path(manuscript_file)
    
    # Load project and manuscript
    loader = ProjectLoader()
    file_handler = FileHandler()
    
    try:
        project = loader.load_project(project_dir / "project.json")
        manuscript_content = file_handler.read_file(manuscript_path)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}")
        return
    
    # Load supporting materials
    characters = ""
    if (project_dir / "characters.md").exists():
        characters = file_handler.read_file(project_dir / "characters.md")
    
    synopsis = ""
    if (project_dir / "synopsis.md").exists():
        synopsis = file_handler.read_file(project_dir / "synopsis.md")
    
    # Initialize checker
    try:
        claude_client = ClaudeClient()
        checker = ConsistencyChecker(claude_client)
    except ValueError as e:
        click.echo(f"Error: {e}")
        return
    
    click.echo("🔍 Checking manuscript for consistency issues...")
    
    try:
        issues = await checker.check_consistency(
            manuscript_content,
            characters,
            synopsis
        )
        
        if issues:
            click.echo(f"\n⚠️  Found {len(issues)} potential issues:")
            for i, issue in enumerate(issues, 1):
                click.echo(f"{i}. {issue}")
        else:
            click.echo("✅ No consistency issues found!")
            
    except Exception as e:
        click.echo(f"Error checking manuscript: {e}")


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.argument("concept", type=str)
def snowflake(project_path: str, concept: str):
    """Start Snowflake Method development with a concept."""
    project_dir = Path(project_path)
    
    # Load project
    loader = ProjectLoader()
    try:
        project = loader.load_project(project_dir / "project.json")
    except FileNotFoundError:
        click.echo("Error: No project.json found. Run 'novelcraft init' first.")
        return
    
    # Initialize Snowflake Method
    snowflake = SnowflakeMethod(concept)
    
    click.echo("❄️  Starting Snowflake Method Development")
    click.echo(f"📝 Initial concept: {concept}")
    
    # Save to project
    snowflake_file = project_dir / "snowflake.json"
    file_handler = FileHandler()
    file_handler.write_json(snowflake_file, snowflake.to_dict())
    
    click.echo(f"✅ Snowflake data saved to: {snowflake_file}")
    click.echo("\n📋 Next steps:")
    click.echo("1. Run 'novelcraft expand' to develop the concept further")
    click.echo("2. Use 'novelcraft generate' to create content from the expanded outline")


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.option("--level", type=click.Choice(["sentence", "paragraph", "page", "chapter"]), 
              default="paragraph", help="Expansion level")
def expand(project_path: str, level: str):
    """Expand Snowflake Method to the next level."""
    asyncio.run(_expand_snowflake(project_path, level))


async def _expand_snowflake(project_path: str, level: str):
    """Async function to expand snowflake."""
    project_dir = Path(project_path)
    
    # Load snowflake data
    snowflake_file = project_dir / "snowflake.json"
    if not snowflake_file.exists():
        click.echo("Error: No snowflake.json found. Run 'novelcraft snowflake' first.")
        return
    
    file_handler = FileHandler()
    snowflake_data = file_handler.read_json(snowflake_file)
    snowflake = SnowflakeMethod.from_dict(snowflake_data)
    
    # Initialize AI client
    try:
        claude_client = ClaudeClient()
    except ValueError as e:
        click.echo(f"Error: {e}")
        return
    
    click.echo(f"❄️  Expanding to {level} level...")
    
    try:
        if level == "sentence":
            await snowflake.expand_to_sentence(claude_client)
        elif level == "paragraph":
            await snowflake.expand_to_paragraph(claude_client)
        elif level == "page":
            await snowflake.expand_to_page(claude_client)
        elif level == "chapter":
            await snowflake.expand_to_chapter_outline(claude_client)
        
        # Save updated snowflake
        file_handler.write_json(snowflake_file, snowflake.to_dict())
        
        click.echo(f"✅ Expanded to {level} level")
        click.echo(f"💾 Updated: {snowflake_file}")
        
        # Show current state
        current_content = getattr(snowflake, f"{level}_summary", "")
        if current_content:
            click.echo(f"\n📄 Current {level} summary:")
            click.echo(current_content[:300] + "..." if len(current_content) > 300 else current_content)
            
    except Exception as e:
        click.echo(f"Error expanding snowflake: {e}")


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
def status(project_path: str):
    """Show project status and statistics."""
    project_dir = Path(project_path)
    
    # Load project
    loader = ProjectLoader()
    try:
        project = loader.load_project(project_dir / "project.json")
    except FileNotFoundError:
        click.echo("Error: No project.json found.")
        return
    
    click.echo(f"📖 Project: {project.title}")
    click.echo(f"👤 Author: {project.author}")
    click.echo(f"📅 Created: {project.created_at.strftime('%Y-%m-%d')}")
    click.echo(f"📝 Chapters: {project.document.chapter_count}")
    click.echo(f"📊 Total words: {project.document.word_count:,}")
    
    # Check for supporting files
    files_status = []
    for filename in ["synopsis.md", "outline.md", "characters.md"]:
        if (project_dir / filename).exists():
            files_status.append(f"✅ {filename}")
        else:
            files_status.append(f"❌ {filename}")
    
    click.echo("\n📁 Supporting files:")
    for status_line in files_status:
        click.echo(f"  {status_line}")
    
    # Check generated content
    generated_dir = project_dir / "generated"
    if generated_dir.exists():
        generated_files = list(generated_dir.glob("*.md"))
        click.echo(f"\n🤖 Generated files: {len(generated_files)}")
        for file in generated_files[:5]:  # Show first 5
            click.echo(f"  📄 {file.name}")
        if len(generated_files) > 5:
            click.echo(f"  ... and {len(generated_files) - 5} more")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()