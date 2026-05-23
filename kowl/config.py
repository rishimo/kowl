"""Configuration management for kowl.

Loads settings from:
1. Environment variables (highest priority)
2. Config file at ~/.config/kowl/config.toml
3. Built-in defaults (lowest priority)
"""

import os
import sys
from pathlib import Path
from typing import Optional

import click

# Default API base URL
DEFAULT_URL = "https://kitchenowl.example.com/api"
CONFIG_PATH = Path.home() / ".config" / "kowl" / "config.toml"


def _load_toml(path: Path) -> dict:
    """Load a TOML file, returning empty dict if not found or unreadable."""
    if not path.exists():
        return {}
    try:
        if sys.version_info >= (3, 11):
            import tomllib
            with open(path, "rb") as f:
                return tomllib.load(f)
        else:
            import tomli  # type: ignore[import]
            with open(path, "rb") as f:
                return tomli.load(f)
    except Exception:
        return {}


class Config:
    """Holds runtime configuration for kowl."""

    def __init__(self) -> None:
        file_data = _load_toml(CONFIG_PATH)
        api_section = file_data.get("api", {})

        # URL: env var > config file > default
        self.url: str = (
            os.environ.get("KITCHENOWL_URL")
            or api_section.get("url")
            or DEFAULT_URL
        ).rstrip("/")

        # API key: env var > config file
        self.api_key: Optional[str] = (
            os.environ.get("KITCHENOWL_API_KEY")
            or api_section.get("key")
            or None
        )

        # Household ID: env var > config file
        self.household_id: Optional[int] = None
        raw_hid = os.environ.get("KOWL_HOUSEHOLD_ID") or api_section.get("household_id")
        if raw_hid:
            try:
                self.household_id = int(raw_hid)
            except ValueError:
                pass


# Module-level singleton, created on first import
config = Config()


def resolve_household_id(ctx: click.Context, household_id: Optional[int]) -> int:
    """Resolve household_id from global flag, config, or option. Raise error if not found."""
    hid = household_id or (ctx.obj.get("household_id") if ctx.obj else None) or config.household_id
    if hid is None:
        raise click.UsageError("--household-id is required (set via flag, config, or env var)")
    return hid
