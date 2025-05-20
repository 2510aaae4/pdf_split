import re

NUMBERED_TITLE_PATTERN = r'^\d+\s+.+'
HIERARCHICAL_TITLE_PATTERN = r'^\d+(\.\d+)+\s*.*'
CHAPTER_TITLE_PATTERN = r'^(Chapter|Part|Section)\s+\w+.*'

PATTERNS = [
    re.compile(NUMBERED_TITLE_PATTERN),
    re.compile(HIERARCHICAL_TITLE_PATTERN),
    re.compile(CHAPTER_TITLE_PATTERN),
]

def matches_any_pattern(title: str) -> bool:
    """Return True if the title matches any predefined pattern."""
    if not isinstance(title, str):
        return False
    return any(p.match(title) for p in PATTERNS)


def filter_bookmarks(bookmarks: list):
    """Recursively add ``matches_pattern`` flag to bookmark dictionaries."""
    filtered = []
    for item in bookmarks:
        if isinstance(item, list):
            filtered.append(filter_bookmarks(item))
        else:
            new_item = dict(item)
            new_item['matches_pattern'] = matches_any_pattern(new_item.get('title', ''))
            filtered.append(new_item)
    return filtered
