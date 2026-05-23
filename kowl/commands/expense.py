"""Expense commands for kowl.

Implements the `kowl expense` command group.
"""

from __future__ import annotations

import sys
from typing import Optional

import click

from ..api import KowlAPIError, client
from ..config import resolve_household_id
from ..output import output, print_error, print_success, render_expenses, yaml_expenses


@click.group("expense")
def expense_group() -> None:
    """Manage household expenses."""


@expense_group.command("list")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.pass_context
def expense_list(ctx: click.Context, household_id: Optional[int]) -> None:
    """List expenses for a household."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.list_expenses(hid)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), render_fn=render_expenses, yaml_transform=yaml_expenses)


@expense_group.command("create")
@click.option("--household-id", type=int, envvar="KOWL_HOUSEHOLD_ID", default=None, help="Household ID")
@click.option("--name", required=True, help="Expense name/description")
@click.option("--amount", type=float, required=True, help="Amount spent")
@click.option("--paid-by", default=None, help="Who paid (username or display name)")
@click.pass_context
def expense_create(
    ctx: click.Context,
    household_id: Optional[int],
    name: str,
    amount: float,
    paid_by: Optional[str],
) -> None:
    """Create a new expense."""
    fmt = ctx.obj or {}
    hid = resolve_household_id(ctx, household_id)
    try:
        data = client.create_expense(hid, name, amount, paid_by)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    if fmt.get("json") or fmt.get("yaml"):
        output(data, as_json=fmt.get("json"), as_yaml=fmt.get("yaml"), yaml_transform=yaml_expenses)
    else:
        print_success(
            f"Created expense '{name}' for {amount:.2f} (id={data.get('id', '?')})"
        )


@expense_group.command("delete")
@click.argument("expense_id", type=int)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def expense_delete(ctx: click.Context, expense_id: int, yes: bool) -> None:
    """Delete an expense."""
    if not yes:
        click.confirm(f"Delete expense id={expense_id}?", abort=True)
    try:
        client.delete_expense(expense_id)
    except KowlAPIError as e:
        print_error(str(e))
        sys.exit(1)
    print_success(f"Deleted expense id={expense_id}")
