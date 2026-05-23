"""Tag commands for kowl.

Implements the `kowl tag` command group.
"""

from __future__ import annotations

import sys
from typing import Optional

import click

from ..api import KowlAPIError, client
from ..config import resolve_household_id
from ..output import output, print_error, print_success, render_tags, yaml_tags


@click.group("tag")
def tag_group() -> None:
    """Manage recipe tags."""


@tag_group.command("list")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.pass_context
def tag_list(ctx: click.Context, household_id: Optional[int]) -> None:
    """List tags for a household."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.list_tags(hid)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_tags, yaml_transform=yaml_tags)


@tag_group.command("create")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.option("--name", required=True, help="Tag name")
@click.pass_context
def tag_create(ctx: click.Context, household_id: Optional[int], name: str) -> None:
    """Create a new tag."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.create_tag(hid, name)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    if fmt.get("json") or fmt.get("yaml"):
        output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), yaml_transform=yaml_tags)
    else:
        print_success(f"Created tag '{name}' (id={data.get('id', '?')})")
