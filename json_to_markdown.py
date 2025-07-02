import json

with open('consistency.json', encoding='utf-8') as f:
    data = json.load(f)

out = ['# Continuity Report Summary\n']
out.append(f"**Continuity Score:** {data.get('continuity_score')}/10\n")

out.append('## Issues Found:\n')
for issue in data['issues_found']:
    out.append(f"- **[{issue['type'].capitalize()}] Chapter {issue['chapter']} ({issue['severity']}):** {issue['description']}")

out.append('\n## Suggestions:\n')
for suggestion in data['suggestions']:
    out.append(f"- {suggestion}")

out.append('\n## Character Consistency:\n')
for character, description in data['character_consistency'].items():
    out.append(f"- **{character}**: {description}")

out.append('\n## Timeline Assessment:\n')
out.append(data['timeline_assessment'])

with open('consistency2.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
