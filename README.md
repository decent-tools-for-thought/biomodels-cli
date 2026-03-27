<div align="center">

# biomodels-cli

![Python](https://img.shields.io/badge/python-3.11%2B-eab308)
![License](https://img.shields.io/badge/license-MIT-ca8a04)

BioModels REST API command-line client for model discovery, retrieval, mapping lookups, and download workflows from the shell.

</div>

> [!IMPORTANT]
> This codebase is entirely AI-generated. It is useful to me, I hope it might be useful to others, and issues and contributions are welcome.

## Map
- [Install](#install)
- [Functionality](#functionality)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Output and Exit Codes](#output-and-exit-codes)
- [Development](#development)
- [Credits](#credits)

## Install
$$\color{#EAB308}Install \space \color{#CA8A04}Tool$$

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install .
biomodels --help
```

## Functionality
$$\color{#EAB308}Model \space \color{#CA8A04}Access$$
- `biomodels model get`: fetch model details by identifier.
- `biomodels model files`: list files attached to a model.
- `biomodels model identifiers`: list all public model identifiers.
- `biomodels model download`: download a model archive or one file from a model.

$$\color{#EAB308}Search \space \color{#CA8A04}Workflows$$
- `biomodels search query`: run BioModels query syntax with pagination and sorting controls.
- `biomodels search all`: page through all search results and return a merged result set.
- `biomodels search download`: download main files for one or more model IDs.

$$\color{#EAB308}Parameter \space \color{#CA8A04}Queries$$
- `biomodels params search`: query parameter search endpoint with paging, sorting, and format selection.
- `biomodels params grep`: filter and project parameter-search entries by model/entity/organism/fields.

$$\color{#EAB308}Mapping \space \color{#CA8A04}Resolution$$
- `biomodels p2m missing`: list Path2Models IDs no longer directly accessible.
- `biomodels p2m representative`: resolve one Path2Models ID to its representative model.
- `biomodels p2m representatives`: resolve many Path2Models IDs in one call.
- `biomodels pdgsmm missing`: list PDGSMM IDs no longer directly accessible.
- `biomodels pdgsmm representative`: resolve one PDGSMM ID to its representative model.
- `biomodels pdgsmm representatives`: resolve many PDGSMM IDs in one call.
- `biomodels resolve`: high-level resolver over mixed ID families (`auto`, `p2m`, `pdgsmm`).

$$\color{#EAB308}High-Level \space \color{#CA8A04}Utilities$$
- `biomodels find`: accept plain text or query syntax and normalize to a model search query.
- `biomodels show`: return consolidated model details and file summary.
- `biomodels fetch model`: helper to download OMEX or main XML for one model.
- `biomodels fetch query`: search and then download matched models as a zip.
- `biomodels ids`: export identifiers with optional prefix filters and limits.
- `biomodels stats query`: summarize returned search page (matches, curation, formats, submitters).
- `biomodels inspect query`: normalize and optionally validate a query upstream.

$$\color{#EAB308}Raw \space \color{#CA8A04}and \space \color{#CA8A04}Docs$$
- `biomodels raw`: send a direct GET call to an API path with repeatable query params.
- `biomodels docs`: print machine-readable command documentation generated from the parser.

Common global options:
- `--base-url`: override BioModels base URL.
- `--timeout`: request timeout in seconds.
- `--config`: explicit config file path.
- `--output text|json|jsonl`: output format mode.

Endpoint format controls:
- `--api-format json|xml|html`: on model/search/mapping commands.
- `--api-format json|xml|csv`: on `params search`.

`--api-format` controls upstream content negotiation (`format` query parameter and `Accept` header). Non-JSON upstream formats are printed as raw text.

## Configuration
$$\color{#EAB308}Save \space \color{#CA8A04}Defaults$$

Configuration precedence (high to low):
1. CLI flags (`--base-url`, `--timeout`)
2. Environment (`BIOMODELS_BASE_URL`, `BIOMODELS_TIMEOUT`)
3. Config file (`$XDG_CONFIG_HOME/biomodels-cli/config.json` or `~/.config/biomodels-cli/config.json`)
4. Built-in defaults

Example config:

```json
{
  "base_url": "https://www.biomodels.org/",
  "timeout": 30
}
```

## Quick Start
$$\color{#EAB308}Try \space \color{#CA8A04}Queries$$

```bash
biomodels search query 'name:insulin'
biomodels --output json search query 'PUBMED:"27869123"'
biomodels --output json find insulin --limit 10
biomodels find pubmed:27869123

biomodels --output json model files BIOMD0000000123
biomodels --output json show BIOMD0000000123 --full
biomodels model get BIOMD0000000123 --api-format xml

biomodels model download BIOMD0000000123 -o BIOMD0000000123.omex
biomodels fetch model BIOMD0000000123 --main-xml
biomodels fetch query 'name:insulin' --limit 25 -o insulin-models.zip

biomodels --output json params grep --query insulin --model BIOMD0000000580 --fields model,entity,parameters
biomodels --output json resolve BMID000000112902 MODEL1707110145 --family auto
biomodels --output json stats query 'name:insulin'
biomodels --output json inspect query insulin --validate

biomodels raw /search --param query='name:glucose' --param numResults=5 --output json
biomodels --output json docs
```

## Output and Exit Codes
- `text`: human-readable summaries.
- `json`: indented JSON.
- `jsonl`: JSON-lines for list/stream workflows.

Exit codes:
- `0`: success.
- `2`: usage/config/input validation errors.
- `1`: runtime/API/network/decode failures.

## Development

```bash
pip install -e .[dev]
pytest
ruff check .
mypy src
```

## Credits

This client is built for the BioModels REST API and is not affiliated with EMBL-EBI.

Credit goes to BioModels maintainers and contributors for the model repository, data services, and API documentation this tool depends on.

- https://www.biomodels.org/docs/
- https://www.biomodels.org/docs/biomodels-jummp-swagger.json
