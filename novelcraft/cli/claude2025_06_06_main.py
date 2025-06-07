"""Main CLI entry point for NovelCraft AI with file-based architecture."""

import click
import json
import sys
import subprocess
import re
from pathlib import Path
from typing import Optional
from collections import Counter

try:
    import yaml
except ImportError:
    yaml = None

from ..core.project import Project
from ..core.character import Character, CharacterManager, CharacterRole
from ..core.document import normalize_chapter_title, ChapterReference, Chapter
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


@project.command('auto-populate')
@click.option('--directory', type=click.Path(exists=True), help='Directory to scan for content')
@click.option('--recursive', is_flag=True, help='Recursively scan subdirectories')
@click.option('--auto-characters', is_flag=True, help='Auto-detect character names from content')
@click.pass_context
def auto_populate_cmd(ctx, directory, recursive, auto_characters):
    """Auto-populate project from existing content"""
    try:
        # Determine project directory
        if directory:
            project_dir = Path(directory)
        else:
            project_dir = Path.cwd()
        
        project_file = project_dir / 'project.json'
        click.echo(f"🔍 Auto-populating project from {project_dir}")
        
        # Load or create project
        if project_file.exists():
            project = ctx.obj['project_loader'].load_project(project_file)
            click.echo(f"📖 Found existing project: {project.title}")
        else:
            title = project_dir.name.replace('_', ' ').replace('-', ' ').title()
            author = "Unknown Author"
            project = Project(title=title, author=author, project_path=project_dir)
            click.echo(f"📝 Created new project: {title}")
        
        # Find content files
        content_files = []
        content_extensions = {'.md', '.txt', '.docx', '.rtf', '.html'}
        
        if recursive:
            for file_path in project_dir.rglob('*'):
                if (file_path.is_file() and 
                    file_path.suffix.lower() in content_extensions and
                    not file_path.name.startswith('.') and
                    'project.json' not in file_path.name):
                    content_files.append(file_path)
        else:
            for file_path in project_dir.iterdir():
                if (file_path.is_file() and 
                    file_path.suffix.lower() in content_extensions and
                    not file_path.name.startswith('.')):
                    content_files.append(file_path)
        
        click.echo(f"📄 Found {len(content_files)} content files")
        
        # Look for character files
        character_files = []
        characters_md = project_dir / 'characters.md'
        if characters_md.exists():
            character_files.append(characters_md)
            click.echo(f"👥 Found characters.md")
        
        # Parse character files
        imported_character_count = 0
        for char_file in character_files:
            try:
                characters_data = parse_characters_from_file(char_file)
                for char_data in characters_data:
                    if not project.characters.get_character(char_data['name']):
                        character = Character(
                            name=char_data['name'],
                            age=char_data.get('age', 0),
                            role=char_data.get('role', CharacterRole.MINOR),
                            description=char_data.get('description', ''),
                            backstory=char_data.get('backstory', '')
                        )
                        
                        if char_data.get('traits'):
                            character.traits.extend(char_data['traits'])
                        
                        project.characters.add_character(character)
                        imported_character_count += 1
                        click.echo(f"✅ Imported character: {char_data['name']}")
            except Exception as e:
                click.echo(f"⚠️  Error parsing {char_file}: {e}")
        
        # Remove character files from content files
        content_files = [f for f in content_files if f not in character_files]
        
        # Process chapter files
        imported_chapters = 0
        for file_path in content_files:
            try:
                chapter_info = detect_chapter_info(file_path)
                if chapter_info:
                    success = import_chapter_from_file(project, file_path, chapter_info)
                    if success:
                        imported_chapters += 1
                        click.echo(f"✅ Imported chapter {chapter_info['number']}")
            except Exception as e:
                click.echo(f"⚠️  Skipped {file_path}: {e}")
        
        # Save project
        ctx.obj['project_loader'].save_project(project, project_file)
        
        # Show results
        click.echo("\n✅ Auto-population complete!")
        click.echo("=" * 40)
        click.echo(f"📖 Project: {project.title}")
        click.echo(f"👤 Author: {project.author}")
        click.echo(f"📚 Chapters: {len(project.document.chapters)}")
        click.echo(f"👥 Characters: {len(project.characters.characters)}")
        
        if imported_chapters > 0:
            click.echo(f"📝 Imported: {imported_chapters} new chapters")
        if imported_character_count > 0:
            click.echo(f"👥 Imported: {imported_character_count} new characters")
        
    except Exception as e:
        click.echo(f"❌ Error during auto-population: {e}", err=True)
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
        character = Character(
            name=name,
            age=age,
            role=CharacterRole[role],
            description=description,
            backstory=backstory or ""
        )
        
        if traits:
            character.traits.extend([trait.strip() for trait in traits.split(',')])
        
        if goals:
            character.goals.extend([goal.strip() for goal in goals.split(',')])
        
        if project:
            project_obj = ctx.obj['project_loader'].load_project(project)
            project_obj.characters.add_character(character)
            ctx.obj['project_loader'].save_project(project_obj, project)
            click.echo(f"✅ Created character '{name}' and added to project")
        else:
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
        
        if name:
            old_name = character.name
            character.name = name
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


@character.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.pass_context
def sync(ctx, project_file):
    """Sync characters with their files"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        click.echo("🔄 Character sync functionality not yet implemented")
        click.echo("💡 Use 'novelcraft project auto-populate' to import characters")
        
    except Exception as e:
        click.echo(f"❌ Error syncing characters: {e}", err=True)
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
        
        if number in project.document.chapters:
            click.echo(f"❌ Chapter {number} already exists")
            sys.exit(1)
        
        normalized_title = normalize_chapter_title(title)
        
        if not content:
            content = click.edit(f"\n# {normalized_title}\n\nWrite your chapter content here...\n")
            if not content:
                content = "Chapter content to be added."
            
            lines = content.split('\n')
            if lines and lines[0].startswith(f'# {normalized_title}'):
                content = '\n'.join(lines[2:]).strip()
        
        success = project.create_chapter(number, normalized_title, content.strip())
        
        if success:
            ctx.obj['project_loader'].save_project(project, project_file)
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
        
        if not content:
            current_content = project.get_chapter_content(chapter_number)
            content = click.edit(f"# {chapter.title}\n\n{current_content}")
            
            if not content:
                click.echo("❌ No content provided")
                sys.exit(1)
            
            lines = content.split('\n')
            if lines and lines[0].startswith(f'# {chapter.title}'):
                content = '\n'.join(lines[2:]).strip()
        
        success = project.update_chapter_content(chapter_number, content.strip())
        
        if success:
            ctx.obj['project_loader'].save_project(project, project_file)
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
        project_path = Path(project_file)
        
        if project_path.is_dir():
            project_file_path = project_path / 'project.json'
            if not project_file_path.exists():
                click.echo(f"❌ No project.json found in {project_path}")
                sys.exit(1)
        else:
            project_file_path = project_path
        
        project = ctx.obj['project_loader'].load_project(project_file_path)
        project.sync_with_files()
        
        stats = project.get_project_statistics()
        
        click.echo(f"\n📊 Project Status: {stats['title']}")
        click.echo("=" * 50)
        
        click.echo(f"📖 Title: {stats['title']}")
        click.echo(f"👤 Author: {stats['author']}")
        click.echo(f"📅 Created: {stats['created_at'].strftime('%Y-%m-%d')}")
        click.echo(f"📝 Last Modified: {stats['modified_at'].strftime('%Y-%m-%d %H:%M')}")
        click.echo(f"🎯 Target Word Count: {stats['target_words']:,}")
        click.echo(f"📊 Current Word Count: {stats['total_words']:,}")
        click.echo(f"📈 Progress: {stats['progress_percentage']:.1f}%")
        click.echo(f"📚 Total Chapters: {stats['total_chapters']}")
        
        if stats['average_chapter_length'] > 0:
            click.echo(f"📄 Average Chapter Length: {stats['average_chapter_length']:,} words")
        
        click.echo(f"👥 Total Characters: {stats['characters_count']}")
        
        if stats['missing_chapters']:
            click.echo(f"⚠️  Missing Chapters: {', '.join(map(str, stats['missing_chapters']))}")
        
    except Exception as e:
        click.echo(f"❌ Error getting project status: {e}", err=True)
        sys.exit(1)


@cli.group()
def ai():
    """AI-assisted writing commands"""
    pass


@cli.command()
@click.argument('project_file', type=click.Path(exists=True))
@click.argument('output_file', type=click.Path())
@click.option('--format', 'export_format', type=click.Choice(['text', 'markdown', 'docx']), 
              default='text', help='Export format')
@click.pass_context
def export(ctx, project_file, output_file, export_format):
    """Export project to various formats"""
    try:
        project = ctx.obj['project_loader'].load_project(project_file)
        
        if export_format == 'markdown':
            content = project.document.export_text()
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


# Helper functions
def parse_characters_from_file(file_path):
    """Parse characters from a markdown file"""
    try:
        content = file_path.read_text(encoding='utf-8')
        characters = []
        
        sections = re.split(r'\n## (.+?)\n', content)
        
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                char_name = sections[i].strip()
                char_content = sections[i + 1].strip()
                
                char_data = parse_character_section(char_name, char_content)
                if char_data:
                    characters.append(char_data)
        
        return characters
        
    except Exception as e:
        print(f"Error parsing character file {file_path}: {e}")
        return []


def parse_character_section(name, content):
    """Parse an individual character section"""
    try:
        char_data = {'name': name}
        
        patterns = {
            'age': r'(?:Age|age):\s*(\d+)',
            'role': r'(?:Role|role):\s*([^\n]+)',
            'description': r'(?:Description|description):\s*([^\n]+)',
            'backstory': r'(?:Backstory|backstory):\s*(.*?)(?=\n(?:###|##|$))',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if key == 'age':
                    try:
                        char_data[key] = int(value)
                    except ValueError:
                        char_data[key] = 0
                elif key == 'role':
                    role_mapping = {
                        'protagonist': CharacterRole.PROTAGONIST,
                        'antagonist': CharacterRole.ANTAGONIST,
                        'supporting': CharacterRole.SUPPORTING,
                        'minor': CharacterRole.MINOR
                    }
                    char_data[key] = role_mapping.get(value.lower(), CharacterRole.MINOR)
                else:
                    char_data[key] = value
        
        traits_match = re.search(r'(?:traits|characteristics):(.*?)(?=\n\w+:|$)', content, re.DOTALL | re.IGNORECASE)
        if traits_match:
            traits_text = traits_match.group(1)
            traits = re.findall(r'[-•*]\s*(.+)', traits_text)
            if traits:
                char_data['traits'] = [trait.strip() for trait in traits]
        
        return char_data
        
    except Exception as e:
        print(f"Error parsing character section for {name}: {e}")
        return None


def detect_chapter_info(file_path):
    """Detect if file is a chapter and extract info"""
    try:
        filename = file_path.stem
        
        patterns = [
            r'(?:chapter|ch)[\s_-]*(\d+)(?:[\s_-]+(.+))?',
            r'(\d+)[\s_-]+(.+)',
            r'(\d+)\.?\s*$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return {
                    'number': int(match.group(1)),
                    'title': match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                }
        
        return {
            'number': 1,
            'title': filename
        }
        
    except Exception:
        return None


def import_chapter_from_file(project, file_path, chapter_info):
    """Import a single chapter from a file"""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        title = chapter_info.get('title') or f"Chapter {chapter_info['number']}"
        title = normalize_chapter_title(title)
        
        if chapter_info['number'] in project.document.chapters:
            return False
        
        success = project.create_chapter(
            chapter_info['number'],
            title,
            content
        )
        
        return success
        
    except Exception as e:
        print(f"Error importing {file_path}: {e}")
        return False


def main():
    """Main entry point for the CLI"""
    cli()


if __name__ == '__main__':
    main()