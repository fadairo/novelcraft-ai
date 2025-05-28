import os
import re
import argparse
from pathlib import Path

def extract_character_names(characters_file):
    """Extract character names from characters.md file."""
    characters = []
    
    if not os.path.exists(characters_file):
        print(f"Warning: {characters_file} not found. Using default character detection.")
        return characters
    
    try:
        with open(characters_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for character names in various markdown formats
        # Format 1: ## Character Name
        heading_matches = re.findall(r'^#{1,3}\s+([A-Z][a-zA-Z\s]+)(?:\s*[-–—]|$)', content, re.MULTILINE)
        characters.extend([name.strip() for name in heading_matches])
        
        # Format 2: **Name:** or **Name** at start of line
        bold_matches = re.findall(r'^\*\*([A-Z][a-zA-Z\s]+)\*\*:?', content, re.MULTILINE)
        characters.extend([name.strip() for name in bold_matches])
        
        # Format 3: Name: at start of line
        colon_matches = re.findall(r'^([A-Z][a-zA-Z\s]+):\s', content, re.MULTILINE)
        characters.extend([name.strip() for name in colon_matches])
        
        # Remove duplicates and common words
        characters = list(set(characters))
        common_words = ['The', 'This', 'That', 'These', 'Those', 'Chapter', 'Part', 'Section', 
                       'Main', 'Supporting', 'Characters', 'Protagonist', 'Antagonist']
        characters = [c for c in characters if c not in common_words and len(c) > 2]
        
        # Split multi-word names to also include first names
        additional_names = []
        for char in characters:
            parts = char.split()
            if len(parts) > 1:
                additional_names.append(parts[0])  # Add first name
                if len(parts) > 2:  # Add last name for 3+ word names
                    additional_names.append(parts[-1])
        
        characters.extend(additional_names)
        characters = list(set(characters))
        
        print(f"Found {len(characters)} characters: {', '.join(sorted(characters))}")
        
    except Exception as e:
        print(f"Error reading {characters_file}: {e}")
    
    return characters

def extract_key_points(content, characters, max_points=5):
    """Extract key points from chapter content."""
    # Split content into paragraphs
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    
    key_points = []
    
    # Common locations in spy novels
    locations = ['Cambridge', 'London', 'Prague', 'Paris', 'France', 'Moscow', 'Berlin', 
                 'Washington', 'Vienna', 'Budapest', 'MI6', 'CIA', 'KGB']
    
    # Look for dialogue sections and narrative turning points
    for i, para in enumerate(paragraphs):
        # Skip very short paragraphs
        if len(para) < 50:
            continue
            
        # Identify important paragraphs (containing key words/phrases)
        importance_indicators = [
            'realized', 'discovered', 'revealed', 'decided', 'remembered',
            'confronted', 'arrived', 'met', 'found', 'understood',
            'suspected', 'betrayed', 'escaped', 'pursued', 'investigated',
            'Operation', 'conspiracy', 'defection', 'intelligence', 'classified'
        ]
        
        # Add character names to importance indicators
        importance_indicators.extend(characters)
        
        if any(indicator in para for indicator in importance_indicators):
            # Split into sentences more carefully to avoid truncation
            # Handle multiple sentence endings
            sentences = re.split(r'(?<=[.!?])\s+', para)
            
            # Find the most important sentence(s)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 30:
                    # Count how many indicators are in this sentence
                    indicator_count = sum(1 for ind in importance_indicators if ind in sentence)
                    if indicator_count > 0:
                        # Keep the full sentence without truncation
                        key_points.append(sentence)
                        break
            
            # Alternative: if no single sentence is good, take a key portion
            if len(key_points) == i:  # No sentence was added
                # Find the most relevant continuous text
                for indicator in importance_indicators:
                    if indicator in para:
                        # Find sentence containing the indicator
                        for sentence in sentences:
                            if indicator in sentence and len(sentence) > 30:
                                key_points.append(sentence.strip())
                                break
                        break
        
        # Stop if we have enough points
        if len(key_points) >= max_points:
            break
    
    # If we don't have enough key points, extract from chapter beginning and end
    if len(key_points) < 3:
        # Get opening context - find first substantial sentence/paragraph
        for para in paragraphs[:3]:  # Check first 3 paragraphs
            if len(para) > 100:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sent in sentences:
                    if len(sent) > 50:
                        key_points.insert(0, sent.strip())
                        break
                break
        
        # Get closing context - find last substantial sentence
        for para in reversed(paragraphs[-3:]):  # Check last 3 paragraphs
            if len(para) > 100:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sent in reversed(sentences):
                    if len(sent) > 50:
                        key_points.append(sent.strip())
                        break
                break
    
    return key_points

def create_outline(novel_dir, smart_mode=False):
    """Generate outline for a novel."""
    
    # Set up paths
    chapters_dir = os.path.join(novel_dir, 'chapters')
    characters_file = os.path.join(novel_dir, 'characters.md')
    output_file = os.path.join(novel_dir, 'outline.md')
    
    # Check if novel directory exists
    if not os.path.exists(novel_dir):
        print(f"Error: Novel directory '{novel_dir}' not found!")
        return False
    
    # Check if chapters directory exists
    if not os.path.exists(chapters_dir):
        print(f"Error: Chapters directory '{chapters_dir}' not found!")
        return False
    
    # Extract character names
    characters = extract_character_names(characters_file)
    
    # Get all chapter files
    chapter_files = [f for f in os.listdir(chapters_dir) if f.startswith('chapter_') and f.endswith('.md')]
    
    if not chapter_files:
        print(f"Error: No chapter files found in '{chapters_dir}'!")
        return False
    
    # Sort chapter files by chapter number (extract number and sort numerically)
    def get_chapter_number(filename):
        match = re.search(r'chapter_(\d+)\.md', filename)
        return int(match.group(1)) if match else 999
    
    chapter_files.sort(key=get_chapter_number)
    
    print(f"Found {len(chapter_files)} chapters in '{novel_dir}'")
    
    outline_content = "# Outline\n\n"
    
    # Common locations in novels (can be extended based on genre)
    locations = ['Cambridge', 'London', 'Prague', 'Paris', 'France', 'Moscow', 'Berlin',
                 'Washington', 'Vienna', 'Budapest', 'New York', 'Rome', 'Geneva',
                 'Edinburgh', 'Dublin', 'Amsterdam', 'Brussels', 'Madrid', 'Tokyo']
    
    for chapter_file in chapter_files:
        # Extract chapter number
        match = re.search(r'chapter_(\d+)\.md', chapter_file)
        if not match:
            continue
            
        chapter_num = int(match.group(1))
        
        # Read chapter content
        file_path = os.path.join(chapters_dir, chapter_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {chapter_file}: {e}")
            continue
        
        print(f"Processing Chapter {chapter_num}...")
        
        # Create chapter header
        if chapter_num == 0:
            outline_content += "## Chapter 0 - Prologue\n\n"
        else:
            outline_content += f"## Chapter {chapter_num}\n\n"
        
        if smart_mode:
            # Smart mode: More intelligent analysis
            summary_points = []
            
            # Identify main characters present
            present_chars = [char for char in characters if char in content]
            
            # Identify locations
            present_locs = [loc for loc in locations if loc in content]
            
            # Look for action sequences
            action_words = ['ran', 'escaped', 'fought', 'discovered', 'revealed', 'confronted', 
                           'attacked', 'fled', 'pursued', 'investigated', 'searched', 'betrayed',
                           'infiltrated', 'intercepted', 'decoded', 'transmitted', 'assassinated']
            
            # Extract meaningful sentences
            sentences = re.split(r'(?<=[.!?])\s+', content)
            important_sentences = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 30:
                    continue
                    
                # Score sentence importance
                importance = 0
                
                # Character mentions
                for char in present_chars:
                    if char in sentence:
                        importance += 2
                
                # Action words
                for word in action_words:
                    if word in sentence.lower():
                        importance += 3
                        
                # Key plot elements
                plot_terms = ['Operation', 'MI6', 'CIA', 'KGB', 'conspiracy', 'defection',
                             'classified', 'intelligence', 'surveillance', 'tradecraft',
                             'mission', 'betrayal', 'secrets', 'double agent']
                if any(term in sentence for term in plot_terms):
                    importance += 5
                
                if importance >= 3:
                    important_sentences.append((importance, sentence))
            
            # Sort by importance and take top sentences
            important_sentences.sort(key=lambda x: x[0], reverse=True)
            
            # Add top important sentences as bullet points (full sentences, no truncation)
            added = 0
            for _, sentence in important_sentences:
                cleaned = sentence.strip()
                if cleaned and len(cleaned) > 30:
                    # Ensure proper punctuation
                    if not cleaned.endswith(('.', '!', '?')):
                        cleaned += '.'
                    summary_points.append(cleaned)
                    added += 1
                    if added >= 5:  # Limit to 5 points per chapter
                        break
            
            # Write points
            if summary_points:
                for point in summary_points:
                    outline_content += f"- {point}\n"
            else:
                outline_content += "- [Chapter needs manual summary]\n"
                
        else:
            # Basic mode: Extract key points
            key_points = extract_key_points(content, characters)
            
            if key_points:
                for point in key_points:
                    # Clean up the point
                    point = point.replace('\n', ' ').strip()
                    point = re.sub(r'\s+', ' ', point)  # Remove extra spaces
                    
                    # Ensure point ends with proper punctuation
                    if not point.endswith(('.', '!', '?')):
                        point += '.'
                    
                    outline_content += f"- {point}\n"
            else:
                outline_content += "- [No key points extracted - manual review needed]\n"
        
        outline_content += "\n"
    
    # Back up existing outline if it exists
    if os.path.exists(output_file):
        backup_file = output_file.replace('.md', '_backup.md')
        os.rename(output_file, backup_file)
        print(f"Existing outline backed up to: {backup_file}")
    
    # Write the new outline
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(outline_content)
    
    print(f"\nOutline generated successfully: {output_file}")
    print(f"Processed {len(chapter_files)} chapters")
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Generate novel outline from chapter files',
        usage='%(prog)s novel_name [options]'
    )
    parser.add_argument('novel', 
                       help='Name of the novel directory (e.g., glasshouse)')
    parser.add_argument('--smart', '-s', action='store_true',
                       help='Generate smart outline with advanced analysis')
    
    args = parser.parse_args()
    
    # Generate outline
    mode = "smart" if args.smart else "basic"
    print(f"Generating {mode} outline for '{args.novel}'...")
    
    success = create_outline(args.novel, args.smart)
    
    if success:
        print(f"\nDone! Check '{args.novel}/outline.md'")
    else:
        print("\nOutline generation failed.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())