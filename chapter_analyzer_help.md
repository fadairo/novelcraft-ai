usage: chapter_analyzer.py [-h] [--output OUTPUT] [--chapters CHAPTERS]
[--analyze-all] [--model MODEL]
[--template TEMPLATE] [--debug]
manuscript_dir

Professional manuscript analysis tool - Faber Academy style

positional arguments:
manuscript_dir Directory containing the manuscript files

optional arguments:
-h, --help show this help message and exit
--output OUTPUT Output directory for reports (default: manuscript
directory)
--chapters CHAPTERS Specific chapters to analyze (e.g., "1,3,5" or "1-10")
--analyze-all Analyze all chapters (default: samples first, middle,
last)
--model MODEL Claude model to use (default: claude-3-opus-20240229)
--template TEMPLATE Path to Faber report template (default:
faberfullreport.md in current directory)
--debug Enable debug logging

This tool generates professional editorial reports in the style of Faber Academy assessments.
It analyzes manuscripts for narrative structure, character development, pacing, and market potential.

Examples:

# Analyze complete manuscript with automatic chapter sampling

chapter_analyzer.py /path/to/manuscript

# Analyze specific chapters

chapter_analyzer.py /path/to/manuscript --chapters 1,5,10,15

# Analyze all chapters

chapter_analyzer.py /path/to/manuscript --analyze-all

# Specify output directory

chapter_analyzer.py /path/to/manuscript --output /path/to/reports

# Use specific Claude model

chapter_analyzer.py /path/to/manuscript --model claude-3-sonnet-20240229

The tool expects manuscript files to be organized with:

- Chapter files (chapter_1.md, ch01.txt, etc.)
- Optional context files (synopsis.md, characters.md, outline.md)
- Optional Faber template (faberfullreport.md) for style reference

Output includes:

- Full editorial report with synopsis, overview, detailed analysis, and recommendations
- Summary report with key points
- Individual chapter analyses (if requested)
