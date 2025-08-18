#!/usr/bin/env python3
import argparse
import sys
import subprocess
import shlex

def parse_range(text: str):
    try:
        start_s, end_s = text.split(",", 1)
        start = int(start_s.strip())
        end = int(end_s.strip())
        if start > end:
            raise ValueError
        return start, end
    except Exception:
        raise argparse.ArgumentTypeError(
            "Expected format START,END with START <= END, e.g. 0,29"
        )

def main():
    parser = argparse.ArgumentParser(
        description="Loop chapters and run chapter_reviser.py for each."
    )
    parser.add_argument(
        "book",
        help="Book name (also the sub-folder), e.g. 'junkmiles'"
    )
    parser.add_argument(
        "--loop-chapters",
        required=True,
        type=parse_range,
        metavar="START,END",
        help="Inclusive chapter range to analyze, e.g. 0,29"
    )
    parser.add_argument(
        "--chapter-script",
        default="chapter_reviser.py",
        help="Path to chapter_reviser.py (default: chapter_reviser.py)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without running them"
    )
    args = parser.parse_args()

    start, end = args.loop_chapters

    for ch in range(start, end + 1):
        # Determine context chapters:
        # - middle chapters: previous and next (e.g., 3,5 for chapter 4)
        # - first chapter in the loop: only next (e.g., 1 for chapter 0)
        # - last chapter in the loop: only previous (e.g., 28 for chapter 29)
        if ch == start and ch == end:
            # Single-chapter loop: choose neighbors if they exist
            context = []
            if ch - 1 >= 0:
                context.append(str(ch - 1))
            context.append(str(ch + 1))
        elif ch == start:
            context = [str(ch + 1)]
        elif ch == end:
            context = [str(ch - 1)]
        else:
            context = [str(ch - 1), str(ch + 1)]

        # Build the command
        cmd = [
            sys.executable,                  # use the current Python interpreter
            args.chapter_script,
            args.book,
            "--chapter", str(ch),
            "--context-chapters", ",".join(context),
            "--analysis-only",
        ]

        # Show the command for visibility
        try:
            pretty = shlex.join(cmd)  # Python 3.8+
        except Exception:
            pretty = " ".join(cmd)
        print(f"\n>>> {pretty}")

        if not args.dry_run:
            # Run and stream output
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print(
                    f"Command failed for chapter {ch} with exit code {result.returncode}.",
                    file=sys.stderr
                )
                # Optional: uncomment to stop on first failure
                # sys.exit(result.returncode)

if __name__ == "__main__":
    main()
