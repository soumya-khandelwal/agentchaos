"""Converts all AgentChaos markdown documentation into a modern HTML documentation portal."""

from __future__ import annotations

import os
import re
from pathlib import Path
from markdown_it import MarkdownIt

DOCS_DIR = Path("/home/soumikhandelwal/agent-chaos/docs")
ROOT_DIR = Path("/home/soumikhandelwal/agent-chaos")

PAGES = [
    {
        "id": "index",
        "title": "Overview & Getting Started",
        "icon": "⚡",
        "src": ROOT_DIR / "README.md",
        "dest": DOCS_DIR / "index.html",
        "category": "Getting Started",
    },
    {
        "id": "concepts",
        "title": "01. Concepts & Failure Modes",
        "icon": "🧠",
        "src": DOCS_DIR / "01-concepts.md",
        "dest": DOCS_DIR / "01-concepts.html",
        "category": "Core Architecture",
    },
    {
        "id": "architecture",
        "title": "02. Architecture & Design",
        "icon": "🏗️",
        "src": DOCS_DIR / "02-architecture.md",
        "dest": DOCS_DIR / "02-architecture.html",
        "category": "Core Architecture",
    },
    {
        "id": "code_walkthrough",
        "title": "03. Code Walkthrough",
        "icon": "🔍",
        "src": DOCS_DIR / "03-code-walkthrough.md",
        "dest": DOCS_DIR / "03-code-walkthrough.html",
        "category": "Core Architecture",
    },
    {
        "id": "testing",
        "title": "04. Testing Guide & Catalog",
        "icon": "🧪",
        "src": DOCS_DIR / "04-testing.md",
        "dest": DOCS_DIR / "04-testing.html",
        "category": "Guides & Workflows",
    },
    {
        "id": "salesforce",
        "title": "05. Salesforce External Services",
        "icon": "☁️",
        "src": DOCS_DIR / "05-salesforce-agentforce.md",
        "dest": DOCS_DIR / "05-salesforce-agentforce.html",
        "category": "Salesforce & Agentforce",
    },
    {
        "id": "salesforce_poc",
        "title": "06. Native Agentforce POC Plan",
        "icon": "⚡",
        "src": DOCS_DIR / "06-agentforce-native-poc.md",
        "dest": DOCS_DIR / "06-agentforce-native-poc.html",
        "category": "Salesforce & Agentforce",
    },
    {
        "id": "salesforce_native_guide",
        "title": "07. Brand New Org Setup & Native Guide",
        "icon": "🚀",
        "src": DOCS_DIR / "07-salesforce-agentforce-native-guide.md",
        "dest": DOCS_DIR / "07-salesforce-agentforce-native-guide.html",
        "category": "Salesforce & Agentforce",
    },
    {
        "id": "testing_guide",
        "title": "Living Testing Catalog",
        "icon": "📋",
        "src": ROOT_DIR / "TESTING_GUIDE.md",
        "dest": DOCS_DIR / "testing-guide.html",
        "category": "Guides & Workflows",
    },
    {
        "id": "learning_design",
        "title": "Design & Learning Map",
        "icon": "🗺️",
        "src": ROOT_DIR / "LEARNING_PATH_AND_DESIGN.md",
        "dest": DOCS_DIR / "learning-design.html",
        "category": "Guides & Workflows",
    },
    {
        "id": "slides",
        "title": "Team Adoption Slide Deck",
        "icon": "📊",
        "src": None,
        "dest_link": "adoption-slides.html",
        "category": "Presentation & Adoption",
    },
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title} - AgentChaos Docs</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Fira+Code:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({startOnLoad: true, theme: 'dark', securityLevel: 'loose'});</script>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(22, 30, 49, 0.7);
      --card-border: rgba(255, 255, 255, 0.08);
      --sidebar-bg: #0c1322;
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.25);
      --accent-secondary: #818cf8;
      --success: #34d399;
      --danger: #f87171;
      --warning: #fbbf24;
      --code-bg: #0f172a;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.7;
      display: flex;
      min-height: 100vh;
      overflow-x: hidden;
    }

    /* Sidebar Navigation */
    .sidebar {
      width: 300px;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      position: fixed;
      top: 0;
      bottom: 0;
      left: 0;
      z-index: 100;
      padding: 1.75rem 1.25rem;
      overflow-y: auto;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 1.25rem;
      font-weight: 800;
      color: #fff;
      text-decoration: none;
      margin-bottom: 2rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--card-border);
    }
    .brand-badge {
      background: linear-gradient(135deg, var(--accent), var(--accent-secondary));
      color: #090d16;
      font-size: 0.7rem;
      font-weight: 800;
      padding: 0.2rem 0.5rem;
      border-radius: 999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .nav-category {
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-muted);
      margin: 1.25rem 0 0.5rem 0.5rem;
    }

    .nav-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .nav-item a {
      display: flex;
      align-items: center;
      gap: 0.65rem;
      padding: 0.6rem 0.85rem;
      border-radius: 8px;
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.9rem;
      font-weight: 500;
      transition: all 0.15s ease;
    }

    .nav-item a:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.05);
    }

    .nav-item.active a {
      color: #fff;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.3);
      font-weight: 600;
    }

    /* Main Content Area */
    .content-wrapper {
      margin-left: 300px;
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .top-header {
      height: 60px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 3rem;
      background: rgba(9, 13, 22, 0.8);
      backdrop-filter: blur(10px);
      position: sticky;
      top: 0;
      z-index: 90;
    }

    .breadcrumbs {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .breadcrumbs span { color: #fff; font-weight: 600; }

    .header-links {
      display: flex;
      gap: 1rem;
    }
    .badge-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: rgba(52, 211, 153, 0.12);
      border: 1px solid rgba(52, 211, 153, 0.3);
      color: var(--success);
      padding: 0.25rem 0.75rem;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 600;
    }

    .main-content {
      max-width: 900px;
      margin: 0 auto;
      padding: 3rem 2rem 6rem;
      width: 100%;
    }

    /* Markdown Styling */
    h1 {
      font-size: 2.4rem;
      font-weight: 800;
      color: #fff;
      margin-bottom: 1.25rem;
      line-height: 1.2;
      background: linear-gradient(135deg, #fff 40%, var(--accent));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    h2 {
      font-size: 1.6rem;
      font-weight: 700;
      color: #f8fafc;
      margin-top: 2.75rem;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--card-border);
    }

    h3 {
      font-size: 1.25rem;
      font-weight: 600;
      color: #e2e8f0;
      margin-top: 2rem;
      margin-bottom: 0.75rem;
    }

    p {
      margin-bottom: 1.25rem;
      color: #cbd5e1;
      font-size: 1.02rem;
    }

    a {
      color: var(--accent);
      text-decoration: none;
      transition: color 0.15s;
    }
    a:hover {
      text-decoration: underline;
    }

    ul, ol {
      margin-bottom: 1.5rem;
      padding-left: 1.5rem;
      color: #cbd5e1;
    }
    li {
      margin-bottom: 0.5rem;
    }

    blockquote {
      border-left: 4px solid var(--accent);
      background: rgba(56, 189, 248, 0.06);
      padding: 1rem 1.25rem;
      border-radius: 0 8px 8px 0;
      margin: 1.5rem 0;
      color: #e0f2fe;
    }
    blockquote p:last-child { margin-bottom: 0; }

    hr {
      border: none;
      height: 1px;
      background: var(--card-border);
      margin: 2.5rem 0;
    }

    /* Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 2rem 0;
      background: var(--card-bg);
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid var(--card-border);
    }
    th, td {
      padding: 0.85rem 1.2rem;
      text-align: left;
      border-bottom: 1px solid var(--card-border);
      font-size: 0.92rem;
    }
    th {
      background: rgba(255, 255, 255, 0.04);
      color: #fff;
      font-weight: 600;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(255, 255, 255, 0.02); }

    /* Code Blocks */
    code:not(pre code) {
      font-family: 'Fira Code', monospace;
      font-size: 0.88em;
      background: rgba(255, 255, 255, 0.08);
      color: #38bdf8;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }

    pre {
      background: var(--code-bg) !important;
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 1.25rem !important;
      margin: 1.5rem 0;
      overflow-x: auto;
      font-family: 'Fira Code', monospace !important;
      font-size: 0.9rem !important;
      line-height: 1.5;
    }

    .mermaid {
      background: var(--code-bg);
      padding: 1.5rem;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      margin: 1.5rem 0;
      display: flex;
      justify-content: center;
    }

    /* Footer Pagination */
    .page-footer {
      display: flex;
      justify-content: space-between;
      margin-top: 4rem;
      padding-top: 2rem;
      border-top: 1px solid var(--card-border);
    }
    .page-btn {
      display: inline-flex;
      flex-direction: column;
      padding: 0.75rem 1.25rem;
      border-radius: 8px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      text-decoration: none;
      transition: all 0.2s;
    }
    .page-btn:hover {
      border-color: var(--accent);
      background: rgba(56, 189, 248, 0.08);
      text-decoration: none;
    }
    .page-btn .label {
      font-size: 0.75rem;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 700;
    }
    .page-btn .target {
      font-size: 0.95rem;
      font-weight: 600;
      color: #fff;
    }
  </style>
</head>
<body>

  <!-- Sidebar -->
  <aside class="sidebar">
    <a href="index.html" class="brand">
      <span>🐒⚡ AgentChaos</span>
      <span class="brand-badge">v1.1</span>
    </a>

    {sidebar_nav}
  </aside>

  <!-- Main Container -->
  <div class="content-wrapper">
    <header class="top-header">
      <div class="breadcrumbs">
        Docs / <span>{page_title}</span>
      </div>
      <div class="header-links">
        <div class="badge-pill">● 49 Unit Tests Passing</div>
      </div>
    </header>

    <main class="main-content">
      {rendered_content}

      <div class="page-footer">
        {prev_button}
        {next_button}
      </div>
    </main>
  </div>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
</body>
</html>
"""


def build_sidebar(current_id: str) -> str:
    categories: dict[str, list[dict]] = {}
    for page in PAGES:
        cat = page["category"]
        categories.setdefault(cat, []).append(page)

    html_parts = []
    for cat, items in categories.items():
        html_parts.append(f'<div class="nav-category">{cat}</div>')
        html_parts.append('<ul class="nav-list">')
        for item in items:
            active_cls = " active" if item["id"] == current_id else ""
            href = item.get("dest_link") or item["dest"].name
            icon = item["icon"]
            title = item["title"]
            html_parts.append(
                f'<li class="nav-item{active_cls}"><a href="{href}">'
                f'<span>{icon}</span> <span>{title}</span></a></li>'
            )
        html_parts.append('</ul>')

    return "\n".join(html_parts)


def transform_markdown(md_text: str) -> str:
    """Preprocess markdown: fix links to .html, fix callouts."""
    # Convert .md relative links to .html
    def replace_md_links(match: re.Match) -> str:
        text = match.group(1)
        url = match.group(2)
        # Only rewrite local relative links ending in .md
        if not url.startswith("http://") and not url.startswith("https://") and url.endswith(".md"):
            url = url[:-3] + ".html"
            # Normalize paths if needed
            if "01-concepts" in url:
                url = "01-concepts.html"
            elif "02-architecture" in url:
                url = "02-architecture.html"
            elif "03-code-walkthrough" in url:
                url = "03-code-walkthrough.html"
            elif "04-testing" in url:
                url = "04-testing.html"
            elif "05-salesforce-agentforce" in url:
                url = "05-salesforce-agentforce.html"
            elif "TESTING_GUIDE" in url:
                url = "testing-guide.html"
            elif "LEARNING_PATH_AND_DESIGN" in url:
                url = "learning-design.html"
            elif "README" in url:
                url = "index.html"
        return f"[{text}]({url})"

    md_text = re.sub(r'\[([^\]]+)\]\(([^)]+\.md)\)', replace_md_links, md_text)
    return md_text


def postprocess_html(html: str) -> str:
    """Transform mermaid pre/code blocks into <div class="mermaid">."""
    html = re.sub(
        r'<pre><code class="language-mermaid">([\s\S]*?)</code></pre>',
        r'<div class="mermaid">\1</div>',
        html,
    )
    # Add language classes to pre tags for Prism styling
    html = re.sub(
        r'<pre><code class="language-([a-zA-Z0-9_\-]+)">',
        r'<pre class="language-\1"><code class="language-\1">',
        html,
    )
    return html


def build_all_pages() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    md_parser = MarkdownIt("commonmark").enable("table")

    renderable_pages = [p for p in PAGES if p.get("src") and p["src"].exists()]

    for i, page in enumerate(renderable_pages):
        current_id = page["id"]
        page_title = page["title"]
        src_path = page["src"]
        dest_path = page["dest"]

        raw_md = src_path.read_text(encoding="utf-8")
        processed_md = transform_markdown(raw_md)
        rendered_body = md_parser.render(processed_md)
        rendered_body = postprocess_html(rendered_body)

        # Pagination buttons
        prev_btn = ""
        if i > 0:
            prev_p = renderable_pages[i - 1]
            prev_href = prev_p["dest"].name
            prev_btn = (
                f'<a href="{prev_href}" class="page-btn">'
                f'<span class="label">← Previous</span>'
                f'<span class="target">{prev_p["title"]}</span></a>'
            )

        next_btn = ""
        if i < len(renderable_pages) - 1:
            next_p = renderable_pages[i + 1]
            next_href = next_p["dest"].name
            next_btn = (
                f'<a href="{next_href}" class="page-btn" style="text-align: right;">'
                f'<span class="label">Next →</span>'
                f'<span class="target">{next_p["title"]}</span></a>'
            )

        sidebar_html = build_sidebar(current_id)

        full_html = (
            HTML_TEMPLATE
            .replace("{page_title}", page_title)
            .replace("{sidebar_nav}", sidebar_html)
            .replace("{rendered_content}", rendered_body)
            .replace("{prev_button}", prev_btn)
            .replace("{next_button}", next_btn)
        )

        dest_path.write_text(full_html, encoding="utf-8")
        print(f"✓ Generated: {dest_path}")

    print("\n🎉 Documentation site generated successfully in docs/!")


if __name__ == "__main__":
    build_all_pages()
