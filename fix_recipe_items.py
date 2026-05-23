#!/usr/bin/env python3
"""
Bulk fix recipe items by programmatically reconciling ingredient quantities.

This script fixes recipes where quantity information is embedded in the ingredient
name field and needs to be moved to the description field.

Usage:
    # Fix a single recipe
    python3 fix_recipe_items.py RECIPE_ID [--dry-run]

    # Fix multiple recipes
    python3 fix_recipe_items.py --recipe-ids 4,6,8,12,14 [--dry-run]

    # Fix recipes with issues from audit report
    python3 fix_recipe_items.py --recipe-ids 26,8,23,50,15,34,62,44,35,48,27,58,6,4,22,31,47,36,28,32,14,24,12 --dry-run

Example:
    # Preview changes without applying
    python3 fix_recipe_items.py 10 --dry-run

    # Fix recipe and apply changes
    python3 fix_recipe_items.py 10

    # Fix multiple recipes
    python3 fix_recipe_items.py --recipe-ids 4,6,8 --dry-run
"""

import sys
import re
import click
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add kowl to path
sys.path.insert(0, str(Path(__file__).parent))

from kowl.api import client, KowlAPIError
from kowl.output import print_success, print_warning, print_error, console
import yaml


def split_quantity_from_name(item_name: str) -> Tuple[str, str]:
    """
    Split quantity prefix from ingredient name.

    Examples:
        "1.5 cups broccoli" → ("Broccoli", "1.5 cups")
        "2 tbsp minced garlic" → ("Garlic", "2 tbsp; minced")
        "1/2 tsp salt" → ("Salt", "1/2 tsp")
        "3-4 oz chicken" → ("Chicken", "3-4 oz")
        "Garlic" → ("Garlic", "")

    Returns: (cleaned_name, quantity_description)
    """
    name = item_name.strip()

    # Pattern for quantity at start: number/fraction + optional unit + remaining
    # Matches: "1.5 cups", "2 tbsp", "1/2 tsp", "3-4 oz", "2-3" etc.
    pattern = r'^([0-9]+(?:[./\-][0-9]*)?)\s*([a-z]+\.?)?\s+(.+)$'
    match = re.match(pattern, name, re.IGNORECASE)

    if match:
        quantity = match.group(1)
        unit = match.group(2) or ""
        remainder = match.group(3).strip()

        # Common prep/cooking verbs to extract from name
        prep_keywords = [
            'minced', 'chopped', 'diced', 'sliced', 'grated', 'shredded',
            'crushed', 'ground', 'peeled', 'deseeded', 'blanched', 'cooked',
            'roasted', 'toasted', 'melted', 'softened', 'beaten', 'zested',
            'julienned', 'thinly', 'finely', 'roughly', 'halved', 'quartered',
            'pitted', 'seeded', 'trimmed', 'rinsed', 'drained', 'pressed',
            'divided'
        ]

        prep_part = ""
        item_name_only = remainder

        # Try to extract prep keyword from remainder
        for prep in prep_keywords:
            if f' {prep}' in f' {remainder.lower()} ':
                # Found a prep keyword, split on it
                parts = re.split(rf'\b{prep}\b', remainder, flags=re.IGNORECASE, maxsplit=1)
                if len(parts) == 2:
                    prep_suffix = parts[1].strip()
                    if prep_suffix and prep_suffix[0] in ',-':
                        # e.g., "minced-ish" or ", minced"
                        prep_part = prep + prep_suffix
                    else:
                        prep_part = prep
                        if prep_suffix:
                            prep_part += f' {prep_suffix}'
                    item_name_only = parts[0].strip()
                    break

        # Build description: quantity unit (+ prep if found)
        description_parts = [quantity]
        if unit:
            description_parts.append(unit)

        description = ' '.join(description_parts)
        if prep_part:
            description += f'; {prep_part.strip()}'

        # Clean up item name
        item_name_clean = item_name_only.strip()
        if item_name_clean:
            # Capitalize first letter
            item_name_clean = item_name_clean[0].upper() + item_name_clean[1:]

        return (item_name_clean, description)

    # No quantity found, return as-is
    return (name, "")


def fetch_recipe(recipe_id: int) -> Optional[Dict]:
    """Fetch recipe from API."""
    try:
        return client.get_recipe(recipe_id)
    except KowlAPIError as e:
        print_error(f"Failed to fetch recipe {recipe_id}: {e}")
        return None


def analyze_items(recipe: Dict) -> List[Dict]:
    """
    Analyze items and identify those needing fixes.

    Returns list of dicts with:
    - item_id
    - original_name
    - original_description
    - needs_fix (bool)
    - fixed_name
    - fixed_description
    - optional
    """
    items = recipe.get('items', [])
    analysis = []

    for item in items:
        orig_name = item.get('name', '').strip()
        orig_desc = (item.get('description', '') or '').strip()

        # Check if name starts with quantity (digit)
        has_quantity_in_name = bool(re.match(r'^[0-9]', orig_name))

        if has_quantity_in_name and not orig_desc:
            # Name has quantity but description is empty - needs fixing
            fixed_name, fixed_desc = split_quantity_from_name(orig_name)
            needs_fix = fixed_name != orig_name
        else:
            fixed_name, fixed_desc = orig_name, orig_desc
            needs_fix = False

        analysis.append({
            'item_id': item.get('id'),
            'original_name': orig_name,
            'original_description': orig_desc,
            'needs_fix': needs_fix,
            'fixed_name': fixed_name,
            'fixed_description': fixed_desc,
            'optional': item.get('optional', False),
        })

    return analysis


def print_analysis(analysis: List[Dict], recipe_id: int, recipe_name: str = "") -> None:
    """Print analysis of items needing fixes."""
    total = len(analysis)
    needs_fix = [a for a in analysis if a['needs_fix']]

    recipe_label = f"Recipe {recipe_id}"
    if recipe_name:
        recipe_label += f": {recipe_name}"

    console.print(f"[bold]{recipe_label}[/bold] — {total} items, {len(needs_fix)} need fixing")

    if not needs_fix:
        console.print("[green]✓ All items properly formatted[/green]")
        return

    console.print()
    for item in needs_fix:
        console.print(f"  [dim]ID {item['item_id']}:[/dim] {item['original_name']!r}")
        console.print(f"    [green]→ name:[/green] {item['fixed_name']!r}")
        console.print(f"    [green]→ desc:[/green] {item['fixed_description']!r}")
    console.print()


def build_fixed_items(analysis: List[Dict]) -> List[Dict]:
    """Build fixed items list for bulk-edit."""
    fixed = []
    for item in analysis:
        fixed.append({
            'name': item['fixed_name'],
            'description': item['fixed_description'],
            'optional': item['optional'],
        })
    return fixed


def apply_fixes_via_bulk_edit(recipe_id: int, fixed_items: List[Dict]) -> bool:
    """
    Apply fixed items using the bulk-edit-items flow.

    This internally uses the same _apply_recipe_edits logic.
    """
    from kowl.commands.recipe import _apply_recipe_edits, _recipe_to_yaml_dict

    try:
        original_recipe = client.get_recipe(recipe_id)
    except KowlAPIError as e:
        print_error(f"Failed to fetch recipe for apply: {e}")
        return False

    original_dict = _recipe_to_yaml_dict(original_recipe)
    edited_dict = dict(original_dict)
    edited_dict['items'] = fixed_items

    try:
        _apply_recipe_edits(recipe_id, original_dict, edited_dict)
        return True
    except Exception as e:
        print_error(f"Failed to apply edits: {e}")
        import traceback
        traceback.print_exc()
        return False


@click.command()
@click.argument('recipe_id', type=int, required=False)
@click.option('--recipe-ids', type=str, help='Comma-separated recipe IDs')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying')
def main(recipe_id: Optional[int], recipe_ids: Optional[str], dry_run: bool) -> None:
    """Fix recipe items by splitting quantity from name field."""

    # Determine which recipes to process
    ids_to_process = []
    if recipe_id:
        ids_to_process = [recipe_id]
    elif recipe_ids:
        ids_to_process = [int(x.strip()) for x in recipe_ids.split(',')]
    else:
        click.echo("Error: Provide RECIPE_ID or --recipe-ids")
        sys.exit(1)

    total_fixed = 0

    for rid in ids_to_process:
        # Fetch and analyze
        recipe = fetch_recipe(rid)
        if not recipe:
            continue

        analysis = analyze_items(recipe)

        # Print analysis
        print_analysis(analysis, rid, recipe.get('name', ''))

        needs_fix = [a for a in analysis if a['needs_fix']]
        if not needs_fix:
            continue

        if dry_run:
            print_warning(f"DRY RUN: Would fix {len(needs_fix)} items")
        else:
            # Apply fixes
            fixed_items = build_fixed_items(analysis)
            if apply_fixes_via_bulk_edit(rid, fixed_items):
                print_success(f"✓ Fixed {len(needs_fix)} items in recipe {rid}\n")
                total_fixed += len(needs_fix)
            else:
                print_error(f"✗ Failed to fix recipe {rid}\n")

    if not dry_run and total_fixed > 0:
        console.print(f"[bold green]Summary: Fixed {total_fixed} items across {len(ids_to_process)} recipe(s)[/bold green]")


if __name__ == '__main__':
    main()
