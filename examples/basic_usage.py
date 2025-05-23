"""Basic usage example for NovelCraft AI."""

import asyncio
from novelcraft import Project, ClaudeClient, ContentGenerator


async def main():
    """Example of basic novel generation."""
    
    # Create a project
    project = Project(
        title="The Time Traveler's Dilemma",
        author="Jane Doe"
    )
    
    # Set up AI client (requires ANTHROPIC_API_KEY environment variable)
    client = ClaudeClient()
    generator = ContentGenerator(client)
    
    # Generate a chapter
    chapter_content = await generator.generate_chapter(
        chapter_number=1,
        title="The Discovery",
        outline="Sarah finds the time machine in her grandmother's attic",
        synopsis="A young scientist discovers time travel and must prevent a dystopian future",
        character_info="Sarah: 28-year-old physicist, curious and determined",
        word_count_target=1500
    )
    
    print("Generated Chapter 1:")
    print(chapter_content)


if __name__ == "__main__":
    asyncio.run(main())
