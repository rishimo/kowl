# kowl — KitchenOwl CLI

A command-line interface for the [KitchenOwl](https://kitchenowl.org) self-hosted meal planner and shopping list app.

## Project layout

```
kitchenowl-cli/
├── kowl/
│   ├── __init__.py        # Package metadata
│   ├── cli.py             # Root click group + household sub-group
│   ├── api.py             # HTTP client (KitchenOwlClient)
│   ├── config.py          # Config loader (env vars + ~/.config/kowl/config.toml)
│   ├── output.py          # Rich-based renderers + JSON/YAML output helpers
│   └── commands/
│       ├── __init__.py
│       ├── recipe.py      # kowl recipe ...
│       ├── shopping.py    # kowl shop ...
│       ├── planner.py     # kowl plan ...
│       ├── expense.py     # kowl expense ...
│       └── tag.py         # kowl tag ...
├── tests/
│   ├── test_api.py        # Unit tests for KitchenOwlClient (mocked HTTP)
│   └── test_commands.py   # Integration tests via click.testing.CliRunner
├── pyproject.toml
└── CLAUDE.md              # This file
```

## Setup

```bash
pip install -e ".[dev]"   # or just: pip install -e .
```

Required environment variables:

| Variable             | Default                               | Description                 |
|----------------------|---------------------------------------|-----------------------------|
| `KITCHENOWL_URL`     | `https://kitchenowl.example.com/api`  | API base URL                |
| `KITCHENOWL_API_KEY` | (required)                            | Bearer token                |
| `KOWL_HOUSEHOLD_ID`  | (none)                                | Default household ID        |

Or store them in `~/.config/kowl/config.toml`:

```toml
[api]
url = "https://kitchenowl.example.com/api"
key = "your-bearer-token"
```

## Running tests

```bash
pytest tests/ -v
```

## Key design decisions

- **`kowl/api.py`** — single `KitchenOwlClient` class with one `_request` helper that handles all error mapping. A module-level `client` singleton is imported by command modules to avoid repeated instantiation.
- **`kowl/output.py`** — `output()` dispatcher checks `--json` / `--yaml` flags from the Click context (`ctx.obj`) and calls the appropriate renderer. Rich is only used for the default human-readable path.
- **`kowl recipe edit`** — fetches recipe, serialises to YAML with `_recipe_to_yaml_dict()`, writes to a temp file, calls `$EDITOR` via `subprocess.call`, parses the result, diffs against original, and applies granular API calls (update metadata, add/remove items). The `_open_editor()` helper can be patched in tests.
- **`kowl recipe import FILE`** — reads a YAML file, creates a bare recipe to get an ID, then POSTs the full payload (metadata + items + tags) to `POST /recipe/{id}` in one shot. Uses `_yaml_dict_to_api_body()` to strip item fields down to `name`/`description`/`optional`.
- **`kowl recipe update RECIPE_ID --file FILE`** — reads a YAML file and POSTs the full payload to `POST /recipe/{id}`, replacing metadata, items, and tags atomically. Without `--file`, behaves as before (metadata-only patch from CLI flags).
- **Global flags** (`--json`, `--yaml`, `--household-id`) are attached to the root `cli` group and stored in `ctx.obj` so every sub-command can read them via `ctx.obj`.

## Commands reference

```
kowl household list
kowl recipe list --household-id INT
kowl recipe get RECIPE_ID
kowl recipe search --household-id INT QUERY
kowl recipe create --household-id INT --name TEXT [options]
kowl recipe update RECIPE_ID [options]
kowl recipe delete RECIPE_ID [--yes]
kowl recipe add-item RECIPE_ID --name TEXT [--description TEXT] [--optional]
kowl recipe remove-item RECIPE_ID ITEM_ID
kowl recipe add-tag RECIPE_ID TAG_NAME
kowl recipe remove-tag RECIPE_ID TAG_NAME
kowl recipe edit RECIPE_ID
kowl recipe bulk-edit-items RECIPE_ID
kowl recipe scrape --household-id INT URL
kowl recipe import --household-id INT FILE
kowl recipe update RECIPE_ID --file FILE
kowl shop list --household-id INT
kowl shop items LIST_ID
kowl shop add LIST_ID --name TEXT [--description TEXT]
kowl shop remove LIST_ID ITEM_ID
kowl shop create --household-id INT --name TEXT
kowl shop delete LIST_ID [--yes]
kowl plan list --household-id INT
kowl plan add --household-id INT --recipe-id INT --day TEXT
kowl plan remove --household-id INT --recipe-id INT --day TEXT
kowl expense list --household-id INT
kowl expense create --household-id INT --name TEXT --amount FLOAT [--paid-by TEXT]
kowl expense delete EXPENSE_ID [--yes]
kowl tag list --household-id INT
kowl tag create --household-id INT --name TEXT
```
