# biomodels-cli

`biomodels` is a production-ready command-line client for the [BioModels REST API](https://www.biomodels.org/docs/) that supports discovery, retrieval, and download workflows with script-friendly output.

## API profile

- API name: BioModels REST API
- Purpose: Access curated mathematical models of biological systems and related metadata/files
- Primary users: computational biology and systems biology researchers, pipeline engineers
- Auth model: none (public API)
- Base URL: `https://www.biomodels.org/`
- OpenAPI: `https://www.biomodels.org/docs/biomodels-jummp-swagger.json`

## Install

Python 3.11+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install .
```

Run:

```bash
biomodels --help
```

## Command surface

Top-level command families:

- `model`: model details, files, identifiers, downloads
- `search`: model search and search-result downloads
- `params`: parameter search endpoint
- `p2m`: Path2Models missing/representative mapping
- `pdgsmm`: PDGSMM missing/representative mapping
- `raw`: generic escape hatch for direct endpoint calls

Common options:

- `--base-url`: override API server URL
- `--timeout`: request timeout in seconds
- `--config`: path to JSON config file
- `--output {text,json,jsonl}`: output mode

Bare invocation prints help and exits `0`.

## Quick start

Search models:

```bash
biomodels search query 'name:insulin'
biomodels --output json search query 'PUBMED:"27869123"'
```

Fetch all pages from a query (useful for pipelines):

```bash
biomodels --output jsonl search all '*' --page-size 100 --limit 250
```

Get model details and files:

```bash
biomodels model get BIOMD0000000123
biomodels --output json model files BIOMD0000000123
```

Download model assets:

```bash
biomodels model download BIOMD0000000123 -o BIOMD0000000123.omex
biomodels model download BIOMD0000000123 --filename model.xml -o model.xml
biomodels search download BIOMD0000000123 BIOMD0000000231 -o models.zip
```

Path2Models and PDGSMM mappings:

```bash
biomodels p2m missing
biomodels p2m representative BMID000000112902
biomodels pdgsmm representatives MODEL1707110145 MODEL1707112456
```

Raw endpoint access:

```bash
biomodels raw /search --param query='name:glucose' --param numResults=5 --output json
```

## Configuration

Configuration precedence (highest to lowest):

1. CLI flags (`--base-url`, `--timeout`)
2. Environment variables (`BIOMODELS_BASE_URL`, `BIOMODELS_TIMEOUT`)
3. Config file (`$XDG_CONFIG_HOME/biomodels-cli/config.json` or `~/.config/biomodels-cli/config.json`)
4. Built-in defaults

Example config file:

```json
{
  "base_url": "https://www.biomodels.org/",
  "timeout": 30
}
```

## Output modes

- `text`: human-readable summaries
- `json`: indented JSON for structured consumption
- `jsonl`: JSON-lines for list/stream workflows

The tool preserves upstream fields and avoids lossy transformation.

## Error handling and exit codes

- `0`: success
- `2`: usage/config/input validation errors
- `1`: runtime failures (network/API/decode)

User-facing errors are concise and actionable (timeout, not-found, rate limit, malformed response, etc.).

## Development

Install with dev tools:

```bash
pip install -e .[dev]
```

Verification commands:

```bash
pytest
ruff check .
mypy src
```

## API caveats

- Some endpoint response shapes vary (especially parameter search and mapping endpoints); prefer `--output json` for stability in automation.
- This release intentionally focuses on the public read/search/download API. Write/update workflows are not available in BioModels public API docs.

## Attribution

This CLI wraps the BioModels API. BioModels content and services are provided by EMBL-EBI and collaborators. See the upstream docs and terms:

- https://www.biomodels.org/docs/
- https://www.ebi.ac.uk/data-protection/privacy-notice/embl-ebi-public-website
