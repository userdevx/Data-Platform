from __future__ import annotations

import re


WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def extract_wiki_links(content: str) -> list[str]:
    links = []

    for match in WIKI_LINK_PATTERN.findall(content):
        title = match.strip()

        if title and title not in links:
            links.append(title)

    return links
