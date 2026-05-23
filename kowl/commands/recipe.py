"""Recipe commands for kowl.

Implements the `kowl recipe` command group including the interactive
`edit` and `bulk-edit-items` subcommands that open $EDITOR.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from typing import Any, Dict, List, Optional

import click
import yaml

from ..api import KowlAPIError, client
from ..config import resolve_household_id
from ..output import (
    console,
    output,
    print_error,
    print_success,
    print_warning,
    render_recipe_detail,
    render_recipes,
    yaml_recipes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _recipe_to_yaml_dict(recipe: Dict[str, Any], include_ids: bool = True) -> Dict[str, Any]:
    """Serialize a recipe API object to a YAML-friendly dict."""
    def _item(item: Dict[str, Any]) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if include_ids:
            d["id"] = item.get("id")
        d["name"] = item.get("name", "")
        d["description"] = item.get("description", "") or ""
        d["optional"] = bool(item.get("optional", False))
        return d

    return {
        "name": recipe.get("name", ""),
        "description": recipe.get("description", "") or "",
        "time": recipe.get("time", 0) or 0,
        "cook_time": recipe.get("cook_time", 0) or 0,
        "prep_time": recipe.get("prep_time", 0) or 0,
        "yields": recipe.get("yields", 0) or 0,
        "visibility": recipe.get("visibility", 0) or 0,
        "source": recipe.get("source", "") or "",
        "items": [_item(i) for i in recipe.get("items", [])],
        "tags": [t.get("name", "") for t in recipe.get("tags", [])],
    }


def _yaml_dict_to_api_body(yaml_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a YAML recipe dict (as written by _recipe_to_yaml_dict) to a POST body."""
    body: Dict[str, Any] = {}
    for key in ("name", "description", "cook_time", "prep_time", "time", "yields", "source", "visibility"):
        if key in yaml_dict:
            body[key] = yaml_dict[key]
    if "items" in yaml_dict:
        body["items"] = [
            {
                "name": item.get("name", ""),
                "description": item.get("description", "") or "",
                "optional": bool(item.get("optional", False)),
            }
            for item in (yaml_dict["items"] or [])
        ]
    if "tags" in yaml_dict:
        body["tags"] = list(yaml_dict["tags"] or [])
    return body


def _open_editor(content: str) -> str:
    """Write content to a temp YAML file, open $EDITOR, return edited content."""
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="kowl-recipe-",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(content)
        tmpfile = tmp.name

    try:
        ret = subprocess.call([editor, tmpfile])
        if ret != 0:
            raise click.ClickException(f"Editor exited with code {ret}")
        with open(tmpfile, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmpfile)
        except OSError:
            pass


def _apply_recipe_edits(
    recipe_id: int,
    original: Dict[str, Any],
    edited: Dict[str, Any],
) -> None:
    """Diff original vs edited YAML dicts and apply changes via API."""
    # ---- Metadata fields ----
    meta_keys = ["name", "description", "cook_time", "prep_time", "time", "yields", "source", "visibility"]
    meta_patch: Dict[str, Any] = {}
    for key in meta_keys:
        if edited.get(key) != original.get(key):
            meta_patch[key] = edited.get(key)

    if meta_patch:
        try:
            client.update_recipe(recipe_id, meta_patch)
            print_success(f"Updated metadata: {', '.join(meta_patch.keys())}")
        except KowlAPIError as e:
            print_error(str(e))

    # ---- Tags ----
    orig_tags: List[str] = original.get("tags", [])
    edit_tags: List[str] = edited.get("tags", [])
    orig_tag_set = set(orig_tags)
    edit_tag_set = set(edit_tags)
    added_tags = edit_tag_set - orig_tag_set
    removed_tags = orig_tag_set - edit_tag_set

    household_id = original.get("household_id")
    for tag_name in added_tags:
        try:
            if household_id:
                client.create_tag(household_id, tag_name)
            # Re-fetch recipe to get updated tag list? For now just report.
            print_success(f"Tag '{tag_name}' created/added (may need manual association).")
        except KowlAPIError as e:
            print_error(f"Could not add tag '{tag_name}': {e}")
    if removed_tags:
        print_warning(
            f"Tag removal via edit is not supported by the API. "
            f"Remove manually: {', '.join(removed_tags)}"
        )

    # ---- Items (ingredients) ----
    orig_items: List[Dict[str, Any]] = original.get("items", [])
    edit_items: List[Dict[str, Any]] = edited.get("items", [])

    # Build lookup by id (items coming from YAML may have id if preserved)
    orig_by_id = {item["id"]: item for item in orig_items if item.get("id")}
    orig_by_name = {item["name"].lower(): item for item in orig_items}
    edit_by_id = {item["id"]: item for item in edit_items if item.get("id")}
    edit_by_name = {item["name"].lower(): item for item in edit_items}

    orig_ids = set(orig_by_id.keys())
    edit_ids = set(edit_by_id.keys())

    # Items to remove: present in original but not in edited (by id)
    removed_ids = orig_ids - edit_ids
    # Also check by name for items without id
    for item in orig_items:
        if item.get("id") and item["id"] in removed_ids:
            continue
        if item["name"].lower() not in edit_by_name:
            removed_ids.add(item.get("id"))

    for item_id in removed_ids:
        if item_id is None:
            continue
        try:
            client.remove_recipe_item(recipe_id, item_id)
            name = orig_by_id.get(item_id, {}).get("name", str(item_id))
            print_success(f"Removed ingredient '{name}'")
        except KowlAPIError as e:
            print_error(f"Could not remove ingredient id={item_id}: {e}")

    # Items to add: present in edited but not in original (by name)
    for item in edit_items:
        iname = item.get("name", "").lower()
        if iname not in orig_by_name:
            try:
                client.add_recipe_item(
                    recipe_id,
                    item.get("name", ""),
                    item.get("description", ""),
                    bool(item.get("optional", False)),
                )
                print_success(f"Added ingredient '{item.get('name')}'")
            except KowlAPIError as e:
                print_error(f"Could not add ingredient '{item.get('name')}': {e}")
        else:
            # Check if description or optional changed
            orig_item = orig_by_name[iname]
            orig_desc = orig_item.get("description", "") or ""
            edit_desc = item.get("description", "") or ""
            orig_opt = bool(orig_item.get("optional", False))
            edit_opt = bool(item.get("optional", False))
            if orig_desc != edit_desc or orig_opt != edit_opt:
                # Remove old, add new
                item_id = orig_item.get("id")
                if item_id:
                    try:
                        client.remove_recipe_item(recipe_id, item_id)
                    except KowlAPIError as e:
                        print_error(f"Could not remove old ingredient '{item.get('name')}': {e}")
                        continue
                try:
                    client.add_recipe_item(
                        recipe_id,
                        item.get("name", ""),
                        edit_desc,
                        edit_opt,
                    )
                    print_success(f"Updated ingredient '{item.get('name')}'")
                except KowlAPIError as e:
                    print_error(f"Could not re-add ingredient '{item.get('name')}': {e}")


# ---------------------------------------------------------------------------
# Command group
# ---------------------------------------------------------------------------


@click.group("recipe")
def recipe_group() -> None:
    """Manage recipes."""


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@recipe_group.command("list")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.pass_context
def recipe_list(ctx: click.Context, household_id: Optional[int]) -> None:
    """List recipes in a household."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.list_recipes(hid)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_recipes, yaml_transform=yaml_recipes)


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@recipe_group.command("get")
@click.argument("recipe_id", type=int)
@click.pass_context
def recipe_get(ctx: click.Context, recipe_id: int) -> None:
    """Get recipe details including ingredients."""
    fmt = ctx.obj or {}
    try:
        data = client.get_recipe(recipe_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    yaml_data = _recipe_to_yaml_dict(data, include_ids=False) if fmt.get("yaml") else data
    output(yaml_data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_recipe_detail)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@recipe_group.command("search")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.argument("query")
@click.pass_context
def recipe_search(ctx: click.Context, household_id: Optional[int], query: str) -> None:
    """Search recipes by query string."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.search_recipes(hid, query)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_recipes, yaml_transform=yaml_recipes)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@recipe_group.command("create")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.option("--name", required=True, help="Recipe name")
@click.option("--description", default="", help="Recipe description")
@click.option("--cook-time", type=int, default=0, help="Cook time in minutes")
@click.option("--prep-time", type=int, default=0, help="Prep time in minutes")
@click.option("--time", "total_time", type=int, default=0, help="Total time in minutes")
@click.option("--yields", type=int, default=0, help="Number of servings")
@click.option("--source", default="", help="Recipe source URL or reference")
@click.pass_context
def recipe_create(
    ctx: click.Context,
    household_id: Optional[int],
    name: str,
    description: str,
    cook_time: int,
    prep_time: int,
    total_time: int,
    yields: int,
    source: str,
) -> None:
    """Create a new recipe."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    body: Dict[str, Any] = {
        "name": name,
        "description": description,
        "cook_time": cook_time,
        "prep_time": prep_time,
        "time": total_time,
        "yields": yields,
        "source": source,
    }
    try:
        data = client.create_recipe(hid, body)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    if fmt.get("json") or fmt.get("yaml"):
        output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"),
               yaml_transform=lambda d: _recipe_to_yaml_dict(d, include_ids=False))
    else:
        print_success(f"Created recipe '{data.get('name', name)}' (id={data.get('id', '?')})")


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@recipe_group.command("update")
@click.argument("recipe_id", type=int)
@click.option("--file", "-f", "yaml_file", type=click.Path(exists=True, dir_okay=False), default=None,
              help="YAML file to update from (sends full payload including items and tags)")
@click.option("--name", default=None, help="Recipe name")
@click.option("--description", default=None, help="Recipe description")
@click.option("--cook-time", type=int, default=None, help="Cook time in minutes")
@click.option("--prep-time", type=int, default=None, help="Prep time in minutes")
@click.option("--time", "total_time", type=int, default=None, help="Total time in minutes")
@click.option("--yields", type=int, default=None, help="Number of servings")
@click.option("--source", default=None, help="Recipe source URL or reference")
@click.option("--visibility", type=int, default=None, help="Visibility: 0=private, 1=household, 2=public")
@click.pass_context
def recipe_update(
    ctx: click.Context,
    recipe_id: int,
    yaml_file: Optional[str],
    name: Optional[str],
    description: Optional[str],
    cook_time: Optional[int],
    prep_time: Optional[int],
    total_time: Optional[int],
    yields: Optional[int],
    source: Optional[str],
    visibility: Optional[int],
) -> None:
    """Update recipe metadata, or replace entirely from a YAML file (--file)."""
    fmt = ctx.obj or {}

    if yaml_file:
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                yaml_dict = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print_error(f"YAML parse error: {e}")
            sys.exit(1)
        if not isinstance(yaml_dict, dict):
            print_error("YAML file must contain a mapping.")
            sys.exit(1)
        body = _yaml_dict_to_api_body(yaml_dict)
    else:
        body = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if cook_time is not None:
            body["cook_time"] = cook_time
        if prep_time is not None:
            body["prep_time"] = prep_time
        if total_time is not None:
            body["time"] = total_time
        if yields is not None:
            body["yields"] = yields
        if source is not None:
            body["source"] = source
        if visibility is not None:
            body["visibility"] = visibility

    if not body:
        print_warning("No fields to update.")
        return

    try:
        data = client.update_recipe(recipe_id, body)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)

    if fmt.get("json") or fmt.get("yaml"):
        output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"),
               yaml_transform=lambda d: _recipe_to_yaml_dict(d, include_ids=False))
    else:
        print_success(f"Updated recipe id={recipe_id}")


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@recipe_group.command("delete")
@click.argument("recipe_id", type=int)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def recipe_delete(ctx: click.Context, recipe_id: int, yes: bool) -> None:
    """Delete a recipe."""
    if not yes:
        click.confirm(f"Delete recipe id={recipe_id}?", abort=True)
    try:
        client.delete_recipe(recipe_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    print_success(f"Deleted recipe id={recipe_id}")


# ---------------------------------------------------------------------------
# add-item
# ---------------------------------------------------------------------------


@recipe_group.command("add-item")
@click.argument("recipe_id", type=int)
@click.option("--name", required=True, help="Ingredient name")
@click.option("--description", default="", help="Ingredient description / amount")
@click.option("--optional", is_flag=True, default=False, help="Mark as optional")
@click.pass_context
def recipe_add_item(
    ctx: click.Context,
    recipe_id: int,
    name: str,
    description: str,
    optional: bool,
) -> None:
    """Add an ingredient to a recipe."""
    fmt = ctx.obj or {}
    try:
        data = client.add_recipe_item(recipe_id, name, description, optional)
    except KowlAPIError as e:
        # Check for 404 — the add-item endpoint may not exist on this server version
        if e.status_code == 404:
            print_error(
                f"Server does not support individual item add endpoint.\n"
                f"Workaround: Use bulk-edit to manage items:\n"
                f"  kowl recipe bulk-edit-items {recipe_id}\n"
                f"\n"
                f"Or programmatically: fetch YAML, modify, apply:\n"
                f"  kowl recipe get {recipe_id} --yaml > /tmp/recipe.yaml\n"
                f"  # Edit /tmp/recipe.yaml to add/remove items\n"
                f"  EDITOR='cat /tmp/recipe.yaml' kowl recipe bulk-edit-items {recipe_id}"
            )
        else:
            print_error(str(e))
        sys.exit(1)
    if fmt.get("json") or fmt.get("yaml"):
        output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"),
               yaml_transform=lambda d: {"name": d.get("name", ""), "description": d.get("description", "") or "", "optional": bool(d.get("optional", False))})
    else:
        print_success(f"Added ingredient '{name}' to recipe id={recipe_id}")


# ---------------------------------------------------------------------------
# remove-item
# ---------------------------------------------------------------------------


@recipe_group.command("remove-item")
@click.argument("recipe_id", type=int)
@click.argument("item_id", type=int)
@click.pass_context
def recipe_remove_item(ctx: click.Context, recipe_id: int, item_id: int) -> None:
    """Remove an ingredient from a recipe."""
    try:
        client.remove_recipe_item(recipe_id, item_id)
    except KowlAPIError as e:
        # Check for 404 — the remove-item endpoint may not exist on this server version
        if e.status_code == 404:
            print_error(
                f"Server does not support individual item remove endpoint.\n"
                f"Workaround: Use bulk-edit to manage items:\n"
                f"  kowl recipe bulk-edit-items {recipe_id}\n"
                f"\n"
                f"Or programmatically: fetch YAML, modify, apply:\n"
                f"  kowl recipe get {recipe_id} --yaml > /tmp/recipe.yaml\n"
                f"  # Edit /tmp/recipe.yaml to add/remove items (delete the item entry to remove)\n"
                f"  EDITOR='cat /tmp/recipe.yaml' kowl recipe bulk-edit-items {recipe_id}"
            )
        else:
            print_error(str(e))
        sys.exit(1)
    print_success(f"Removed ingredient id={item_id} from recipe id={recipe_id}")


# ---------------------------------------------------------------------------
# add-tag
# ---------------------------------------------------------------------------


@recipe_group.command("add-tag")
@click.argument("recipe_id", type=int)
@click.argument("tag_name")
@click.pass_context
def recipe_add_tag(ctx: click.Context, recipe_id: int, tag_name: str) -> None:
    """Add a tag to a recipe (creates tag if it doesn't exist).

    NOTE: KitchenOwl's API does not have a dedicated endpoint to associate an
    existing tag with a recipe. The common approach is to update the recipe
    with the full tag list. This command uses the edit flow to apply the change.
    """
    try:
        recipe = client.get_recipe(recipe_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)

    existing_tags = [t.get("name", "") for t in recipe.get("tags", [])]
    if tag_name in existing_tags:
        print_warning(f"Tag '{tag_name}' already present.")
        return

    # Build updated recipe payload preserving all existing fields
    updated = dict(recipe)
    updated["tags"] = existing_tags + [tag_name]

    try:
        # The update endpoint accepts tag names as strings in some KitchenOwl versions
        client.update_recipe(recipe_id, {"tags": updated["tags"]})
        print_success(f"Added tag '{tag_name}' to recipe id={recipe_id}")
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# remove-tag
# ---------------------------------------------------------------------------


@recipe_group.command("remove-tag")
@click.argument("recipe_id", type=int)
@click.argument("tag_name")
@click.pass_context
def recipe_remove_tag(ctx: click.Context, recipe_id: int, tag_name: str) -> None:
    """Remove a tag from a recipe."""
    try:
        recipe = client.get_recipe(recipe_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)

    existing_tags = [t.get("name", "") for t in recipe.get("tags", [])]
    if tag_name not in existing_tags:
        print_warning(f"Tag '{tag_name}' not found on recipe id={recipe_id}.")
        return

    updated_tags = [t for t in existing_tags if t != tag_name]
    try:
        client.update_recipe(recipe_id, {"tags": updated_tags})
        print_success(f"Removed tag '{tag_name}' from recipe id={recipe_id}")
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# edit  (interactive YAML editor)
# ---------------------------------------------------------------------------


@recipe_group.command("edit")
@click.argument("recipe_id", type=int)
@click.pass_context
def recipe_edit(ctx: click.Context, recipe_id: int) -> None:
    """Open a recipe in $EDITOR as YAML and apply changes on save.

    Fields available for editing: name, description, cook_time, prep_time,
    time, yields, source, visibility, tags, items (ingredients).
    """
    try:
        recipe = client.get_recipe(recipe_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)

    original_yaml_dict = _recipe_to_yaml_dict(recipe)
    # Preserve household_id for potential tag creation
    original_yaml_dict["household_id"] = recipe.get("household_id")

    header = (
        "# Edit recipe fields below. Save and close the editor to apply changes.\n"
        "# Lines starting with '#' are ignored.\n"
        "# Visibility: 0=private, 1=household, 2=public\n"
        "# To remove an ingredient, delete its entry. To add, append a new entry.\n\n"
    )

    content = header + yaml.dump(
        {k: v for k, v in original_yaml_dict.items() if k != "household_id"},
        allow_unicode=True,
        default_flow_style=False,
    )

    edited_content = _open_editor(content)

    try:
        edited_dict = yaml.safe_load(edited_content)
    except yaml.YAMLError as e:
        print_error(f"YAML parse error: {e}")
        sys.exit(1)

    if edited_dict is None:
        print_warning("Empty file — no changes applied.")
        return

    # Inject household_id back for tag logic
    edited_dict["household_id"] = recipe.get("household_id")

    _apply_recipe_edits(recipe_id, original_yaml_dict, edited_dict)
    console.print("[bold green]Done.[/bold green]")


# ---------------------------------------------------------------------------
# bulk-edit-items
# ---------------------------------------------------------------------------


@recipe_group.command("bulk-edit-items")
@click.argument("recipe_id", type=int)
@click.pass_context
def recipe_bulk_edit_items(ctx: click.Context, recipe_id: int) -> None:
    """Edit only the ingredients of a recipe in $EDITOR as YAML."""
    try:
        recipe = client.get_recipe(recipe_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)

    original_yaml_dict = _recipe_to_yaml_dict(recipe)
    items_only = {"items": original_yaml_dict["items"]}

    header = (
        "# Edit ingredients below. Save and close to apply.\n"
        "# Each item must have at least a 'name' field.\n"
        "# To remove an ingredient, delete its entry.\n"
        "# To add one, append a new entry with name/description/optional.\n\n"
    )
    content = header + yaml.dump(items_only, allow_unicode=True, default_flow_style=False)

    edited_content = _open_editor(content)

    try:
        edited_dict = yaml.safe_load(edited_content)
    except yaml.YAMLError as e:
        print_error(f"YAML parse error: {e}")
        sys.exit(1)

    if edited_dict is None:
        print_warning("Empty file — no changes applied.")
        return

    # Merge back to full dict for diff function
    merged_original = dict(original_yaml_dict)
    merged_edited = dict(original_yaml_dict)
    merged_edited["items"] = edited_dict.get("items", [])

    _apply_recipe_edits(recipe_id, merged_original, merged_edited)
    console.print("[bold green]Done.[/bold green]")


# ---------------------------------------------------------------------------
# scrape
# ---------------------------------------------------------------------------


@recipe_group.command("scrape")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.argument("url")
@click.pass_context
def recipe_scrape(ctx: click.Context, household_id: Optional[int], url: str) -> None:
    """Scrape a recipe from a URL and add it to the household."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.scrape_recipe(hid, url)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    yaml_data = _recipe_to_yaml_dict(data, include_ids=False) if fmt.get("yaml") else data
    output(yaml_data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_recipe_detail)


# ---------------------------------------------------------------------------
# import  (YAML file → new recipe)
# ---------------------------------------------------------------------------


@recipe_group.command("import")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.argument("yaml_file", metavar="FILE", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def recipe_import(ctx: click.Context, household_id: Optional[int], yaml_file: str) -> None:
    """Create a new recipe from a YAML file (includes items and tags)."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)

    try:
        with open(yaml_file, "r", encoding="utf-8") as f:
            yaml_dict = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print_error(f"YAML parse error: {e}")
        sys.exit(1)

    if not isinstance(yaml_dict, dict):
        print_error("YAML file must contain a mapping.")
        sys.exit(1)

    if not yaml_dict.get("name"):
        print_error("YAML file must have a 'name' field.")
        sys.exit(1)

    # Create the bare recipe first to get an ID
    meta: Dict[str, Any] = {
        "name": yaml_dict["name"],
        "description": yaml_dict.get("description", "") or "",
    }
    try:
        created = client.create_recipe(hid, meta)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)

    recipe_id = created.get("id")
    if not recipe_id:
        print_error("Server did not return a recipe ID after creation.")
        sys.exit(1)

    # Push the full payload (metadata + items + tags) in one shot
    body = _yaml_dict_to_api_body(yaml_dict)
    try:
        data = client.update_recipe(recipe_id, body)
    except KowlAPIError as e:
        print_error(f"Recipe created (id={recipe_id}) but full update failed: {e}")
        sys.exit(1)

    if fmt.get("json") or fmt.get("yaml"):
        yaml_data = _recipe_to_yaml_dict(data, include_ids=False) if fmt.get("yaml") else data
        output(yaml_data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_recipe_detail)
    else:
        print_success(f"Imported '{data.get('name', yaml_dict['name'])}' as recipe id={recipe_id}")
