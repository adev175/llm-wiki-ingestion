# llm-wiki-ingest — Standalone MCP Server

Standalone MCP server, completely independent from llm-wiki.  
**Goal:** receive different input formats → return clean markdown.  
Does not know about wiki, does not call wiki tools, does not import from llm-wiki.

---

## Repo structure

```
llm-wiki-ingest/
├── server.py               # Single MCP server
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

## Tools

| Tool | Input | Output |
|------|-------|--------|
| `ingest_pdf` | `/input/paper.pdf` | Markdown + Obsidian image embeds |
| `ingest_pdf_url` | arXiv or direct PDF URL | Markdown |
| `ingest_excel` | `/input/backtest.xlsx` | Markdown tables per sheet |
| `ingest_clipboard` | HTML or plain text | Clean markdown |
| `ingest_note` | Raw unstructured text | Structured markdown + frontmatter |
| `ingest_image` | `/input/chart.png` | `![[assets/...]]` Obsidian embed |

---

## Usage with Claude Desktop

```json
{
  "mcpServers": {
    "llm-wiki-ingest": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/vault/assets:/assets",
        "-v", "/path/to/downloads:/input:ro",
        "llm-wiki-ingest-mcp"
      ]
    }
  }
}
```

- `/assets` — where images extracted from PDFs are saved (write)
- `/input` — where users place files to ingest (read-only)
- Container is auto-removed after each session (`--rm`)

---

## Build & run

```bash
# Build image
docker build -t llm-wiki-ingest-mcp .

# Manual test run
docker run -i --rm \
  -v ~/vault/assets:/assets \
  -v ~/Downloads:/input:ro \
  llm-wiki-ingest-mcp
```

---

## Hard constraints

- No imports from llm-wiki
- No external LLM API calls
- Writes only to `/assets/`
- Every tool returns `str` (markdown)
- Error strings start with `✗`
- Marker failure → silent fallback to pymupdf4llm
