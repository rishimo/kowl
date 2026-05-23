# kowl Usage Guide

Practical workflows for common tasks with the KitchenOwl CLI.

## Setup

```bash
export KITCHENOWL_URL=https://kitchenowl.example.com/api
export KITCHENOWL_API_KEY=your-bearer-token
export KOWL_HOUSEHOLD_ID=1   # optional default, avoids --household-id on every command
```

---

## Bulk export recipes

Export all recipes in a household to a YAML file for backup or migration:

```bash
kowl --yaml recipe list > recipes.yaml
```

Export a single recipe with full ingredients and tags:

```bash
kowl --yaml recipe get 42 > chicken-piccata.yaml
```

Export all recipes one file each (bash loop):

```bash
kowl --json recipe list | python3 -c "
import json, sys
for r in json.load(sys.stdin):
    print(r['id'], r['name'].replace('/', '-'))
" | while read id name; do
    kowl --yaml recipe get "$id" > "recipes/${name}.yaml"
done
```

---

## Import / create recipes from YAML

Given a YAML file like:

```yaml
name: Chicken Piccata
description: Classic Italian chicken with lemon and capers
time: 30
cook_time: 20
prep_time: 10
yields: 4
source: https://example.com/chicken-piccata
tags:
  - chicken
  - italian
items:
  - name: Chicken Breast
    description: 4 fillets (about 1.5 lbs)
    optional: false
  - name: Capers
    description: 3 tbsp
    optional: false
  - name: Lemon
    description: 2 lemons, juiced
    optional: false
  - name: Butter
    description: 3 tbsp
    optional: false
```

Create the recipe with all its ingredients and tags in one command:

```bash
kowl recipe import chicken-piccata.yaml
```

Import all YAML files in a directory:

```bash
for f in recipes/*.yaml; do
    kowl recipe import "$f"
done
```

---

## Update a recipe

Update metadata fields individually:

```bash
kowl recipe update 42 --name "Roasted Tomato Soup" --yields 4 --cook-time 30
```

Replace a recipe entirely from a YAML file (metadata, items, and tags in one shot):

```bash
kowl recipe update 42 --file chicken-piccata.yaml
```

Open the recipe in your `$EDITOR` as YAML and apply changes on save:

```bash
kowl recipe edit 42
```

This lets you rename ingredients, change descriptions, add/remove tags, and update all metadata fields in one pass. Items you delete from the file are removed; new entries are added.

---

## Edit ingredients only

To edit just the ingredient list without touching the recipe metadata:

```bash
kowl recipe bulk-edit-items 42
```

Your editor opens with only the `items:` block. Add, remove, or modify lines and save.

---

## Create a combined shopping list

Pull items from multiple recipes into one shopping list:

```bash
# Create a new list
LIST_ID=$(kowl --json shop create --name "Weekly Shop" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Add ingredients from two recipes
for recipe_id in 42 57; do
    kowl --json recipe get "$recipe_id" \
      | python3 -c "
import json, sys, subprocess
recipe = json.load(sys.stdin)
list_id = '$LIST_ID'
for item in recipe.get('items', []):
    subprocess.run([
        'kowl', 'shop', 'add', list_id,
        '--name', item['name'],
        '--description', item.get('description', ''),
    ])
"
done

# Review the list
kowl shop items "$LIST_ID"
```

---

## Quick reference

```
# Recipes
kowl --yaml recipe list
kowl --yaml recipe get RECIPE_ID
kowl recipe edit RECIPE_ID
kowl recipe bulk-edit-items RECIPE_ID
kowl recipe import FILE
kowl recipe create --name "..." --cook-time N --yields N
kowl recipe update RECIPE_ID --name "..." --yields N
kowl recipe update RECIPE_ID --file chicken-piccata.yaml
kowl recipe add-item RECIPE_ID --name "..." --description "..."
kowl recipe remove-item RECIPE_ID ITEM_ID
kowl recipe add-tag RECIPE_ID TAG
kowl recipe remove-tag RECIPE_ID TAG
kowl recipe scrape --household-id 1 https://example.com/recipe

# Shopping
kowl --yaml shop list
kowl --yaml shop items LIST_ID
kowl shop create --name "..."
kowl shop add LIST_ID --name "..." --description "..."
kowl shop remove LIST_ID ITEM_ID
kowl shop delete LIST_ID --yes

# Planner
kowl --yaml plan list
kowl plan add --recipe-id 42 --day Monday
kowl plan remove --recipe-id 42 --day Monday

# Expenses
kowl --yaml expense list
kowl expense create --name "Groceries" --amount 45.50 --paid-by alice
kowl expense delete EXPENSE_ID --yes

# Tags
kowl --yaml tag list
kowl tag create --name "vegan"
```
