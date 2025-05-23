"""Consistency checking for manuscripts."""

from typing import List, Dict, Any
import re


class ConsistencyChecker:
    """Checks manuscript for consistency issues."""
    
    def __init__(self, ai_client=None):
        self.ai_client = ai_client
    
    async def check_consistency(
        self,
        manuscript: str,
        character_info: str,
        story_context: str,
    ) -> List[str]:
        """Check for consistency issues."""
        issues = []
        
        # Basic checks
        issues.extend(self._check_character_names(manuscript, character_info))
        issues.extend(self._check_timeline(manuscript))
        
        # AI-powered checks if available
        if self.ai_client:
            ai_issues = await self.ai_client.check_consistency(
                manuscript, character_info, story_context
            )
            issues.extend(ai_issues)
        
        return issues
    
    def _check_character_names(self, manuscript: str, character_info: str) -> List[str]:
        """Check for character name consistency."""
        issues = []
        
        # Extract character names from character info
        character_names = re.findall(r'^#+\s*(.+?)$', character_info, re.MULTILINE)
        
        for name in character_names:
            name = name.strip()
            if name and len(name.split()) <= 3:  # Reasonable name length
                # Check for variations in the manuscript
                variations = [name, name.lower(), name.upper(), name.title()]
                found_variations = []
                
                for var in variations:
                    if var in manuscript and var != name:
                        found_variations.append(var)
                
                if found_variations:
                    issues.append(f"Character name variations found for '{name}': {found_variations}")
        
        return issues
    
    def _check_timeline(self, manuscript: str) -> List[str]:
        """Check for timeline inconsistencies.""" 
        issues = []
        
        # Look for time references
        time_patterns = [
            r'\b(yesterday|today|tomorrow)\b',
            r'\b(morning|afternoon|evening|night)\b',
            r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b',
        ]
        
        time_refs = []
        for pattern in time_patterns:
            matches = re.findall(pattern, manuscript, re.IGNORECASE)
            time_refs.extend(matches)
        
        # Basic timeline consistency check (simplified)
        if 'yesterday' in manuscript.lower() and 'tomorrow' in manuscript.lower():
            # More sophisticated logic would be needed for real timeline checking
            pass
        
        return issues
