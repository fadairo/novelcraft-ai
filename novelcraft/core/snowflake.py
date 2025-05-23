"""
Implementation of the Snowflake Method for novel development.
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio


@dataclass
class CharacterSheet:
    """Character sheet for Snowflake Method."""
    name: str
    motivation: str
    goal: str
    conflict: str
    epiphany: str
    one_sentence_summary: str = ""
    one_paragraph_summary: str = ""
    character_synopsis: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "motivation": self.motivation,
            "goal": self.goal,
            "conflict": self.conflict,
            "epiphany": self.epiphany,
            "one_sentence_summary": self.one_sentence_summary,
            "one_paragraph_summary": self.one_paragraph_summary,
            "character_synopsis": self.character_synopsis,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterSheet":
        return cls(**data)


class SnowflakeMethod:
    """Implementation of Randy Ingermanson's Snowflake Method."""
    
    def __init__(self, concept: str = ""):
        """Initialize with a basic concept."""
        self.concept = concept
        self.current_step = 1
        
        # Step 1: One sentence summary
        self.one_sentence_summary = ""
        
        # Step 2: One paragraph summary
        self.paragraph_summary = ""
        
        # Step 3: Character summaries
        self.major_characters: List[CharacterSheet] = []
        self.minor_characters: List[CharacterSheet] = []
        
        # Step 4: Expand paragraph to page
        self.page_summary = ""
        
        # Step 5: Character synopses (done in step 3)
        
        # Step 6: Expand page to chapter outline
        self.chapter_outline: List[Dict[str, str]] = []
        
        # Step 7: Expand character descriptions
        # (Enhanced character sheets)
        
        # Step 8: Scene list
        self.scene_list: List[Dict[str, Any]] = []
        
        # Step 9: Narrative descriptions of scenes
        self.scene_narratives: Dict[str, str] = {}
        
        # Step 10: First draft (handled by main generation system)
        
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
    
    async def expand_to_sentence(self, ai_client) -> str:
        """Step 1: Expand concept to one sentence summary."""
        if self.one_sentence_summary:
            return self.one_sentence_summary
        
        prompt = f"""
        Take this story concept and create a compelling one-sentence summary (no more than 15 words):
        
        Concept: {self.concept}
        
        The sentence should capture the main character, the central conflict, and what's at stake.
        Make it intriguing and specific. Avoid generic phrases.
        
        Examples of good one-sentence summaries:
        - "A farm boy discovers he's the galaxy's last hope against an evil empire."
        - "A lawyer takes on a case that forces her to confront her family's dark secrets."
        - "A time traveler accidentally changes history and must fix it before reality collapses."
        """
        
        self.one_sentence_summary = await ai_client.generate_content(prompt)
        self.current_step = max(self.current_step, 1)
        self.modified_at = datetime.now()
        
        return self.one_sentence_summary
    
    async def expand_to_paragraph(self, ai_client) -> str:
        """Step 2: Expand sentence to paragraph."""
        if not self.one_sentence_summary:
            await self.expand_to_sentence(ai_client)
        
        if self.paragraph_summary:
            return self.paragraph_summary
        
        prompt = f"""
        Expand this one-sentence story summary into a full paragraph (about 100 words):
        
        One-sentence summary: {self.one_sentence_summary}
        
        The paragraph should include:
        1. The setup/opening situation
        2. The first major plot turn (25% mark)
        3. The midpoint disaster (50% mark)
        4. The final disaster (75% mark)
        5. The resolution
        
        Focus on the main story arc and major plot points. Don't get bogged down in details.
        """
        
        self.paragraph_summary = await ai_client.generate_content(prompt)
        self.current_step = max(self.current_step, 2)
        self.modified_at = datetime.now()
        
        return self.paragraph_summary
    
    async def develop_characters(self, ai_client) -> List[CharacterSheet]:
        """Step 3: Develop major characters."""
        if not self.paragraph_summary:
            await self.expand_to_paragraph(ai_client)
        
        if self.major_characters:
            return self.major_characters
        
        # First, identify the main characters
        prompt = f"""
        Based on this story summary, identify the 3-5 most important characters:
        
        {self.paragraph_summary}
        
        For each character, provide:
        1. Name (or role if name isn't clear)
        2. Their main motivation (what drives them)
        3. Their goal (what they want to achieve)
        4. Their conflict (what stands in their way)
        5. Their epiphany (what they learn/how they change)
        
        Format each character as:
        Character: [Name]
        Motivation: [What drives them]
        Goal: [What they want]
        Conflict: [What opposes them]
        Epiphany: [How they change]
        """
        
        character_analysis = await ai_client.generate_content(prompt)
        
        # Parse the response to create character sheets
        self.major_characters = []
        lines = character_analysis.split('\n')
        current_character = None
        
        for line in lines:
            line = line.strip()
            if line and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'character' in key or 'name' in key:
                    if current_character:
                        self.major_characters.append(current_character)
                    current_character = CharacterSheet(
                        name=value,
                        motivation="",
                        goal="",
                        conflict="",
                        epiphany=""
                    )
                elif current_character:
                    if 'motivation' in key:
                        current_character.motivation = value
                    elif 'goal' in key:
                        current_character.goal = value
                    elif 'conflict' in key:
                        current_character.conflict = value
                    elif 'epiphany' in key or 'learn' in key or 'change' in key:
                        current_character.epiphany = value
        
        if current_character:
            self.major_characters.append(current_character)
        
        # Create one-sentence summaries for each character
        for character in self.major_characters:
            if not character.one_sentence_summary:
                char_prompt = f"""
                Create a one-sentence summary for this character:
                
                Name: {character.name}
                Motivation: {character.motivation}
                Goal: {character.goal}
                Conflict: {character.conflict}
                
                Make it compelling and capture their essence in one sentence.
                """
                character.one_sentence_summary = await ai_client.generate_content(char_prompt)
        
        self.current_step = max(self.current_step, 3)
        self.modified_at = datetime.now()
        
        return self.major_characters
    
    async def expand_to_page(self, ai_client) -> str:
        """Step 4: Expand paragraph to one page."""
        if not self.paragraph_summary:
            await self.expand_to_paragraph(ai_client)
        
        if self.page_summary:
            return self.page_summary
        
        prompt = f"""
        Expand this paragraph summary into a full page (about 400 words):
        
        Paragraph summary: {self.paragraph_summary}
        
        The page should include:
        1. Detailed setup and character introduction
        2. The inciting incident
        3. Plot point 1 (25% mark) - what gets the story rolling
        4. The midpoint disaster (50% mark) - major setback
        5. Plot point 2 (75% mark) - final disaster before climax
        6. Brief climax and resolution
        
        Make it engaging and specific. Include character motivations and stakes.
        Focus on the story structure and main plot points.
        """
        
        self.page_summary = await ai_client.generate_content(prompt)
        self.current_step = max(self.current_step, 4)
        self.modified_at = datetime.now()
        
        return self.page_summary
    
    async def expand_character_synopses(self, ai_client) -> List[CharacterSheet]:
        """Step 5: Expand character descriptions."""
        if not self.major_characters:
            await self.develop_characters(ai_client)
        
        for character in self.major_characters:
            if not character.character_synopsis:
                prompt = f"""
                Write a one-page character synopsis for: {character.name}
                
                Character details:
                - Motivation: {character.motivation}
                - Goal: {character.goal}
                - Conflict: {character.conflict}
                - Epiphany: {character.epiphany}
                
                Story context: {self.page_summary}
                
                Include:
                1. Backstory and what shaped them
                2. Their role in the story
                3. How they change throughout the story
                4. Key relationships with other characters
                5. Their character arc from beginning to end
                6. Physical description and personality traits
                
                Make it about 200-300 words.
                """
                
                character.character_synopsis = await ai_client.generate_content(prompt)
        
        self.current_step = max(self.current_step, 5)
        self.modified_at = datetime.now()
        
        return self.major_characters
    
    async def expand_to_chapter_outline(self, ai_client) -> List[Dict[str, str]]:
        """Step 6: Expand to chapter outline."""
        if not self.page_summary:
            await self.expand_to_page(ai_client)
        
        if self.chapter_outline:
            return self.chapter_outline
        
        character_info = "\n".join([
            f"- {char.name}: {char.one_sentence_summary}" 
            for char in self.major_characters
        ])
        
        prompt = f"""
        Convert this story summary into a detailed chapter outline:
        
        Story summary: {self.page_summary}
        
        Main characters:
        {character_info}
        
        Create 15-25 chapters, each with:
        1. Chapter number and title
        2. 2-3 sentence summary of what happens
        3. Which characters appear
        4. The main conflict/tension
        5. How it advances the plot
        
        Follow the three-act structure:
        - Act 1 (Chapters 1-6): Setup, inciting incident, first plot point
        - Act 2A (Chapters 7-12): Rising action, complications
        - Act 2B (Chapters 13-18): Midpoint, more complications, second plot point
        - Act 3 (Chapters 19-25): Climax, falling action, resolution
        
        Format as:
        Chapter 1: [Title]
        Summary: [What happens]
        Characters: [Who appears]
        Conflict: [Main tension]
        Purpose: [Plot advancement]
        
        [blank line between chapters]
        """
        
        outline_text = await ai_client.generate_content(prompt)
        
        # Parse the outline into structured format
        self.chapter_outline = []
        current_chapter = {}
        
        for line in outline_text.split('\n'):
            line = line.strip()
            if line.startswith('Chapter'):
                if current_chapter:
                    self.chapter_outline.append(current_chapter)
                chapter_match = line.split(':', 1)
                if len(chapter_match) == 2:
                    chapter_num = len(self.chapter_outline) + 1
                    current_chapter = {
                        'number': chapter_num,
                        'title': chapter_match[1].strip(),
                        'summary': '',
                        'characters': '',
                        'conflict': '',
                        'purpose': ''
                    }
            elif current_chapter and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'summary' in key:
                    current_chapter['summary'] = value
                elif 'character' in key:
                    current_chapter['characters'] = value
                elif 'conflict' in key:
                    current_chapter['conflict'] = value
                elif 'purpose' in key:
                    current_chapter['purpose'] = value
        
        if current_chapter:
            self.chapter_outline.append(current_chapter)
        
        self.current_step = max(self.current_step, 6)
        self.modified_at = datetime.now()
        
        return self.chapter_outline
    
    async def expand_character_details(self, ai_client) -> List[CharacterSheet]:
        """Step 7: Expand character details further."""
        if not self.major_characters:
            await self.develop_characters(ai_client)
        
        # Expand each character's paragraph summary
        for character in self.major_characters:
            if not character.one_paragraph_summary:
                prompt = f"""
                Expand this character summary into a full paragraph:
                
                Character: {character.name}
                One-sentence summary: {character.one_sentence_summary}
                
                Story context: {self.paragraph_summary}
                
                Write a paragraph that covers:
                1. Their background and personality
                2. What they want and why
                3. What opposes them
                4. How they grow and change
                5. Their role in the overall story
                
                Keep it to about 75-100 words.
                """
                
                character.one_paragraph_summary = await ai_client.generate_content(prompt)
        
        self.current_step = max(self.current_step, 7)
        self.modified_at = datetime.now()
        
        return self.major_characters
    
    async def create_scene_list(self, ai_client) -> List[Dict[str, Any]]:
        """Step 8: Create detailed scene list."""
        if not self.chapter_outline:
            await self.expand_to_chapter_outline(ai_client)
        
        if self.scene_list:
            return self.scene_list
        
        self.scene_list = []
        
        # Process chapters in batches to avoid overwhelming the AI
        for i in range(0, len(self.chapter_outline), 3):
            batch = self.chapter_outline[i:i+3]
            
            chapters_text = "\n\n".join([
                f"Chapter {ch['number']}: {ch['title']}\n"
                f"Summary: {ch['summary']}\n"
                f"Characters: {ch['characters']}"
                for ch in batch
            ])
            
            prompt = f"""
            Break down these chapters into 2-4 scenes each:
            
            {chapters_text}
            
            For each scene, provide:
            1. Scene number within chapter
            2. Location/setting
            3. Characters present
            4. What happens (2-3 sentences)
            5. Emotional purpose/tension
            6. POV character
            
            Format as:
            Chapter X, Scene Y: [Location]
            Characters: [Who's there]
            POV: [Point of view character]
            Action: [What happens]
            Purpose: [Emotional goal/tension]
            
            [blank line between scenes]
            """
            
            scenes_text = await ai_client.generate_content(prompt)
            
            # Parse scenes for this batch
            current_scene = {}
            
            for line in scenes_text.split('\n'):
                line = line.strip()
                if line.startswith('Chapter') and 'Scene' in line:
                    if current_scene:
                        self.scene_list.append(current_scene)
                    
                    # Parse "Chapter X, Scene Y: Location"
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        chapter_scene = parts[0].strip()
                        location = parts[1].strip()
                        
                        # Extract chapter and scene numbers
                        import re
                        match = re.search(r'Chapter (\d+).*Scene (\d+)', chapter_scene)
                        if match:
                            chapter_num = int(match.group(1))
                            scene_num = int(match.group(2))
                            
                            current_scene = {
                                'chapter': chapter_num,
                                'scene': scene_num,
                                'location': location,
                                'characters': '',
                                'pov': '',
                                'action': '',
                                'purpose': ''
                            }
                elif current_scene and ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if 'character' in key:
                        current_scene['characters'] = value
                    elif 'pov' in key or 'point of view' in key:
                        current_scene['pov'] = value
                    elif 'action' in key or 'happens' in key:
                        current_scene['action'] = value
                    elif 'purpose' in key or 'tension' in key or 'goal' in key:
                        current_scene['purpose'] = value
            
            if current_scene:
                self.scene_list.append(current_scene)
            
            # Small delay to be respectful to the API
            await asyncio.sleep(1)
        
        self.current_step = max(self.current_step, 8)
        self.modified_at = datetime.now()
        
        return self.scene_list
    
    async def write_scene_narratives(self, ai_client) -> Dict[str, str]:
        """Step 9: Write narrative descriptions for each scene."""
        if not self.scene_list:
            await self.create_scene_list(ai_client)
        
        # Only write narratives for scenes that don't have them yet
        scenes_to_write = [
            scene for scene in self.scene_list 
            if f"{scene['chapter']}-{scene['scene']}" not in self.scene_narratives
        ]
        
        for scene in scenes_to_write:
            scene_key = f"{scene['chapter']}-{scene['scene']}"
            
            # Get character context
            character_context = ""
            if self.major_characters:
                char_names = [char.name for char in self.major_characters]
                relevant_chars = [
                    char for char in self.major_characters 
                    if char.name in scene.get('characters', '')
                ]
                if relevant_chars:
                    character_context = "\n".join([
                        f"{char.name}: {char.one_sentence_summary}"
                        for char in relevant_chars
                    ])
            
            prompt = f"""
            Write a detailed narrative description for this scene:
            
            Chapter {scene['chapter']}, Scene {scene['scene']}
            Location: {scene['location']}
            Characters: {scene['characters']}
            POV: {scene.get('pov', 'Third person')}
            What happens: {scene['action']}
            Purpose: {scene['purpose']}
            
            Character context:
            {character_context}
            
            Write a 200-300 word narrative description that:
            1. Sets the scene and mood
            2. Shows character actions and dialogue
            3. Advances the plot
            4. Creates the intended emotional impact
            5. Flows naturally from the previous scene
            
            Write in the chosen POV and make it engaging and vivid.
            """
            
            narrative = await ai_client.generate_content(prompt)
            self.scene_narratives[scene_key] = narrative
            
            # Small delay to be respectful to the API
            await asyncio.sleep(0.5)
        
        self.current_step = max(self.current_step, 9)
        self.modified_at = datetime.now()
        
        return self.scene_narratives
    
    def get_scene_narrative(self, chapter: int, scene: int) -> str:
        """Get narrative for a specific scene."""
        scene_key = f"{chapter}-{scene}"
        return self.scene_narratives.get(scene_key, "")
    
    def get_chapter_scenes(self, chapter_number: int) -> List[Dict[str, Any]]:
        """Get all scenes for a specific chapter."""
        return [
            scene for scene in self.scene_list 
            if scene['chapter'] == chapter_number
        ]
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current development status."""
        return {
            "current_step": self.current_step,
            "concept": self.concept,
            "steps_completed": {
                "step_1_sentence": bool(self.one_sentence_summary),
                "step_2_paragraph": bool(self.paragraph_summary),
                "step_3_characters": len(self.major_characters) > 0,
                "step_4_page": bool(self.page_summary),
                "step_5_character_synopses": all(
                    char.character_synopsis for char in self.major_characters
                ),
                "step_6_chapter_outline": len(self.chapter_outline) > 0,
                "step_7_character_details": all(
                    char.one_paragraph_summary for char in self.major_characters
                ),
                "step_8_scene_list": len(self.scene_list) > 0,
                "step_9_scene_narratives": len(self.scene_narratives) > 0,
                "step_10_ready_for_draft": self.current_step >= 9,
            },
            "statistics": {
                "major_characters": len(self.major_characters),
                "minor_characters": len(self.minor_characters),
                "total_chapters": len(self.chapter_outline),
                "total_scenes": len(self.scene_list),
                "completed_narratives": len(self.scene_narratives),
            },
            "ready_for_draft": self.current_step >= 6,  # Can start drafting after step 6
            "fully_developed": self.current_step >= 9,
        }
    
    def get_story_summary(self) -> str:
        """Get the most developed story summary available."""
        if self.page_summary:
            return self.page_summary
        elif self.paragraph_summary:
            return self.paragraph_summary
        elif self.one_sentence_summary:
            return self.one_sentence_summary
        else:
            return self.concept
    
    def export_for_generation(self) -> Dict[str, Any]:
        """Export data in format suitable for content generation."""
        return {
            "story_summary": self.get_story_summary(),
            "characters": [
                {
                    "name": char.name,
                    "description": char.character_synopsis or char.one_paragraph_summary or char.one_sentence_summary,
                    "motivation": char.motivation,
                    "goal": char.goal,
                    "conflict": char.conflict,
                }
                for char in self.major_characters
            ],
            "chapter_outline": self.chapter_outline,
            "scene_list": self.scene_list,
            "scene_narratives": self.scene_narratives,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "concept": self.concept,
            "current_step": self.current_step,
            "one_sentence_summary": self.one_sentence_summary,
            "paragraph_summary": self.paragraph_summary,
            "page_summary": self.page_summary,
            "major_characters": [char.to_dict() for char in self.major_characters],
            "minor_characters": [char.to_dict() for char in self.minor_characters],
            "chapter_outline": self.chapter_outline,
            "scene_list": self.scene_list,
            "scene_narratives": self.scene_narratives,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SnowflakeMethod":
        """Create from dictionary."""
        snowflake = cls(data.get("concept", ""))
        snowflake.current_step = data.get("current_step", 1)
        snowflake.one_sentence_summary = data.get("one_sentence_summary", "")
        snowflake.paragraph_summary = data.get("paragraph_summary", "")
        snowflake.page_summary = data.get("page_summary", "")
        snowflake.chapter_outline = data.get("chapter_outline", [])
        snowflake.scene_list = data.get("scene_list", [])
        snowflake.scene_narratives = data.get("scene_narratives", {})
        
        # Load characters
        for char_data in data.get("major_characters", []):
            snowflake.major_characters.append(CharacterSheet.from_dict(char_data))
        
        for char_data in data.get("minor_characters", []):
            snowflake.minor_characters.append(CharacterSheet.from_dict(char_data))
        
        if "created_at" in data:
            snowflake.created_at = datetime.fromisoformat(data["created_at"])
        if "modified_at" in data:
            snowflake.modified_at = datetime.fromisoformat(data["modified_at"])
        
        return snowflake


# Convenience functions for step-by-step development
async def develop_story_step_by_step(concept: str, ai_client, target_step: int = 10) -> SnowflakeMethod:
    """Develop a story through the Snowflake Method steps."""
    snowflake = SnowflakeMethod(concept)
    
    if target_step >= 1:
        await snowflake.expand_to_sentence(ai_client)
        print(f"✅ Step 1 complete: {snowflake.one_sentence_summary}")
    
    if target_step >= 2:
        await snowflake.expand_to_paragraph(ai_client)
        print(f"✅ Step 2 complete: Paragraph summary ({len(snowflake.paragraph_summary)} chars)")
    
    if target_step >= 3:
        await snowflake.develop_characters(ai_client)
        print(f"✅ Step 3 complete: {len(snowflake.major_characters)} characters developed")
    
    if target_step >= 4:
        await snowflake.expand_to_page(ai_client)
        print(f"✅ Step 4 complete: Page summary ({len(snowflake.page_summary)} chars)")
    
    if target_step >= 5:
        await snowflake.expand_character_synopses(ai_client)
        print(f"✅ Step 5 complete: Character synopses written")
    
    if target_step >= 6:
        await snowflake.expand_to_chapter_outline(ai_client)
        print(f"✅ Step 6 complete: {len(snowflake.chapter_outline)} chapters outlined")
    
    if target_step >= 7:
        await snowflake.expand_character_details(ai_client)
        print(f"✅ Step 7 complete: Character details expanded")
    
    if target_step >= 8:
        await snowflake.create_scene_list(ai_client)
        print(f"✅ Step 8 complete: {len(snowflake.scene_list)} scenes listed")
    
    if target_step >= 9:
        await snowflake.write_scene_narratives(ai_client)
        print(f"✅ Step 9 complete: {len(snowflake.scene_narratives)} scene narratives written")
    
    if target_step >= 10:
        print("✅ Ready for Step 10: First draft writing (use content generation tools)")
    
    return snowflake