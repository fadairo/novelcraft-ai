# NovelCraft AI

**AI-powered novel writing assistant with file-based architecture**

NovelCraft AI is a comprehensive toolkit for novelists that combines traditional project management with cutting-edge AI assistance. Write, organize, and enhance your novel with the power of Claude AI while maintaining full control over your content in standard Markdown files.

## 🌟 Key Features

- **📁 File-Based Architecture** - Your chapters live as individual `.md` files, not locked in a database
- **🤖 AI-Powered Generation** - Generate new chapters, expand existing content, and get writing suggestions
- **🔍 Intelligent Analysis** - Get detailed feedback on pacing, dialogue, character development, and continuity
- **👥 Character Management** - Track characters, relationships, and development arcs
- **📊 Progress Tracking** - Monitor word counts, chapter completion, and project milestones
- **🔗 Continuity Checking** - AI-powered consistency validation across your entire manuscript
- **📖 Multiple Export Formats** - Export to text, Markdown, or Word documents

## 🚀 Quick Start

### Installation

```bash
pip install -e .
```

### Set Up Your API Key

```bash
# Windows
set ANTHROPIC_API_KEY=your-api-key-here

# Mac/Linux
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Create Your First Project

```bash
# Create a new novel project
novelcraft project create --title "My Novel" --author "Your Name"

# Navigate to your project
cd my_novel

# Check project status
novelcraft status .
```

## 📁 Project Structure

NovelCraft AI organizes your novel with a clean, version-control friendly structure:

```
my_novel/
├── project.json          # Project metadata and chapter references
├── chapters/             # Individual chapter files
│   ├── 00_chapter_0.md   # Prologue or Chapter 0
│   ├── 01_chapter_1.md   # Chapter 1
│   ├── 02_chapter_2.md   # Chapter 2
│   └── ...
├── characters/           # Character development files
├── synopsis.md          # Story synopsis
├── outline.md           # Plot outline
└── characters.md        # Character information
```

## 🤖 AI-Powered Writing

### Generate New Chapters

```bash
# Generate a new chapter based on your outline and existing content
novelcraft ai generate-chapter project.json --number 5 --word-count 2500

# Generate with specific context chapters
novelcraft ai generate-chapter project.json --number 10 --context-chapters 7,8,9

# Generate with custom title and outline section
novelcraft ai generate-chapter project.json --number 15 \
  --title "The Revelation" \
  --outline-section "Henry discovers Elena's true identity"
```

### Expand Existing Content

```bash
# Add 500 words to an existing chapter
novelcraft ai expand-chapter project.json --chapter 8 --target-words 500

# Expand with specific direction
novelcraft ai expand-chapter project.json --chapter 12 \
  --notes "Add more tension between Henry and Tom" \
  --target-words 300
```

### Analyze and Improve

```bash
# Get comprehensive chapter analysis
novelcraft ai analyze-chapter project.json --chapter 5

# Focus on specific areas
novelcraft ai analyze-chapter project.json --chapter 10 \
  --focus pacing --focus dialogue --focus character_development

# Check continuity across chapters
novelcraft ai check-continuity project.json --chapters 15,16,17,18
```

### Get Writing Suggestions

```bash
# Get AI suggestions for your next chapters
novelcraft ai suggest-next project.json --num-suggestions 3
```

## 📚 Project Management

### Working with Chapters

```bash
# Create a new chapter manually
novelcraft chapter create project.json --number 3 --title "The Discovery"

# Edit an existing chapter
novelcraft chapter edit project.json 3

# Show chapter details and content preview
novelcraft chapter show project.json 3

# List all chapters
novelcraft chapter list project.json
```

### Managing Characters

```bash
# Create a new character
novelcraft character create --project project.json \
  --name "Dr. Henry Millbank" \
  --age 71 \
  --role PROTAGONIST \
  --description "Retired historian and former MI6 operative"

# List all characters
novelcraft character list project.json

# Show character details
novelcraft character show project.json "Dr. Henry Millbank"

# Edit character information
novelcraft character edit project.json "Dr. Henry Millbank" \
  --add-trait "Highly analytical" \
  --add-goal "Uncover the truth about Operation Glasshouse"
```

### Project Operations

```bash
# Show comprehensive project status
novelcraft status .

# Discover and import existing chapter files
novelcraft project discover project.json

# Sync project with file system changes
novelcraft project sync project.json

# Validate project integrity
novelcraft project validate project.json

# Export your novel
novelcraft export project.json output.md --format markdown
```

## 📊 Tracking Progress

NovelCraft AI provides detailed insights into your writing progress:

```bash
# View project statistics
novelcraft status .

# Detailed word count breakdown
novelcraft wordcount project.json

# Search across all chapters
novelcraft search project.json "Operation Glasshouse"
```

## 🔄 Importing Existing Work

### From a Single Manuscript

If you have an existing manuscript in Word or text format:

```bash
# Use the provided chapter splitter script
python split_manuscript.py your_manuscript.docx

# Discover and import the generated chapters
novelcraft project discover project.json
```

### From Individual Files

If you already have separate chapter files:

```bash
# Place them in the chapters/ directory
# Then discover and import
novelcraft project discover project.json
```

## 🛠️ Advanced Features

### Continuity Checking

NovelCraft AI can analyze your entire manuscript for consistency issues:

```bash
# Check all chapters for continuity
novelcraft ai check-continuity project.json

# Check specific chapter range
novelcraft ai check-continuity project.json --chapters 10,11,12,13,14
```

### Style Analysis

Get detailed feedback on your writing style and suggestions for improvement:

```bash
# Analyze writing style and get suggestions
novelcraft ai analyze-chapter project.json --chapter 8 \
  --focus pacing --focus dialogue --focus style
```

### Character Development Tracking

Monitor character arcs and relationships across your novel:

```bash
# View character relationships and development
novelcraft character show project.json "Dr. Henry Millbank"

# Track character mentions across chapters
novelcraft search project.json "Henry"
```

## 🔧 Configuration

### Environment Variables

```bash
ANTHROPIC_API_KEY=your-api-key-here    # Required for AI features
NOVELCRAFT_EDITOR=code                 # Your preferred editor
NOVELCRAFT_WORD_TARGET=80000          # Default word count target
```

### Project Settings

Edit your `project.json` to customize:

```json
{
  "title": "Your Novel Title",
  "author": "Your Name",
  "target_word_count": 90000,
  "genre": "Literary Thriller",
  "themes": ["loyalty", "memory", "truth"]
}
```

## 📖 Example Workflow

Here's a complete workflow for starting and developing a novel:

```bash
# 1. Create project
novelcraft project create --title "The Cambridge Cipher" --author "Jane Doe"
cd the_cambridge_cipher

# 2. Set up your story foundation
echo "A retired academic discovers secrets in a library book..." > synopsis.md
echo "# Chapter Outline\n\n## Chapter 1: The Discovery\n..." > outline.md

# 3. Generate your first chapter
novelcraft ai generate-chapter project.json --number 1 --title "The Discovery" --word-count 2000

# 4. Check the results
novelcraft status .

# 5. Analyze and improve
novelcraft ai analyze-chapter project.json --chapter 1

# 6. Generate more chapters
novelcraft ai generate-chapter project.json --number 2 --context-chapters 1

# 7. Check continuity as you go
novelcraft ai check-continuity project.json

# 8. Get suggestions for what to write next
novelcraft ai suggest-next project.json
```

## 🤝 Integration with Other Tools

NovelCraft AI works seamlessly with:

- **Git** - Version control your entire project
- **Any text editor** - Edit chapters in VS Code, Obsidian, or your favorite Markdown editor
- **Backup systems** - All files are standard formats, easy to backup and sync
- **Export tools** - Convert to any format you need for publishing

## 🆘 Troubleshooting

### Common Issues

**"API key not found"**

```bash
# Make sure your API key is set
echo $ANTHROPIC_API_KEY  # Mac/Linux
echo %ANTHROPIC_API_KEY%  # Windows
```

**"Chapter not found"**

```bash
# Sync your project with the file system
novelcraft project sync project.json
```

**"Import failed"**

```bash
# Check file encoding and format
# Use the discovery feature instead
novelcraft project discover project.json
```

### Getting Help

```bash
# General help
novelcraft --help

# Command-specific help
novelcraft ai --help
novelcraft chapter --help
novelcraft character --help
```

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

Built with:

- [Anthropic Claude AI](https://www.anthropic.com/) for intelligent content generation
- [Click](https://click.palletsprojects.com/) for the command-line interface
- [Pydantic](https://pydantic.dev/) for data validation

---

**Ready to revolutionize your novel writing process?**

Start with `novelcraft project create` and let AI help you craft your masterpiece! 📚✨
