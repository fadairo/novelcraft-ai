# NovelCraft AI 📚✨

An AI-assisted novel writing application that helps authors create, edit, and refine their manuscripts using Claude AI. Built with the Snowflake Method and advanced consistency checking.

[![CI](https://github.com/yourusername/novelcraft-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/novelcraft-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## 🎯 Features

- **AI-Powered Content Generation**: Generate chapters, scenes, and dialogue using Claude AI
- **Snowflake Method Integration**: Structured story development from concept to manuscript
- **Consistency Checking**: Automated detection of plot holes, character inconsistencies, and timeline issues
- **Style Matching**: AI learns and maintains your unique writing voice
- **Multi-Format Support**: Works with Markdown, DOCX, TXT, and more
- **Project Management**: Organized workspace for manuscripts, characters, and outlines
- **Command-Line Interface**: Powerful CLI for streamlined workflow

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/novelcraft-ai.git
cd novelcraft-ai

# Install the package
pip install -e .

# Set up your Claude AI API key
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Create Your First Project

```bash
# Initialize a new novel project
novelcraft init my-novel --title "My Amazing Novel" --author "Your Name"

# Navigate to your project
cd my-novel

# Edit your synopsis, outline, and characters
# Then generate your first chapter
novelcraft generate . --chapter 1

# Check for consistency issues
novelcraft check . manuscripts/chapter_1.md
```

### Using the Snowflake Method

```bash
# Start with a concept
novelcraft snowflake . "A time traveler accidentally changes history"

# Expand through the levels
novelcraft expand . --level sentence
novelcraft expand . --level paragraph
novelcraft expand . --level page
novelcraft expand . --level chapter

# Generate content from your expanded outline
novelcraft generate . --from-outline
```

## 📖 Documentation

### Project Structure

When you create a new project, NovelCraft sets up this structure:

```
my-novel/
├── project.json          # Project configuration
├── synopsis.md          # Story synopsis
├── outline.md           # Chapter outlines
├── characters.md        # Character profiles
├── manuscripts/         # Your manuscript files
├── generated/          # AI-generated content
└── snowflake.json      # Snowflake Method data
```

### Core Commands

#### Project Management

- `novelcraft init <path>` - Create a new project
- `novelcraft status <path>` - Show project statistics

#### Content Generation

- `novelcraft generate <path>` - Generate missing chapters
- `novelcraft generate <path> --chapter N` - Generate specific chapter
- `novelcraft generate <path> --from-outline` - Generate from outline

#### Snowflake Method

- `novelcraft snowflake <path> "concept"` - Start with a concept
- `novelcraft expand <path> --level <level>` - Expand to next level

#### Quality Control

- `novelcraft check <path> <file>` - Check consistency and continuity

### Configuration

Create a `.novelcraft.yml` file in your project for custom settings:

```yaml
ai:
  model: "claude-3-sonnet-20240229"
  temperature: 0.7
  max_tokens: 4000

generation:
  default_word_count: 2000
  style_analysis: true
  consistency_checking: true

snowflake:
  auto_expand: false
  character_limit: 5
```

## 🛠️ Development

### Setting Up Development Environment

```bash
# Clone and install in development mode
git clone https://github.com/yourusername/novelcraft-ai.git
cd novelcraft-ai
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check novelcraft/
black novelcraft/

# Type checking
mypy novelcraft/
```

### Project Architecture

```
novelcraft/
├── core/           # Core domain models (Document, Character, Project)
├── ai/            # AI integration (Claude client, generators)
├── editor/        # Editing tools (consistency checker, style analyzer)
├── io/           # File handling (readers, writers, loaders)
└── cli/          # Command-line interface
```

### Key Components

- **Document**: Manages chapters, scenes, and manuscript content
- **Character**: Handles character profiles and relationships
- **SnowflakeMethod**: Implements the 10-step story development process
- **ClaudeClient**: Interfaces with Anthropic's Claude AI
- **ContentGenerator**: AI-powered content creation
- **ConsistencyChecker**: Automated quality control

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Write tests for new features
- Follow PEP 8 style guidelines
- Add type hints to all functions
- Update documentation for user-facing changes

## 📝 Examples

### Basic Novel Generation

```python
from novelcraft import Project, ClaudeClient, ContentGenerator

# Set up the project
project = Project(title="My Novel", author="Me")

# Initialize AI
client = ClaudeClient()
generator = ContentGenerator(client)

# Generate a chapter
chapter = await generator.generate_chapter(
    chapter_number=1,
    title="The Beginning",
    outline="Hero discovers their power",
    synopsis="A young person finds they can control time",
    character_info="Alex: 16-year-old protagonist, curious and brave"
)
```

### Advanced Workflow

```python
from novelcraft import SnowflakeMethod, ConsistencyChecker

# Develop story using Snowflake Method
snowflake = SnowflakeMethod("Time travel causes paradoxes")
await snowflake.expand_to_paragraph(client)
await snowflake.develop_characters(client)

# Check consistency
checker = ConsistencyChecker(client)
issues = await checker.check_consistency(
    manuscript_text,
    character_profiles,
    story_bible
)
```

## 🔧 API Reference

See our [API Documentation](docs/api.md) for detailed information about classes and methods.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Randy Ingermanson for the Snowflake Method
- Anthropic for Claude AI
- The open-source community for excellent Python tools

## 📞 Support

- 📧 Email: support@novelcraft.ai
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/novelcraft-ai/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/novelcraft-ai/discussions)

---

**Happy Writing! 📖✨**
