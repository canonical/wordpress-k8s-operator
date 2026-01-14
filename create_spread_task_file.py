# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

#!/usr/bin/env python3
"""
Extract commands from markdown files.

This script reads a markdown file and extracts all commands from code blocks.
Code blocks are defined by triple backticks (```), and blocks starting with
{note} or {tip} are excluded.
"""

import sys
import re


def extract_commands_from_markdown(file_path):
    """
    Extract all commands from code blocks in a markdown file.
    
    Args:
        file_path: Path to the markdown file
        
    Returns:
        List of command strings found in code blocks
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find sections to exclude: "What you'll need", "Requirements", or "Prerequisites"
    excluded_section_ranges = []
    header_pattern = r'^(#+)\s+(.+)$'
    
    # Find all headers in the document
    headers = []
    for match in re.finditer(header_pattern, content, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        position = match.start()
        headers.append((position, level, title))
    
    # Find all sections with names: "What you'll need", "Requirements", or "Prerequisites"
    excluded_section_names = ["what you'll need", "requirements", "prerequisites"]
    for i, (pos, level, title) in enumerate(headers):
        if title.lower() in excluded_section_names:
            start_pos = pos
            # Find the next header at the same or higher level (fewer or equal #)
            end_pos = len(content)
            for j in range(i + 1, len(headers)):
                next_pos, next_level, next_title = headers[j]
                if next_level <= level:
                    end_pos = next_pos
                    break
            excluded_section_ranges.append((start_pos, end_pos))
    
    # First, find all blocks with 4+ backticks to identify excluded regions
    excluded_ranges = []
    pattern_4plus = r'````+[^\n]*\n(.*?)````+'
    for match in re.finditer(pattern_4plus, content, re.DOTALL):
        excluded_ranges.append((match.start(), match.end()))
    
    # Add all excluded sections to excluded ranges
    excluded_ranges.extend(excluded_section_ranges)
    
    # Find all code blocks: exactly 3 backticks (not more), optional language, content, then exactly 3 backticks
    # Use negative lookbehind and lookahead to ensure exactly 3 backticks
    pattern = r'(?<!`)```(?!`)([^\n]*)\n(.*?)(?<!`)```(?!`)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    commands = []
    for match in matches:
        lang_identifier = match.group(1)
        code_content = match.group(2)
        match_start = match.start()
        match_end = match.end()
        
        # Skip blocks that start with { (like {note}, {tip}, or {terminal})
        if lang_identifier.strip().startswith('{'):
            continue
        
        # Skip blocks that are nested within 4+ backtick blocks or in excluded sections
        is_nested = any(start <= match_start < match_end <= end 
                       for start, end in excluded_ranges)
        if is_nested:
            continue
        
        # Add non-empty code content
        if code_content.strip():
            commands.append(code_content.strip())
    
    return commands

def write_task_yaml(commands, output_path="task.yaml"):
    """
    Write extracted commands to a task.yaml file.
    
    Args:
        commands: List of command strings to write
        output_path: Path to the output YAML file
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Write the header
        f.write("summary: Tutorial test\n")
        f.write("\n")
        f.write("kill-timeout: 30m\n")
        f.write("\n")
        f.write("execute: |\n")
        
        # Write each command with 2-space indentation
        for command in commands:
            # Split multi-line commands and indent each line
            for line in command.split('\n'):
                f.write(f"  {line}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_commands.py <markdown_file>")
        print("Example: python extract_commands.py docs/tutorial.md")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        commands = extract_commands_from_markdown(file_path)
        
        print(f"Found {len(commands)} command block(s) in {file_path}:\n")
        
        for i, command in enumerate(commands, 1):
            print(f"Command block {i}:")
            print(command)
            print("-" * 70)
            print()
        
        # Write commands to task.yaml
        output_file = "task.yaml"
        write_task_yaml(commands, output_file)
        print(f"\nCommands written to {output_file}")
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

