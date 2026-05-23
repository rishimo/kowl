"""Meal planner commands for kowl.

Implements the `kowl plan` command group.
"""

from __future__ import annotations

import sys
from typing import Optional

import click

from ..api import KowlAPIError, client
from ..config import resolve_household_id
from ..output import output, print_error, print_success, render_planner, yaml_planner


@click.group("plan")
def plan_group() -> None:
    """Manage the meal planner."""


@plan_group.command("list")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.pass_context
def plan_list(ctx: click.Context, household_id: Optional[int]) -> None:
    """List all planner entries for a household."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.list_planner(hid)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_planner, yaml_transform=yaml_planner)


@plan_group.command("add")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.option("--recipe-id", type=int, required=True, help="Recipe ID to add")
@click.option("--day", required=True, help="Day name (e.g. Monday, Tuesday)")
@click.pass_context
def plan_add(ctx: click.Context, household_id: Optional[int], recipe_id: int, day: str) -> None:
    """Add a recipe to the meal planner for a specific day."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.add_planner_entry(hid, recipe_id, day)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    if fmt.get("json") or fmt.get("yaml"):
        output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), yaml_transform=yaml_planner)
    else:
        print_success(f"Added recipe id={recipe_id} to planner on {day}")


@plan_group.command("remove")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.option("--recipe-id", type=int, required=True, help="Recipe ID to remove")
@click.option("--day", required=True, help="Day name (e.g. Monday, Tuesday)")
@click.pass_context
def plan_remove(ctx: click.Context, household_id: Optional[int], recipe_id: int, day: str) -> None:
    """Remove a recipe from the meal planner."""
    hid = resolve_household_id(ctx, household_id)
    try:
        client.remove_planner_entry(hid, recipe_id, day)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    print_success(f"Removed recipe id={recipe_id} from planner on {day}")
