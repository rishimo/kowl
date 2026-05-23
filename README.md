# kowl — KitchenOwl CLI

A command-line interface for [KitchenOwl](https://kitchenowl.org), the self-hosted meal planner and grocery list app.

`kowl` lets you manage recipes, shopping lists, meal plans, expenses, and tags entirely from your terminal — useful for scripting, bulk operations, and headless automation.

## Installation

```bash
pip install -e .
```

Python 3.9+ required.

## Configuration

Set your KitchenOwl instance URL and API key via environment variables or a config file.

**Environment variables:**

```bash
export KITCHENOWL_URL=https://kitchenowl.example.com/api
export KITCHENOWL_API_KEY=your-bearer-token
export KOWL_HOUSEHOLD_ID=1   # optional — avoids --household-id on every command
```

**Config file** (`~/.config/kowl/config.toml`):

```toml
[api]
url = "https://kitchenowl.example.com/api"
key = "your-bearer-token"
household_id = 1
```

To get your API key, log in to KitchenOwl, go to **Profile → API Tokens**, and create a new token.

## Usage

```
kowl [--json | --yaml] [--household-id INT] COMMAND [ARGS]
```

Global flags `--json` and `--yaml` switch all output to machine-readable format.

### Recipes

```bash
kowl recipe list
kowl recipe get RECIPE_ID
kowl recipe search "pasta"
kowl recipe create --name "Tomato Soup" --cook-time 25 --yields 4
kowl recipe update RECIPE_ID --name "New Name" --yields 2
kowl recipe update RECIPE_ID --file recipe.yaml   # replace recipe from YAML file
kowl recipe edit RECIPE_ID                         # open in $EDITOR as YAML
kowl recipe bulk-edit-items RECIPE_ID              # edit only the ingredients in $EDITOR
kowl recipe import recipe.yaml                     # create recipe from YAML file
kowl recipe scrape URL                             # scrape recipe from a web page
kowl recipe add-item RECIPE_ID --name "Salt" --description "1 tsp"
kowl recipe remove-item RECIPE_ID ITEM_ID
kowl recipe add-tag RECIPE_ID "vegetarian"
kowl recipe remove-tag RECIPE_ID "vegetarian"
kowl recipe delete RECIPE_ID [--yes]
```

### Shopping lists

```bash
kowl shop list
kowl shop items LIST_ID
kowl shop create --name "Weekly Shop"
kowl shop add LIST_ID --name "Eggs" --description "12 pcs"
kowl shop remove LIST_ID ITEM_ID
kowl shop delete LIST_ID [--yes]
```

### Meal planner

```bash
kowl plan list
kowl plan add --recipe-id 42 --day Monday
kowl plan remove --recipe-id 42 --day Monday
```

### Expenses

```bash
kowl expense list
kowl expense create --name "Groceries" --amount 45.50 --paid-by alice
kowl expense delete EXPENSE_ID [--yes]
```

### Tags

```bash
kowl tag list
kowl tag create --name "vegan"
```

### Households

```bash
kowl household list
```

## Recipe YAML format

`kowl recipe import`, `kowl recipe update --file`, and `kowl recipe edit` all use the same YAML structure:

```yaml
name: Tomato Soup
description: Simple blended soup
time: 30
cook_time: 25
prep_time: 5
yields: 4
source: https://example.com/recipe
tags:
  - soup
  - vegetarian
items:
  - name: Tomatoes
    description: 6 medium
    optional: false
  - name: Salt
    description: 1 tsp
    optional: false
```

## Output formats

By default, output is formatted for humans using Rich. Add `--json` or `--yaml` to get structured output suitable for scripting:

```bash
# Export all recipes
kowl --yaml recipe list > recipes.yaml

# Get a recipe as JSON and pipe to jq
kowl --json recipe get 42 | jq '.items[].name'
```

## Bulk operations

See [USAGE.md](USAGE.md) for recipes (pun intended) covering:
- Exporting all recipes to individual YAML files
- Importing a directory of YAML recipes
- Building a shopping list from multiple recipes
- Replacing recipe contents from a YAML file

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Development

The project layout:

```
kowl/
├── cli.py          # Root click group
├── api.py          # HTTP client
├── config.py       # Config loader
├── output.py       # Rich + JSON/YAML renderers
└── commands/
    ├── recipe.py
    ├── shopping.py
    ├── planner.py
    ├── expense.py
    └── tag.py
```

## License

MIT
