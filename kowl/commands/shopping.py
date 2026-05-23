"""Shopping list commands for kowl.

Implements the `kowl shop` command group.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional

import click

from ..api import KowlAPIError, client
from ..config import resolve_household_id
from ..output import (
    output,
    print_error,
    print_success,
    render_shopping_items,
    render_shopping_lists,
    yaml_shopping_items,
    yaml_shopping_lists,
)


@click.group("shop")
def shop_group() -> None:
    """Manage shopping lists."""


@shop_group.command("list")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.pass_context
def shop_list(ctx: click.Context, household_id: Optional[int]) -> None:
    """List shopping lists in a household."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.list_shopping_lists(hid)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_shopping_lists, yaml_transform=yaml_shopping_lists)


@shop_group.command("items")
@click.argument("list_id", type=int)
@click.pass_context
def shop_items(ctx: click.Context, list_id: int) -> None:
    """List items in a shopping list."""
    fmt = ctx.obj or {}
    try:
        data = client.list_shopping_items(list_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_shopping_items, yaml_transform=yaml_shopping_items)


@shop_group.command("add")
@click.argument("list_id", type=int)
@click.option("--name", required=True, help="Item name")
@click.option("--description", default="", help="Item description or quantity")
@click.pass_context
def shop_add(ctx: click.Context, list_id: int, name: str, description: str) -> None:
    """Add an item to a shopping list."""
    fmt = ctx.obj or {}
    try:
        data = client.add_shopping_item(list_id, name, description)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    if fmt.get("json") or fmt.get("yaml"):
        output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), yaml_transform=yaml_shopping_items)
    else:
        print_success(f"Added '{name}' to shopping list id={list_id}")


@shop_group.command("remove")
@click.argument("list_id", type=int)
@click.argument("item_id", type=int)
@click.pass_context
def shop_remove(ctx: click.Context, list_id: int, item_id: int) -> None:
    """Remove an item from a shopping list."""
    try:
        client.remove_shopping_item(list_id, item_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    print_success(f"Removed item id={item_id} from shopping list id={list_id}")


@shop_group.command("create")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.option("--name", required=True, help="Shopping list name")
@click.pass_context
def shop_create(ctx: click.Context, household_id: Optional[int], name: str) -> None:
    """Create a new shopping list."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.create_shopping_list(hid, name)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    if fmt.get("json") or fmt.get("yaml"):
        output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), yaml_transform=yaml_shopping_lists)
    else:
        print_success(f"Created shopping list '{name}' (id={data.get('id', '?')})")


@shop_group.command("delete")
@click.argument("list_id", type=int)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def shop_delete(ctx: click.Context, list_id: int, yes: bool) -> None:
    """Delete a shopping list."""
    if not yes:
        click.confirm(f"Delete shopping list id={list_id}?", abort=True)
    try:
        client.delete_shopping_list(list_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    print_success(f"Deleted shopping list id={list_id}")
