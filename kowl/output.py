"""Output helpers for kowl.

Provides functions to render data as rich tables/panels, raw JSON,
or YAML, depending on the global output flags.
"""

from __future__ import annotations

import json
import sys
from typing import Any, List, Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# Shared console instances
console = Console()
err_console = Console(stderr=True, style="bold red")


# ---------------------------------------------------------------------------
# Low-level format helpers
# ---------------------------------------------------------------------------


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    console.print_json(json.dumps(data))


def print_yaml(data: Any) -> None:
    """Print data as YAML to stdout."""
    console.print(yaml.dump(data, allow_unicode=True, default_flow_style=False), end="")


def print_error(message: str) -> None:
    """Print an error message in red to stderr."""
    err_console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print a success message in green."""
    console.print(f"[bold green]{message}[/bold green]")


def print_warning(message: str) -> None:
    """Print a warning message in yellow."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


# ---------------------------------------------------------------------------
# Output mode dispatcher
# ---------------------------------------------------------------------------


def output(
    data: Any,
    *,
    as_json: bool = False,
    as_yaml: bool = False,
    render_fn: Any = None,
    yaml_transform: Any = None,
) -> None:
    """Output data in the requested format.

    If neither as_json nor as_yaml is set, calls render_fn(data) for
    human-readable output.  render_fn defaults to a simple print if omitted.
    yaml_transform, if provided, is called on data before YAML serialization.
    """
    if as_json:
        print_json(data)
    elif as_yaml:
        print_yaml(yaml_transform(data) if yaml_transform else data)
    else:
        if render_fn is not None:
            render_fn(data)
        else:
            console.print(data)


# ---------------------------------------------------------------------------
# Domain-specific rich renderers
# ---------------------------------------------------------------------------


def render_households(households: List[dict]) -> None:
    if not households:
        console.print("[italic]No households found.[/italic]")
        return
    table = Table(title="Households", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    for h in households:
        table.add_row(str(h.get("id", "")), h.get("name", ""))
    console.print(table)


def render_recipes(recipes: List[dict]) -> None:
    if not recipes:
        console.print("[italic]No recipes found.[/italic]")
        return
    table = Table(title="Recipes", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Tags")
    for r in recipes:
        tags = ", ".join(t.get("name", "") for t in r.get("tags", []))
        table.add_row(str(r.get("id", "")), r.get("name", ""), tags)
    console.print(table)


def render_recipe_detail(recipe: dict) -> None:
    """Render a single recipe with ingredients."""
    name = recipe.get("name", "Unknown")
    lines: List[str] = []

    fields = [
        ("Description", recipe.get("description", "")),
        ("Source", recipe.get("source", "")),
        ("Cook time", recipe.get("cook_time", 0)),
        ("Prep time", recipe.get("prep_time", 0)),
        ("Total time", recipe.get("time", 0)),
        ("Yields", recipe.get("yields", 0)),
        ("Visibility", recipe.get("visibility", 0)),
    ]
    for label, value in fields:
        if value:
            lines.append(f"[bold]{label}:[/bold] {value}")

    tags = ", ".join(t.get("name", "") for t in recipe.get("tags", []))
    if tags:
        lines.append(f"[bold]Tags:[/bold] {tags}")

    items = recipe.get("items", [])
    if items:
        lines.append("\n[bold underline]Ingredients:[/bold underline]")
        for item in items:
            optional_marker = " [italic](optional)[/italic]" if item.get("optional") else ""
            desc = item.get("description", "")
            desc_str = f" — {desc}" if desc else ""
            lines.append(
                f"  [cyan]{item.get('id', '?')}[/cyan]  {item.get('name', '')}{desc_str}{optional_marker}"
            )

    body = "\n".join(lines)
    console.print(Panel(body, title=f"[bold]{name}[/bold]", expand=False))


def render_shopping_lists(lists: List[dict]) -> None:
    if not lists:
        console.print("[italic]No shopping lists found.[/italic]")
        return
    table = Table(title="Shopping Lists", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    for sl in lists:
        table.add_row(str(sl.get("id", "")), sl.get("name", ""))
    console.print(table)


def render_shopping_items(items: List[dict]) -> None:
    if not items:
        console.print("[italic]No items in shopping list.[/italic]")
        return
    table = Table(title="Shopping Items", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Description")
    for item in items:
        table.add_row(
            str(item.get("id", "")),
            item.get("name", ""),
            item.get("description", ""),
        )
    console.print(table)


def render_planner(entries: List[dict]) -> None:
    if not entries:
        console.print("[italic]Planner is empty.[/italic]")
        return
    table = Table(title="Meal Planner", box=box.ROUNDED)
    table.add_column("Day", style="cyan", no_wrap=True)
    table.add_column("Recipe ID", style="bold")
    table.add_column("Recipe Name")
    for entry in entries:
        recipe = entry.get("recipe", {}) or {}
        table.add_row(
            str(entry.get("day", "")),
            str(recipe.get("id", entry.get("recipe_id", ""))),
            recipe.get("name", ""),
        )
    console.print(table)


def render_expenses(expenses: List[dict]) -> None:
    if not expenses:
        console.print("[italic]No expenses found.[/italic]")
        return
    table = Table(title="Expenses", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Amount", justify="right")
    table.add_column("Paid by")
    for e in expenses:
        amount = e.get("amount", 0)
        table.add_row(
            str(e.get("id", "")),
            e.get("name", ""),
            f"{amount:.2f}",
            e.get("paid_by", ""),
        )
    console.print(table)


def render_tags(tags: List[dict]) -> None:
    if not tags:
        console.print("[italic]No tags found.[/italic]")
        return
    table = Table(title="Tags", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    for t in tags:
        table.add_row(str(t.get("id", "")), t.get("name", ""))
    console.print(table)


# ---------------------------------------------------------------------------
# YAML clean serializers (strip internal IDs and server-only fields)
# ---------------------------------------------------------------------------


def yaml_recipes(data: Any) -> Any:
    def _r(r: dict) -> dict:
        d: dict = {"name": r.get("name", "")}
        tags = [t.get("name", "") for t in r.get("tags", [])]
        if tags:
            d["tags"] = tags
        return d

    if isinstance(data, list):
        return [_r(r) for r in data]
    return _r(data)


def yaml_households(data: Any) -> Any:
    if isinstance(data, list):
        return [{"name": h.get("name", "")} for h in data]
    return {"name": data.get("name", "")}


def yaml_shopping_lists(data: Any) -> Any:
    if isinstance(data, list):
        return [{"name": sl.get("name", "")} for sl in data]
    return {"name": data.get("name", "")}


def yaml_shopping_items(data: Any) -> Any:
    def _item(i: dict) -> dict:
        d: dict = {"name": i.get("name", "")}
        if i.get("description"):
            d["description"] = i["description"]
        return d

    if isinstance(data, list):
        return [_item(i) for i in data]
    return _item(data)


def yaml_planner(data: Any) -> Any:
    def _entry(e: dict) -> dict:
        recipe = e.get("recipe") or {}
        return {
            "day": e.get("day", ""),
            "recipe": recipe.get("name", "") or str(e.get("recipe_id", "")),
        }

    if isinstance(data, list):
        return [_entry(e) for e in data]
    return _entry(data)


def yaml_expenses(data: Any) -> Any:
    def _expense(e: dict) -> dict:
        d: dict = {"name": e.get("name", ""), "amount": e.get("amount", 0)}
        if e.get("paid_by"):
            d["paid_by"] = e["paid_by"]
        return d

    if isinstance(data, list):
        return [_expense(e) for e in data]
    return _expense(data)


def yaml_tags(data: Any) -> Any:
    if isinstance(data, list):
        return [t.get("name", "") for t in data]
    return data.get("name", "")
