"""Main CLI entry point for kowl.

Defines the root `cli` group with global flags and registers all
sub-command groups.
"""

from __future__ import annotations

import sys
from typing import Optional

import click

from .api import KowlAPIError, client
from .commands.expense import expense_group
from .commands.planner import plan_group
from .commands.recipe import recipe_group
from .commands.shopping import shop_group
from .commands.tag import tag_group
from .output import output, print_error, render_households, yaml_households


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="kowl")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON")
@click.option("--yaml", "output_yaml", is_flag=True, default=False, help="Output as YAML")
@click.option(
    "--household-id",
    type=int,
    envvar="KOWL_HOUSEHOLD_ID",
    default=None,
    help="Default household ID (also read from KOWL_HOUSEHOLD_ID env var)",
)
@click.pass_context
def cli(
    ctx: click.Context,
    output_json: bool,
    output_yaml: bool,
    household_id: Optional[int],
) -> None:
    """kowl — KitchenOwl command-line interface.

    Manage recipes, shopping lists, meal plans, expenses, and tags.

    Configuration is read from environment variables or
    ~/.config/kowl/config.toml.

    \b
    Environment variables:
      KITCHENOWL_URL      API base URL (default: https://kitchenowl.example.com/api)
      KITCHENOWL_API_KEY  Bearer token for authentication
      KOWL_HOUSEHOLD_ID   Default household ID
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = output_json
    ctx.obj["yaml"] = output_yaml
    if household_id is not None:
        ctx.obj["household_id"] = household_id


# ---------------------------------------------------------------------------
# household sub-group (simple enough to live here)
# ---------------------------------------------------------------------------


@cli.group("household")
def household_group() -> None:
    """Manage households."""


@household_group.command("list")
@click.pass_context
def household_list(ctx: click.Context) -> None:
    """List all households you belong to."""
    fmt = ctx.obj or {}
    try:
        data = client.list_households()
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    output(
        data,
        as_json=fmt.get("json"),
        as_yaml=fmt.get("yaml"),
        render_fn=render_households,
        yaml_transform=yaml_households,
    )


# ---------------------------------------------------------------------------
# Register sub-groups
# ---------------------------------------------------------------------------

cli.add_command(recipe_group)
cli.add_command(shop_group)
cli.add_command(plan_group)
cli.add_command(expense_group)
cli.add_command(tag_group)
