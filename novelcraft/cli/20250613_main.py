"""Main CLI entry point for NovelCraft AI with file-based architecture."""

import click
import json
import sys
from pathlib import Path
from typing import Optional

from ..core.project import Project
from ..core.character import Character, CharacterManager, CharacterRole
from ..core.document import normalize_chapter_title, ChapterReference
from ..io.project_loader import ProjectLoader
from ..io.file_handler import FileHandler


@click.group()
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx):
    """NovelCraft AI - AI-powered novel writing assistant"""
    ctx.ensure_object(dict)
    ctx.obj['file_handler'] = FileHandler()
    ctx.obj['project_loader'] = ProjectLoader()


@cli.group()
def project():
    """Project management commands"""
    pass


@cli.group()
def character():
    """Character management commands"""
    pass


@cli.group()
def chapter():
    """Chapter management commands"""
    pass


# Project Commands
@project.command()
@click.option('--title', prompt='Project title', help='Title of the novel')
@click.option('--author', prompt='Author name', help='Author of the novel')
@click.option('--path', type=click.Path(), help='Project directory path')
@click.pass_context
def create(ctx, title, author, path):
    """Create a new novel project"""
    try:
        if path:
            project_path = Path(path).resolve()
        else:
            # Use current directory with project name
            safe_title = title.lower().replace(' ', '_').replace('-', '_')
            project_path = Path.cwd() / safe_title
        
        project_path.mkdir(parents=True, exist_ok=True)
        
        new_project = Project(
            title=title,
            author=author,
            project_path=project_path
        )
        
        project_file = project_path / 'project.json'
        ctx.obj['project_loader'].save_project(new_project, project_file)
        
        click.echo(f"✅ Created project '{title}' in {project_path}")
        click.echo(f"📁 Project file: {project_file}")
        click.echo(f"📁 Chapters directory: {project_path / 'chapters'}")
        
    except Exception as e:
        click.echo(f"❌ Error creating project: {e}", err=True)
        sys.exit(1)


@project.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def discover(ctx, project_file):
    """Discover and import existing content files"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        # Discover existing content
        discovered = project.discover_existing_content()
        
        click.echo(f"🔍 Discovering content in {project.project_path}")
        click.echo("=" * 50)
        
        # Show discovered files
        if discovered["chapters"]:
            click.echo(f"📚 Found {len(discovered['chapters'])} chapter files:")
            for chapter_file in discovered["chapters"]:
                click.echo(f"  • {chapter_file}")
        
        if discovered["characters"]:
            click.echo(f"👥 Found {len(discovered['characters'])} character files:")
            for char_file in discovered["characters"]:
                click.echo(f"  • {char_file}")
        
        if discovered["other_files"]:
            click.echo(f"📄 Found {len(discovered['other_files'])} other files:")
            for other_file in discovered["other_files"]:
                click.echo(f"  • {other_file}")
        
        # Import chapters
        imported = project.import_existing_chapters()
        if imported:
            click.echo(f"\n✅ Imported {len(imported)} chapters:")
            for chapter_name in imported:
                click.echo(f"  • {chapter_name}")
            
            # Save updated project
            ctx.obj['project_loader'].save_project(project, project_file)
        else:
            click.echo("\n📭 No new chapters to import")
        
    except Exception as e:
        click.echo(f"❌ Error discovering content: {e}", err=True)
        sys.exit(1)


@project.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def sync(ctx, project_file):
    """Sync project with file system changes"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        # Sync with files
        project.sync_with_files()
        
        # Save updated project
        ctx.obj['project_loader'].save_project(project, project_file)
        
        click.echo("✅ Project synchronized with file system")
        
        # Show updated statistics
        stats = project.get_project_statistics()
        click.echo(f"📊 Total words: {stats['total_words']:,}")
        click.echo(f"📚 Chapters: {stats['total_chapters']}")
        
    except Exception as e:
        click.echo(f"❌ Error syncing project: {e}", err=True)
        sys.exit(1)


@project.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def validate(ctx, project_file):
    """Validate project integrity"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        issues = project.validate_project()
        
        if not issues:
            click.echo("✅ Project validation passed - no issues found")
        else:
            click.echo(f"⚠️  Found {len(issues)} issues:")
            for issue in issues:
                click.echo(f"  • {issue}")
        
    except Exception as e:
        click.echo(f"❌ Error validating project: {e}", err=True)
        sys.exit(1)


@project.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def load(ctx, project_file):
    """Load an existing project"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        click.echo(f"📖 Loaded project: {project.title}")
        click.echo(f"👤 Author: {project.author}")
        click.echo(f"📊 Chapters: {len(project.document.chapters)}")
        click.echo(f"👥 Characters: {len(project.characters.characters)}")
        
    except Exception as e:
        click.echo(f"❌ Error loading project: {e}", err=True)
        sys.exit(1)


@project.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def info(ctx, project_file):
    """Show project information"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        click.echo(f"\n📖 Project: {project.title}")
        click.echo(f"👤 Author: {project.author}")
        click.echo(f"📅 Created: {project.created_at.strftime('%Y-%m-%d %H:%M')}")
        click.echo(f"📝 Modified: {project.modified_at.strftime('%Y-%m-%d %H:%M')}")
        click.echo(f"📊 Total words: {project.document.word_count}")
        click.echo(f"📚 Chapters: {len(project.document.chapters)}")
        click.echo(f"👥 Characters: {len(project.characters.characters)}")
        
        if project.metadata:
            click.echo(f"\n📋 Metadata:")
            for key, value in project.metadata.items():
                click.echo(f"  {key}: {value}")
                
    except Exception as e:
        click.echo(f"❌ Error getting project info: {e}", err=True)
        sys.exit(1)


# Character Commands
@character.command()
@click.option('--project', type=click.Path(exists=True), help='Project file path')
@click.option('--name', prompt='Character name', help='Name of the character')
@click.option('--age', prompt='Character age', type=int, help='Age of the character')
@click.option('--role', type=click.Choice(['PROTAGONIST', 'ANTAGONIST', 'SUPPORTING', 'MINOR']), 
              default='SUPPORTING', help='Character role')
@click.option('--description', prompt='Character description', help='Description of the character')
@click.option('--backstory', help='Character backstory')
@click.option('--traits', help='Character traits (comma-separated)')
@click.option('--goals', help='Character goals (comma-separated)')
@click.pass_context
def create(ctx, project, name, age, role, description, backstory, traits, goals):
    """Create a new character"""
    try:
        # Create character
        character = Character(
            name=name,
            age=age,
            role=CharacterRole[role],
            description=description,
            backstory=backstory or ""
        )
        
        # Add traits
        if traits:
            character.traits.extend([trait.strip() for trait in traits.split(',')])
        
        # Add goals
        if goals:
            character.goals.extend([goal.strip() for goal in goals.split(',')])
        
        # If project specified, add to project
        if project:
            project_obj = ctx.obj['project_loader'].load_project(project)
            project_obj.characters.add_character(character)
            ctx.obj['project_loader'].save_project(project_obj, project)
            click.echo(f"✅ Created character '{name}' and added to project")
        else:
            # Save as standalone character file
            char_file = Path(f"{name.lower().replace(' ', '_')}.json")
            ctx.obj['file_handler'].write_json(char_file, character.to_dict())
            click.echo(f"✅ Created character '{name}' saved to {char_file}")
            
    except Exception as e:
        click.echo(f"❌ Error creating character: {e}", err=True)
        sys.exit(1)


@character.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def list(ctx, project_file):
    """List all characters in a project"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        if not project.characters.characters:
            click.echo("📭 No characters found in project")
            return
        
        click.echo(f"\n👥 Characters in '{project.title}':")
        click.echo("=" * 50)
        
        for character in project.characters.characters.values():
            click.echo(f"\n👤 {character.name}")
            click.echo(f"   Age: {character.age}")
            click.echo(f"   Role: {character.role.value}")
            click.echo(f"   Description: {character.description}")
            
            if character.traits:
                click.echo(f"   Traits: {', '.join(character.traits)}")
            
            if character.goals:
                click.echo(f"   Goals: {', '.join(character.goals)}")
                
    except Exception as e:
        click.echo(f"❌ Error listing characters: {e}", err=True)
        sys.exit(1)


@character.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.argument('character_name')
@click.pass_context
def show(ctx, project_file, character_name):
    """Show detailed information about a character"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        character = project.characters.get_character(character_name)
        
        if not character:
            click.echo(f"❌ Character '{character_name}' not found")
            sys.exit(1)
        
        click.echo(f"\n👤 Character: {character.name}")
        click.echo("=" * 50)
        click.echo(f"Age: {character.age}")
        click.echo(f"Role: {character.role.value}")
        click.echo(f"Description: {character.description}")
        
        if character.backstory:
            click.echo(f"\nBackstory:")
            click.echo(character.backstory)
        
        if character.traits:
            click.echo(f"\nTraits:")
            for trait in character.traits:
                click.echo(f"  • {trait}")
        
        if character.goals:
            click.echo(f"\nGoals:")
            for goal in character.goals:
                click.echo(f"  • {goal}")
        
        if character.relationships:
            click.echo(f"\nRelationships:")
            for rel_name, relationship in character.relationships.items():
                click.echo(f"  • {rel_name}: {relationship}")
                
    except Exception as e:
        click.echo(f"❌ Error showing character: {e}", err=True)
        sys.exit(1)


@character.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.argument('character_name')
@click.option('--name', help='New character name')
@click.option('--age', type=int, help='New character age')
@click.option('--role', type=click.Choice(['PROTAGONIST', 'ANTAGONIST', 'SUPPORTING', 'MINOR']), help='New character role')
@click.option('--description', help='New character description')
@click.option('--backstory', help='New character backstory')
@click.option('--add-trait', help='Add a trait')
@click.option('--add-goal', help='Add a goal')
@click.pass_context
def edit(ctx, project_file, character_name, name, age, role, description, backstory, add_trait, add_goal):
    """Edit an existing character"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        character = project.characters.get_character(character_name)
        
        if not character:
            click.echo(f"❌ Character '{character_name}' not found")
            sys.exit(1)
        
        # Update fields
        if name:
            old_name = character.name
            character.name = name
            # Update in character manager
            project.characters.characters[name] = project.characters.characters.pop(old_name)
        
        if age is not None:
            character.age = age
        
        if role:
            character.role = CharacterRole[role]
        
        if description:
            character.description = description
        
        if backstory:
            character.backstory = backstory
        
        if add_trait:
            character.traits.append(add_trait)
        
        if add_goal:
            character.goals.append(add_goal)
        
        # Save project
        ctx.obj['project_loader'].save_project(project, project_file)
        click.echo(f"✅ Updated character '{character.name}'")
        
    except Exception as e:
        click.echo(f"❌ Error editing character: {e}", err=True)
        sys.exit(1)


@character.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.argument('character_name')
@click.confirmation_option(prompt='Are you sure you want to delete this character?')
@click.pass_context
def delete(ctx, project_file, character_name):
    """Delete a character from the project"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        if character_name not in project.characters.characters:
            click.echo(f"❌ Character '{character_name}' not found")
            sys.exit(1)
        
        project.characters.remove_character(character_name)
        ctx.obj['project_loader'].save_project(project, project_file)
        click.echo(f"✅ Deleted character '{character_name}'")
        
    except Exception as e:
        click.echo(f"❌ Error deleting character: {e}", err=True)
        sys.exit(1)


# Chapter Commands
@chapter.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.option('--number', prompt='Chapter number', type=int, help='Chapter number')
@click.option('--title', prompt='Chapter title', help='Chapter title')
@click.option('--content', help='Chapter content (or provide via editor)')
@click.pass_context
def create(ctx, project_file, number, title, content):
    """Create a new chapter with file-based storage"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        # Check if chapter already exists
        if number in project.document.chapters:
            click.echo(f"❌ Chapter {number} already exists")
            sys.exit(1)
        
        # Normalize the title
        normalized_title = normalize_chapter_title(title)
        
        # Get content from editor if not provided
        if not content:
            content = click.edit(f"\n# {normalized_title}\n\nWrite your chapter content here...\n")
            if not content:
                content = "Chapter content to be added."
            
            # Remove the header from editor content if present
            lines = content.split('\n')
            if lines and lines[0].startswith(f'# {normalized_title}'):
                content = '\n'.join(lines[2:]).strip()
        
        # Create chapter using the new file-based system
        success = project.create_chapter(number, normalized_title, content.strip())
        
        if success:
            # Save updated project
            ctx.obj['project_loader'].save_project(project, project_file)
            
            # Get chapter info for display
            chapter = project.document.get_chapter(number)
            file_path = chapter.get_file_path(project.project_path)
            
            click.echo(f"✅ Created {normalized_title}")
            click.echo(f"📝 Word count: {chapter.word_count}")
            click.echo(f"📁 File: {file_path.relative_to(project.project_path)}")
        else:
            click.echo(f"❌ Failed to create chapter")
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"❌ Error creating chapter: {e}", err=True)
        sys.exit(1)


@chapter.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.argument('chapter_number', type=int)
@click.option('--content', help='New chapter content')
@click.pass_context
def edit(ctx, project_file, chapter_number, content):
    """Edit an existing chapter"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        chapter = project.document.get_chapter(chapter_number)
        if not chapter:
            click.echo(f"❌ Chapter {chapter_number} not found")
            sys.exit(1)
        
        # Get current content if no new content provided
        if not content:
            current_content = project.get_chapter_content(chapter_number)
            content = click.edit(f"# {chapter.title}\n\n{current_content}")
            
            if not content:
                click.echo("❌ No content provided")
                sys.exit(1)
            
            # Remove the header from editor content
            lines = content.split('\n')
            if lines and lines[0].startswith(f'# {chapter.title}'):
                content = '\n'.join(lines[2:]).strip()
        
        # Update chapter content
        success = project.update_chapter_content(chapter_number, content.strip())
        
        if success:
            # Save updated project
            ctx.obj['project_loader'].save_project(project, project_file)
            
            # Get updated chapter info
            chapter = project.document.get_chapter(chapter_number)
            click.echo(f"✅ Updated {chapter.title}")
            click.echo(f"📝 Word count: {chapter.word_count}")
        else:
            click.echo(f"❌ Failed to update chapter")
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"❌ Error editing chapter: {e}", err=True)
        sys.exit(1)


@chapter.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.argument('chapter_number', type=int)
@click.pass_context
def show(ctx, project_file, chapter_number):
    """Show chapter content and metadata"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        chapter = project.document.get_chapter(chapter_number)
        if not chapter:
            click.echo(f"❌ Chapter {chapter_number} not found")
            sys.exit(1)
        
        # Sync with file first
        chapter.sync_with_file(project.project_path)
        
        click.echo(f"\n📖 {chapter.title}")
        click.echo("=" * (len(chapter.title) + 4))
        click.echo(f"Number: {chapter.number}")
        click.echo(f"Words: {chapter.word_count:,}")
        click.echo(f"Status: {chapter.status}")
        
        if chapter.file_path:
            file_path = chapter.get_file_path(project.project_path)
            click.echo(f"File: {chapter.file_path}")
            click.echo(f"File exists: {'✅' if file_path and file_path.exists() else '❌'}")
            
            if chapter.file_modified_at:
                click.echo(f"File modified: {chapter.file_modified_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if chapter.summary:
            click.echo(f"\nSummary: {chapter.summary}")
        
        if chapter.notes:
            click.echo(f"\nNotes: {chapter.notes}")
        
        # Show content preview
        content = project.get_chapter_content(chapter_number)
        if content:
            preview = content[:200] + "..." if len(content) > 200 else content
            click.echo(f"\nContent preview:\n{preview}")
        
    except Exception as e:
        click.echo(f"❌ Error showing chapter: {e}", err=True)
        sys.exit(1)


@chapter.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def list(ctx, project_file):
    """List all chapters in a project"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        if not project.document.chapters:
            click.echo("📭 No chapters found in project")
            return
        
        click.echo(f"\n📚 Chapters in '{project.title}':")
        click.echo("=" * 60)
        
        total_words = 0
        for number in sorted(project.document.chapters.keys()):
            chapter = project.document.chapters[number]
            total_words += chapter.word_count
            click.echo(f"Chapter {chapter.number:2d}: {chapter.title:<30} ({chapter.word_count:4d} words)")
        
        click.echo("=" * 60)
        click.echo(f"Total: {len(project.document.chapters)} chapters, {total_words} words")
        
    except Exception as e:
        click.echo(f"❌ Error listing chapters: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def status(ctx, project_file):
    """Show project status and statistics"""
    try:
        # Handle directory vs file path
        project_path = Path(project_file)
        
        if project_path.is_dir():
            # Look for project.json in the directory
            project_file_path = project_path / 'project.json'
            if not project_file_path.exists():
                click.echo(f"❌ No project.json found in {project_path}")
                click.echo("   Make sure you're in a project directory or specify the project file directly")
                sys.exit(1)
        else:
            # Use the file directly
            project_file_path = project_path
        
        project = ctx.obj['project_loader'].load_project(project_file_path)
        
        # Sync with files to get latest statistics
        project.sync_with_files()
        
        # Get comprehensive statistics
        stats = project.get_project_statistics()
        
        click.echo(f"\n📊 Project Status: {stats['title']}")
        click.echo("=" * 50)
        
        # Basic info
        click.echo(f"📖 Title: {stats['title']}")
        click.echo(f"👤 Author: {stats['author']}")
        click.echo(f"📅 Created: {stats['created_at'].strftime('%Y-%m-%d')}")
        click.echo(f"📝 Last Modified: {stats['modified_at'].strftime('%Y-%m-%d %H:%M')}")
        
        # Progress stats
        click.echo(f"🎯 Target Word Count: {stats['target_words']:,}")
        click.echo(f"📊 Current Word Count: {stats['total_words']:,}")
        click.echo(f"📈 Progress: {stats['progress_percentage']:.1f}%")
        
        # Chapter stats
        click.echo(f"📚 Total Chapters: {stats['total_chapters']}")
        if stats['average_chapter_length'] > 0:
            click.echo(f"📄 Average Chapter Length: {stats['average_chapter_length']:,} words")
        
        # Character stats
        click.echo(f"👥 Total Characters: {stats['characters_count']}")
        
        # Missing chapters
        if stats['missing_chapters']:
            click.echo(f"⚠️  Missing Chapters: {', '.join(map(str, stats['missing_chapters']))}")
        
        # File-based chapter info
        chapters_with_files = sum(1 for ch in stats['chapters'] if ch['has_file'])
        if chapters_with_files != stats['total_chapters']:
            click.echo(f"📁 Chapters with files: {chapters_with_files}/{stats['total_chapters']}")
        
        # Recent activity
        if stats['chapters']:
            recent_chapters = sorted(stats['chapters'], key=lambda x: x['words'], reverse=True)[:3]
            click.echo(f"\n📝 Largest Chapters:")
            for chapter in recent_chapters:
                status_icon = "📁" if chapter['has_file'] else "❌"
                click.echo(f"  {status_icon} {chapter['title']} ({chapter['words']:,} words)")
        
    except Exception as e:
        click.echo(f"❌ Error getting project status: {e}", err=True)
        sys.exit(1)


@cli.group()
def ai():
    """AI-assisted writing commands"""
    pass


# AI Generation Commands
@ai.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.option('--number', prompt='Chapter number', type=int, help='Chapter number to generate')
@click.option('--title', help='Chapter title (auto-generated if not provided)')
@click.option('--outline-section', help='Specific outline section for this chapter')
@click.option('--word-count', default=2000, help='Target word count')
@click.option('--context-chapters', help='Comma-separated list of chapter numbers to use as context')
@click.pass_context
def generate_chapter(ctx, project_file, number, title, outline_section, word_count, context_chapters):
    """Generate a new chapter using AI"""
    import asyncio
    from ..ai.claude_client import ClaudeClient
    from ..ai.content_generator import ContentGenerator
    
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        # Check if chapter already exists
        if number in project.document.chapters:
            click.echo(f"❌ Chapter {number} already exists")
            sys.exit(1)
        
        # Parse context chapters
        context_chapter_list = None
        if context_chapters:
            try:
                context_chapter_list = [int(x.strip()) for x in context_chapters.split(',')]
            except ValueError:
                click.echo("❌ Invalid context chapters format. Use: 1,2,3")
                sys.exit(1)
        
        # Initialize AI components
        claude_client = ClaudeClient()
        generator = ContentGenerator(claude_client)
        
        click.echo(f"🤖 Generating Chapter {number}...")
        if title:
            click.echo(f"📝 Title: {title}")
        click.echo(f"🎯 Target: {word_count:,} words")
        
        # Generate chapter
        async def generate():
            return await generator.generate_and_save_chapter(
                project=project,
                chapter_number=number,
                title=title,
                outline_section=outline_section or "",
                word_count_target=word_count,
                context_chapters=context_chapter_list
            )
        
        success = asyncio.run(generate())
        
        if success:
            # Save project and show results
            ctx.obj['project_loader'].save_project(project, project_file)
            
            chapter = project.document.get_chapter(number)
            click.echo(f"✅ Generated {chapter.title}")
            click.echo(f"📝 Word count: {chapter.word_count:,}")
            click.echo(f"📁 File: {chapter.file_path}")
        else:
            click.echo("❌ Failed to generate chapter")
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"❌ Error generating chapter: {e}", err=True)
        sys.exit(1)


@ai.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.option('--chapter', prompt='Chapter number', type=int, help='Chapter number to expand')
@click.option('--notes', help='Specific expansion notes or direction')
@click.option('--target-words', default=500, help='Target number of words to add')
@click.pass_context
def expand_chapter(ctx, project_file, chapter, notes, target_words):
    """Expand an existing chapter with AI-generated content"""
    import asyncio
    from ..ai.claude_client import ClaudeClient
    from ..ai.content_generator import ContentGenerator
    
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        # Check if chapter exists
        if chapter not in project.document.chapters:
            click.echo(f"❌ Chapter {chapter} not found")
            sys.exit(1)
        
        chapter_obj = project.document.get_chapter(chapter)
        
        # Initialize AI components
        claude_client = ClaudeClient()
        generator = ContentGenerator(claude_client)
        
        click.echo(f"🤖 Expanding {chapter_obj.title}...")
        click.echo(f"🎯 Adding ~{target_words:,} words")
        if notes:
            click.echo(f"📝 Notes: {notes}")
        
        # Expand chapter
        async def expand():
            return await generator.expand_chapter(
                project=project,
                chapter_number=chapter,
                expansion_notes=notes or "",
                target_expansion=target_words
            )
        
        expansion_content = asyncio.run(expand())
        
        if expansion_content:
            # Get current content and append expansion
            current_content = project.get_chapter_content(chapter)
            new_content = current_content + "\n\n" + expansion_content
            
            # Update chapter
            success = project.update_chapter_content(chapter, new_content)
            
            if success:
                ctx.obj['project_loader'].save_project(project, project_file)
                
                updated_chapter = project.document.get_chapter(chapter)
                words_added = updated_chapter.word_count - chapter_obj.word_count
                
                click.echo(f"✅ Expanded {chapter_obj.title}")
                click.echo(f"📝 Words added: {words_added:,}")
                click.echo(f"📊 New total: {updated_chapter.word_count:,} words")
            else:
                click.echo("❌ Failed to save expanded content")
                sys.exit(1)
        else:
            click.echo("❌ Failed to generate expansion")
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"❌ Error expanding chapter: {e}", err=True)
        sys.exit(1)


@ai.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.option('--chapter', prompt='Chapter number', type=int, help='Chapter number to analyze')
@click.option('--focus', multiple=True, help='Focus areas: pacing, dialogue, character_development, continuity')
@click.pass_context
def analyze_chapter(ctx, project_file, chapter, focus):
    """Analyze a chapter and get AI improvement suggestions"""
    import asyncio
    from ..ai.claude_client import ClaudeClient
    from ..ai.content_generator import ContentGenerator
    
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        # Check if chapter exists
        if chapter not in project.document.chapters:
            click.echo(f"❌ Chapter {chapter} not found")
            sys.exit(1)
        
        chapter_obj = project.document.get_chapter(chapter)
        
        # Default focus areas if none specified
        focus_areas = list(focus) if focus else ["pacing", "dialogue", "character_development", "continuity"]
        
        # Initialize AI components
        claude_client = ClaudeClient()
        generator = ContentGenerator(claude_client)
        
        click.echo(f"🤖 Analyzing {chapter_obj.title}...")
        click.echo(f"🔍 Focus areas: {', '.join(focus_areas)}")
        
        # Analyze chapter
        async def analyze():
            return await generator.improve_chapter(
                project=project,
                chapter_number=chapter,
                focus_areas=focus_areas
            )
        
        analysis = asyncio.run(analyze())
        
        if analysis:
            click.echo(f"\n📊 Analysis Results for {chapter_obj.title}")
            click.echo("=" * 50)
            
            if "overall_assessment" in analysis:
                click.echo(f"📝 Overall: {analysis['overall_assessment']}")
            
            if analysis.get("strengths"):
                click.echo(f"\n✅ Strengths:")
                for strength in analysis["strengths"]:
                    click.echo(f"  • {strength}")
            
            if analysis.get("areas_for_improvement"):
                click.echo(f"\n⚠️  Areas for Improvement:")
                for issue in analysis["areas_for_improvement"]:
                    click.echo(f"  • {issue}")
            
            if analysis.get("specific_suggestions"):
                click.echo(f"\n💡 Specific Suggestions:")
                for suggestion in analysis["specific_suggestions"]:
                    priority = suggestion.get("priority", "medium")
                    area = suggestion.get("area", "general")
                    text = suggestion.get("suggestion", str(suggestion))
                    priority_icon = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
                    click.echo(f"  {priority_icon} [{area}] {text}")
            
            if analysis.get("continuity_issues"):
                click.echo(f"\n🔗 Continuity Issues:")
                for issue in analysis["continuity_issues"]:
                    click.echo(f"  • {issue}")
            
            if analysis.get("style_notes"):
                click.echo(f"\n🎨 Style Notes: {analysis['style_notes']}")
            
            # If it's just raw text analysis
            if "analysis_text" in analysis and not any(k in analysis for k in ["strengths", "areas_for_improvement"]):
                click.echo(f"\n{analysis['analysis_text']}")
        else:
            click.echo("❌ Failed to analyze chapter")
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"❌ Error analyzing chapter: {e}", err=True)
        sys.exit(1)


@ai.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.option('--chapters', help='Comma-separated chapter numbers to check (default: all)')
@click.pass_context
def check_continuity(ctx, project_file, chapters):
    """Check continuity across chapters"""
    import asyncio
    from ..ai.claude_client import ClaudeClient
    from ..ai.content_generator import ContentGenerator
    
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        # Parse chapter range
        chapter_range = None
        if chapters:
            try:
                chapter_range = [int(x.strip()) for x in chapters.split(',')]
            except ValueError:
                click.echo("❌ Invalid chapters format. Use: 1,2,3")
                sys.exit(1)
        
        # Initialize AI components
        claude_client = ClaudeClient()
        generator = ContentGenerator(claude_client)
        
        if chapter_range:
            click.echo(f"🤖 Checking continuity for chapters: {', '.join(map(str, chapter_range))}")
        else:
            click.echo(f"🤖 Checking continuity across all chapters")
        
        # Check continuity
        async def check():
            return await generator.check_continuity(
                project=project,
                chapter_range=chapter_range
            )
        
        report = asyncio.run(check())
        
        if report:
            click.echo(f"\n🔗 Continuity Report")
            click.echo("=" * 30)
            
            if "continuity_score" in report:
                score = report["continuity_score"]
                click.echo(f"📊 Overall Score: {score}/10")
            
            if report.get("issues_found"):
                click.echo(f"\n⚠️  Issues Found:")
                for issue in report["issues_found"]:
                    if isinstance(issue, dict):
                        issue_type = issue.get("type", "unknown")
                        chapter_num = issue.get("chapter", "?")
                        description = issue.get("description", str(issue))
                        severity = issue.get("severity", "medium")
                        severity_icon = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
                        click.echo(f"  {severity_icon} Chapter {chapter_num} ({issue_type}): {description}")
                    else:
                        click.echo(f"  • {issue}")
            
            if report.get("suggestions"):
                click.echo(f"\n💡 Suggestions:")
                for suggestion in report["suggestions"]:
                    click.echo(f"  • {suggestion}")
            
            if report.get("character_consistency"):
                click.echo(f"\n👥 Character Consistency:")
                for char_name, assessment in report["character_consistency"].items():
                    click.echo(f"  • {char_name}: {assessment}")
            
            if report.get("timeline_assessment"):
                click.echo(f"\n⏰ Timeline: {report['timeline_assessment']}")
            
            # Raw analysis fallback
            if "analysis_text" in report and not report.get("issues_found"):
                click.echo(f"\n{report['analysis_text']}")
        else:
            click.echo("❌ Failed to check continuity")
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"❌ Error checking continuity: {e}", err=True)
        sys.exit(1)


@ai.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.option('--num-suggestions', default=3, help='Number of chapter suggestions to generate')
@click.pass_context
def suggest_next(ctx, project_file, num_suggestions):
    """Get AI suggestions for next chapters to write"""
    import asyncio
    from ..ai.claude_client import ClaudeClient
    from ..ai.content_generator import ContentGenerator
    
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        # Initialize AI components
        claude_client = ClaudeClient()
        generator = ContentGenerator(claude_client)
        
        click.echo(f"🤖 Generating {num_suggestions} chapter suggestions...")
        
        # Get suggestions
        async def suggest():
            return await generator.suggest_next_chapters(
                project=project,
                num_suggestions=num_suggestions
            )
        
        suggestions = asyncio.run(suggest())
        
        if suggestions:
            click.echo(f"\n💡 Chapter Suggestions")
            click.echo("=" * 30)
            
            for i, suggestion in enumerate(suggestions, 1):
                if isinstance(suggestion, dict):
                    chapter_num = suggestion.get("chapter_number", "?")
                    title = suggestion.get("title", "Untitled")
                    summary = suggestion.get("summary", "No summary")
                    word_count = suggestion.get("estimated_word_count", "Unknown")
                    
                    click.echo(f"\n📖 Suggestion {i}: Chapter {chapter_num}")
                    click.echo(f"   Title: {title}")
                    click.echo(f"   Summary: {summary}")
                    
                    if suggestion.get("key_events"):
                        click.echo(f"   Key Events: {', '.join(suggestion['key_events'])}")
                    
                    if suggestion.get("character_focus"):
                        click.echo(f"   Character Focus: {suggestion['character_focus']}")
                    
                    if suggestion.get("plot_advancement"):
                        click.echo(f"   Plot Advancement: {suggestion['plot_advancement']}")
                    
                    click.echo(f"   Est. Word Count: {word_count}")
                else:
                    click.echo(f"\n📖 Suggestion {i}: {suggestion}")
        else:
            click.echo("❌ Failed to generate suggestions")
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"❌ Error generating suggestions: {e}", err=True)
        sys.exit(1)
def export(ctx, project_file, output_file, export_format):
    """Export project to various formats"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        if export_format == 'markdown':
            content = project.document.export_text()
            # Convert to markdown format
            markdown_content = f"# {project.document.title}\n\n"
            markdown_content += f"**Author:** {project.document.author}\n\n"
            
            if project.document.synopsis:
                markdown_content += f"## Synopsis\n\n{project.document.synopsis}\n\n"
            
            for chapter in project.document.get_chapters_sorted():
                markdown_content += f"## {chapter.title}\n\n"
                markdown_content += f"{chapter.content}\n\n"
            
            ctx.obj['file_handler'].write_file(output_file, markdown_content)
            
        elif export_format == 'text':
            content = project.document.export_text()
            ctx.obj['file_handler'].write_file(output_file, content)
            
        elif export_format == 'docx':
            # Use the file handler's export functionality
            ctx.obj['file_handler'].export_chapters_to_file(
                project.document.chapters, output_file, 'docx'
            )
        
        click.echo(f"✅ Exported to {output_file} ({export_format} format)")
        
    except Exception as e:
        click.echo(f"❌ Error exporting project: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.argument('query')
@click.pass_context
def search(ctx, project_file, query):
    """Search for text across all chapters"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        results = project.document.search_content(query)
        
        if not results:
            click.echo(f"🔍 No results found for '{query}'")
            return
        
        click.echo(f"🔍 Found {len(results)} result(s) for '{query}':")
        click.echo("=" * 50)
        
        for result in results:
            click.echo(f"\n📖 {result['chapter_title']}")
            click.echo(f"📍 Position: {result['position']}")
            click.echo(f"📝 Context: ...{result['context']}...")
            
    except Exception as e:
        click.echo(f"❌ Error searching: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def wordcount(ctx, project_file):
    """Show detailed word count statistics"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        click.echo(f"\n📊 Word Count Report: {project.title}")
        click.echo("=" * 60)
        
        total_words = 0
        chapters = project.document.get_chapters_sorted()
        
        for chapter in chapters:
            words = chapter.get_total_word_count()
            total_words += words
            click.echo(f"{chapter.title:<40} {words:>8,} words")
        
        click.echo("=" * 60)
        click.echo(f"{'Total':<40} {total_words:>8,} words")
        
        # Progress toward target
        target = project.document.target_word_count
        progress = (total_words / target) * 100 if target > 0 else 0
        remaining = max(0, target - total_words)
        
        click.echo(f"{'Target':<40} {target:>8,} words")
        click.echo(f"{'Progress':<40} {progress:>7.1f}%")
        click.echo(f"{'Remaining':<40} {remaining:>8,} words")
        
        if chapters:
            avg_chapter = total_words // len(chapters)
            click.echo(f"{'Average per chapter':<40} {avg_chapter:>8,} words")
        
    except Exception as e:
        click.echo(f"❌ Error calculating word count: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def import_text(ctx, file_path, project_file):
    """Import text from a file into the project"""
    try:
        from ..core.document import Chapter, normalize_chapter_title
        
        project = ctx.obj['project_loader'].load_project(project_file)
        content = ctx.obj['file_handler'].read_file(file_path)
        
        # Enhanced chapter detection with title normalization
        import re
        
        # Split by various chapter patterns
        chapter_patterns = [
            r'\n(?=Chapter\s+\w+(?:-\w+)?[:\.])',  # "Chapter One:", "Chapter 1."
            r'\n(?=Ch\.?\s+\w+(?:-\w+)?[:\.])',    # "Ch. One:", "Ch 1."
            r'\n(?=\d+\.)',                        # "1.", "2."
        ]
        
        chapters = [content]  # Start with full content
        
        for pattern in chapter_patterns:
            new_chapters = []
            for chapter_content in chapters:
                splits = re.split(pattern, chapter_content, flags=re.MULTILINE)
                new_chapters.extend(splits)
            chapters = new_chapters
            
        imported_count = 0
        for i, chapter_content in enumerate(chapters, 1):
            if chapter_content.strip():
                # Extract title from first line
                lines = chapter_content.strip().split('\n')
                first_line = lines[0].strip() if lines else f"Imported Chapter {i}"
                
                # Normalize the title
                if re.match(r'(Chapter|Ch\.?)\s+', first_line, re.IGNORECASE):
                    title = normalize_chapter_title(first_line)
                    content_text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
                else:
                    title = f"Chapter {i}"
                    content_text = chapter_content.strip()
                
                chapter = Chapter(number=i, title=title, content=content_text)
                project.document.add_chapter(chapter)
                imported_count += 1
        
        ctx.obj['project_loader'].save_project(project, project_file)
        click.echo(f"✅ Imported {imported_count} chapters from {file_path}")
        
    except Exception as e:
        click.echo(f"❌ Error importing text: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point for the CLI"""
    cli()


if __name__ == '__main__':
    main()