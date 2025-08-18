
"""
chapter_splitter.py
-------------------
Split a single manuscript file into per-chapter artefacts.

Rules
-----
A new chapter starts when the manuscript contains exactly this pattern:
    <blank line>
    <a line that is only digits, e.g. "12">
    <blank line>

The numeric line itself is not included in the chapter text.
Optionally, a single ALL-CAPS prelude line (e.g., "PART I") immediately
above the number (with a blank line between) can be carried into the chapter.

Usage
-----
As a library:
    from chapter_splitter import split_text_to_chapters, write_chapters_to_disk
    chunks = split_text_to_chapters(text, include_uppercase_prelude=True)
    paths  = write_chapters_to_disk(chunks, out_dir, filename_pattern="{n:02d}_chapter_{n:02d}.md")

As a CLI:
    python chapter_splitter.py --input manuscript_full.md --out artefacts/chapters
    python chapter_splitter.py --input manuscript_full.md --out artefacts/chapters --pattern "chapter_{n:02d}.md"
    python chapter_splitter.py --input manuscript_full.md --out artefacts/chapters --no-prelude
    python chapter_splitter.py --input manuscript_full.md --out artefacts/chapters --dry-run
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Iterable
import re
import argparse


Chunk = Tuple[int, str]  # (chapter_number, chapter_text)


def _find_markers(lines: List[str]) -> List[Tuple[int, int]]:
    """
    Return a list of (line_index, chapter_number) where lines[line_index]
    is a numeric marker that has a blank line immediately after it.
    """
    markers: List[Tuple[int, int]] = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.isdigit():
            # require a blank line AFTER the number (per the user's rule)
            if i + 1 < len(lines) and lines[i + 1].strip() == "":
                markers.append((i, int(s)))
    return markers


def split_text_to_chapters(
    text: str,
    *,
    include_uppercase_prelude: bool = True,
) -> List[Chunk]:
    """
    Split a manuscript (string) into chapters based on numeric markers.

    Returns a list of (chapter_number, chapter_text) in order.
    Chapter text excludes the numeric marker line itself and the blank
    line that follows it. If include_uppercase_prelude=True and there is an
    ALL-CAPS line two lines above the number (with a blank line between),
    that prelude line is prepended to the chapter text.
    """
    # Keep line endings for precise slicing
    lines = text.splitlines(keepends=True)

    # Precompute byte offsets for accurate start/end indices
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))

    def lstart(i: int) -> int:
        return offsets[i]

    def lend(i: int) -> int:
        return offsets[i + 1]

    markers = _find_markers(lines)
    if not markers:
        return []

    chunks: List[Chunk] = []
    for idx, (line_i, chap_num) in enumerate(markers):
        # Start right AFTER the marker (and drop the blank line after it)
        start = lend(line_i)
        if line_i + 1 < len(lines) and lines[line_i + 1].strip() == "":
            start = lend(line_i + 1)

        # Include a single ALL-CAPS prelude two lines above (prelude + blank + number)
        if include_uppercase_prelude and line_i >= 2:
            if lines[line_i - 1].strip() == "":
                prelude = lines[line_i - 2].strip()
                if prelude and re.fullmatch(r"[A-Z][A-Z ]*", prelude):
                    start = min(start, lstart(line_i - 2))

        # End right BEFORE the next marker
        if idx + 1 < len(markers):
            next_line_i, _ = markers[idx + 1]
            end = lstart(next_line_i)
            # trim a single trailing blank line if present
            if next_line_i - 1 >= 0 and lines[next_line_i - 1].strip() == "":
                end = lstart(next_line_i - 1)
        else:
            end = len(text)

        chunk = text[start:end].lstrip("\r\n")
        if chunk.strip():
            chunks.append((chap_num, chunk))

    return chunks


def write_chapters_to_disk(
    chunks: Iterable[Chunk],
    out_dir: Path,
    filename_pattern: str = "{n:02d}_chapter_{n:02d}.md",
) -> List[Path]:
    """
    Write chapter chunks to disk using the given filename pattern.
    Returns a list of written Paths in order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for chap_num, chunk in chunks:
        path = out_dir / filename_pattern.format(n=chap_num)
        path.write_text(chunk, encoding="utf-8")
        written.append(path)
    return written


def split_file_to_chapters(
    manuscript_path: Path,
    out_dir: Path,
    *,
    filename_pattern: str = "{n:02d}_chapter_{n:02d}.md",
    include_uppercase_prelude: bool = True,
) -> List[Path]:
    """
    Convenience wrapper: read a file, split text, and write artefacts.
    """
    text = Path(manuscript_path).read_text(encoding="utf-8")
    chunks = split_text_to_chapters(text, include_uppercase_prelude=include_uppercase_prelude)
    return write_chapters_to_disk(chunks, out_dir, filename_pattern=filename_pattern)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Split a manuscript into per-chapter artefacts based on numeric markers."
    )
    p.add_argument("--input", "-i", type=Path, required=True, help="Path to the full manuscript (.md/.txt).")
    p.add_argument("--out", "-o", type=Path, required=True, help="Output folder for chapter artefacts.")
    p.add_argument(
        "--pattern",
        "-p",
        default="{n:02d}_chapter_{n:02d}.md",
        help="Filename pattern. Use {n} for chapter number (e.g., 'chapter_{n:02d}.md').",
    )
    p.add_argument(
        "--no-prelude",
        action="store_true",
        help="Do not pull ALL-CAPS prelude lines (e.g., 'PART I') into chapters.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and show what would be written without creating files.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    text = args.input.read_text(encoding="utf-8")
    chunks = split_text_to_chapters(text, include_uppercase_prelude=not args.no_prelude)

    if args.dry_run:
        print(f"Found {len(chunks)} chapters:")
        for n, chunk in chunks:
            print(f" - {args.pattern.format(n=n)}  ({len(chunk)} chars)")
        return 0

    written = write_chapters_to_disk(chunks, args.out, filename_pattern=args.pattern)
    print(f"Wrote {len(written)} files to {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
