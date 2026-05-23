"""Tests for CLI commands (kowl.commands.*).

Uses click.testing.CliRunner to invoke commands without a real server.
All API calls are patched at the client level.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from kowl.api import KowlAPIError
from kowl.cli import cli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Household commands
# ---------------------------------------------------------------------------


class TestHouseholdCommands:
    def test_household_list(self, runner: CliRunner) -> None:
        households = [{"id": 1, "name": "Home"}]
        with patch("kowl.commands.recipe.client") as mock_c, \
             patch("kowl.cli.client") as mock_cli_c:
            mock_cli_c.list_households.return_value = households
            result = runner.invoke(cli, ["household", "list"])
        assert result.exit_code == 0

    def test_household_list_json(self, runner: CliRunner) -> None:
        households = [{"id": 1, "name": "Home"}]
        with patch("kowl.cli.client") as mock_c:
            mock_c.list_households.return_value = households
            result = runner.invoke(cli, ["--json", "household", "list"])
        assert result.exit_code == 0
        assert '"id": 1' in result.output

    def test_household_list_api_error(self, runner: CliRunner) -> None:
        with patch("kowl.cli.client") as mock_c:
            mock_c.list_households.side_effect = KowlAPIError("Cannot connect to ...")
            result = runner.invoke(cli, ["household", "list"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Recipe commands
# ---------------------------------------------------------------------------


class TestRecipeCommands:
    def test_recipe_list(self, runner: CliRunner) -> None:
        recipes = [{"id": 1, "name": "Pasta", "tags": []}]
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.list_recipes.return_value = recipes
            result = runner.invoke(cli, ["recipe", "list", "--household-id", "1"])
        assert result.exit_code == 0
        mock_c.list_recipes.assert_called_once_with(1)

    def test_recipe_list_json(self, runner: CliRunner) -> None:
        recipes = [{"id": 1, "name": "Pasta", "tags": []}]
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.list_recipes.return_value = recipes
            result = runner.invoke(cli, ["--json", "recipe", "list", "--household-id", "1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["name"] == "Pasta"

    def test_recipe_list_error(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.list_recipes.side_effect = KowlAPIError("Not found: /household/99/recipe", 404)
            result = runner.invoke(cli, ["recipe", "list", "--household-id", "99"])
        assert result.exit_code == 1

    def test_recipe_get(self, runner: CliRunner) -> None:
        recipe = {
            "id": 5,
            "name": "Risotto",
            "description": "Creamy",
            "items": [{"id": 1, "name": "rice", "description": "300g", "optional": False}],
            "tags": [],
        }
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.get_recipe.return_value = recipe
            result = runner.invoke(cli, ["recipe", "get", "5"])
        assert result.exit_code == 0
        mock_c.get_recipe.assert_called_once_with(5)

    def test_recipe_search(self, runner: CliRunner) -> None:
        results = [{"id": 2, "name": "Soup", "tags": []}]
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.search_recipes.return_value = results
            result = runner.invoke(cli, ["recipe", "search", "--household-id", "1", "soup"])
        assert result.exit_code == 0
        mock_c.search_recipes.assert_called_once_with(1, "soup")

    def test_recipe_create(self, runner: CliRunner) -> None:
        created = {"id": 10, "name": "Tacos"}
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.create_recipe.return_value = created
            result = runner.invoke(
                cli,
                [
                    "recipe", "create",
                    "--household-id", "1",
                    "--name", "Tacos",
                    "--description", "Easy street tacos",
                ],
            )
        assert result.exit_code == 0
        assert "Tacos" in result.output
        call_body = mock_c.create_recipe.call_args[0][1]
        assert call_body["name"] == "Tacos"

    def test_recipe_create_error(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.create_recipe.side_effect = KowlAPIError("Authentication failed.", 401)
            result = runner.invoke(
                cli,
                ["recipe", "create", "--household-id", "1", "--name", "Tacos"],
            )
        assert result.exit_code == 1

    def test_recipe_update(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.update_recipe.return_value = {"id": 5, "name": "New Name"}
            result = runner.invoke(cli, ["recipe", "update", "5", "--name", "New Name"])
        assert result.exit_code == 0
        mock_c.update_recipe.assert_called_once_with(5, {"name": "New Name"})

    def test_recipe_update_no_fields(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            result = runner.invoke(cli, ["recipe", "update", "5"])
        assert result.exit_code == 0
        assert "No fields" in result.output
        mock_c.update_recipe.assert_not_called()

    def test_recipe_delete_with_yes(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.delete_recipe.return_value = {}
            result = runner.invoke(cli, ["recipe", "delete", "--yes", "5"])
        assert result.exit_code == 0
        mock_c.delete_recipe.assert_called_once_with(5)

    def test_recipe_delete_abort(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            result = runner.invoke(cli, ["recipe", "delete", "5"], input="n\n")
        assert result.exit_code != 0
        mock_c.delete_recipe.assert_not_called()

    def test_recipe_add_item(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.add_recipe_item.return_value = {"id": 20, "name": "garlic"}
            result = runner.invoke(
                cli,
                ["recipe", "add-item", "5", "--name", "garlic", "--description", "2 cloves"],
            )
        assert result.exit_code == 0
        mock_c.add_recipe_item.assert_called_once_with(5, "garlic", "2 cloves", False)

    def test_recipe_add_item_optional(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.add_recipe_item.return_value = {"id": 21, "name": "chili"}
            result = runner.invoke(
                cli,
                ["recipe", "add-item", "5", "--name", "chili", "--optional"],
            )
        assert result.exit_code == 0
        mock_c.add_recipe_item.assert_called_once_with(5, "chili", "", True)

    def test_recipe_remove_item(self, runner: CliRunner) -> None:
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.remove_recipe_item.return_value = {}
            result = runner.invoke(cli, ["recipe", "remove-item", "5", "20"])
        assert result.exit_code == 0
        mock_c.remove_recipe_item.assert_called_once_with(5, 20)

    def test_recipe_scrape(self, runner: CliRunner) -> None:
        scraped = {"id": 99, "name": "Scraped Recipe", "items": [], "tags": []}
        with patch("kowl.commands.recipe.client") as mock_c:
            mock_c.scrape_recipe.return_value = scraped
            result = runner.invoke(
                cli,
                ["recipe", "scrape", "--household-id", "1", "https://example.com/recipe"],
            )
        assert result.exit_code == 0
        mock_c.scrape_recipe.assert_called_once_with(1, "https://example.com/recipe")


# ---------------------------------------------------------------------------
# Shopping commands
# ---------------------------------------------------------------------------


class TestShoppingCommands:
    def test_shop_list(self, runner: CliRunner) -> None:
        lists = [{"id": 1, "name": "Weekly"}]
        with patch("kowl.commands.shopping.client") as mock_c:
            mock_c.list_shopping_lists.return_value = lists
            result = runner.invoke(cli, ["shop", "list", "--household-id", "1"])
        assert result.exit_code == 0
        mock_c.list_shopping_lists.assert_called_once_with(1)

    def test_shop_items(self, runner: CliRunner) -> None:
        items = [{"id": 1, "name": "Milk"}, {"id": 2, "name": "Eggs"}]
        with patch("kowl.commands.shopping.client") as mock_c:
            mock_c.list_shopping_items.return_value = items
            result = runner.invoke(cli, ["shop", "items", "1"])
        assert result.exit_code == 0
        mock_c.list_shopping_items.assert_called_once_with(1)

    def test_shop_add(self, runner: CliRunner) -> None:
        with patch("kowl.commands.shopping.client") as mock_c:
            mock_c.add_shopping_item.return_value = {"id": 5, "name": "Butter"}
            result = runner.invoke(cli, ["shop", "add", "1", "--name", "Butter"])
        assert result.exit_code == 0
        mock_c.add_shopping_item.assert_called_once_with(1, "Butter", "")

    def test_shop_remove(self, runner: CliRunner) -> None:
        with patch("kowl.commands.shopping.client") as mock_c:
            mock_c.remove_shopping_item.return_value = {}
            result = runner.invoke(cli, ["shop", "remove", "1", "5"])
        assert result.exit_code == 0
        mock_c.remove_shopping_item.assert_called_once_with(1, 5)

    def test_shop_create(self, runner: CliRunner) -> None:
        with patch("kowl.commands.shopping.client") as mock_c:
            mock_c.create_shopping_list.return_value = {"id": 3, "name": "Party"}
            result = runner.invoke(
                cli, ["shop", "create", "--household-id", "1", "--name", "Party"]
            )
        assert result.exit_code == 0
        mock_c.create_shopping_list.assert_called_once_with(1, "Party")

    def test_shop_delete_with_yes(self, runner: CliRunner) -> None:
        with patch("kowl.commands.shopping.client") as mock_c:
            mock_c.delete_shopping_list.return_value = {}
            result = runner.invoke(cli, ["shop", "delete", "--yes", "1"])
        assert result.exit_code == 0
        mock_c.delete_shopping_list.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# Planner commands
# ---------------------------------------------------------------------------


class TestPlannerCommands:
    def test_plan_list(self, runner: CliRunner) -> None:
        entries = [{"day": "Monday", "recipe": {"id": 1, "name": "Pasta"}}]
        with patch("kowl.commands.planner.client") as mock_c:
            mock_c.list_planner.return_value = entries
            result = runner.invoke(cli, ["plan", "list", "--household-id", "1"])
        assert result.exit_code == 0
        mock_c.list_planner.assert_called_once_with(1)

    def test_plan_add(self, runner: CliRunner) -> None:
        with patch("kowl.commands.planner.client") as mock_c:
            mock_c.add_planner_entry.return_value = {"id": 1, "day": "Tuesday"}
            result = runner.invoke(
                cli,
                [
                    "plan", "add",
                    "--household-id", "1",
                    "--recipe-id", "5",
                    "--day", "Tuesday",
                ],
            )
        assert result.exit_code == 0
        mock_c.add_planner_entry.assert_called_once_with(1, 5, "Tuesday")

    def test_plan_remove(self, runner: CliRunner) -> None:
        with patch("kowl.commands.planner.client") as mock_c:
            mock_c.remove_planner_entry.return_value = {}
            result = runner.invoke(
                cli,
                [
                    "plan", "remove",
                    "--household-id", "1",
                    "--recipe-id", "5",
                    "--day", "Tuesday",
                ],
            )
        assert result.exit_code == 0
        mock_c.remove_planner_entry.assert_called_once_with(1, 5, "Tuesday")


# ---------------------------------------------------------------------------
# Expense commands
# ---------------------------------------------------------------------------


class TestExpenseCommands:
    def test_expense_list(self, runner: CliRunner) -> None:
        expenses = [{"id": 1, "name": "Groceries", "amount": 45.5, "paid_by": "alice"}]
        with patch("kowl.commands.expense.client") as mock_c:
            mock_c.list_expenses.return_value = expenses
            result = runner.invoke(cli, ["expense", "list", "--household-id", "1"])
        assert result.exit_code == 0
        mock_c.list_expenses.assert_called_once_with(1)

    def test_expense_create(self, runner: CliRunner) -> None:
        with patch("kowl.commands.expense.client") as mock_c:
            mock_c.create_expense.return_value = {"id": 5, "name": "Dinner", "amount": 80.0}
            result = runner.invoke(
                cli,
                [
                    "expense", "create",
                    "--household-id", "1",
                    "--name", "Dinner",
                    "--amount", "80.0",
                    "--paid-by", "bob",
                ],
            )
        assert result.exit_code == 0
        mock_c.create_expense.assert_called_once_with(1, "Dinner", 80.0, "bob")

    def test_expense_delete_with_yes(self, runner: CliRunner) -> None:
        with patch("kowl.commands.expense.client") as mock_c:
            mock_c.delete_expense.return_value = {}
            result = runner.invoke(cli, ["expense", "delete", "--yes", "5"])
        assert result.exit_code == 0
        mock_c.delete_expense.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# Tag commands
# ---------------------------------------------------------------------------


class TestTagCommands:
    def test_tag_list(self, runner: CliRunner) -> None:
        tags = [{"id": 1, "name": "dinner"}, {"id": 2, "name": "quick"}]
        with patch("kowl.commands.tag.client") as mock_c:
            mock_c.list_tags.return_value = tags
            result = runner.invoke(cli, ["tag", "list", "--household-id", "1"])
        assert result.exit_code == 0
        mock_c.list_tags.assert_called_once_with(1)

    def test_tag_create(self, runner: CliRunner) -> None:
        with patch("kowl.commands.tag.client") as mock_c:
            mock_c.create_tag.return_value = {"id": 3, "name": "vegan"}
            result = runner.invoke(
                cli, ["tag", "create", "--household-id", "1", "--name", "vegan"]
            )
        assert result.exit_code == 0
        mock_c.create_tag.assert_called_once_with(1, "vegan")

    def test_tag_list_json(self, runner: CliRunner) -> None:
        tags = [{"id": 1, "name": "dinner"}]
        with patch("kowl.commands.tag.client") as mock_c:
            mock_c.list_tags.return_value = tags
            result = runner.invoke(cli, ["--json", "tag", "list", "--household-id", "1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["name"] == "dinner"


# ---------------------------------------------------------------------------
# Edit command (mocked editor)
# ---------------------------------------------------------------------------


class TestRecipeEditCommand:
    def test_recipe_edit_no_changes(self, runner: CliRunner) -> None:
        """If YAML is unchanged, no API calls should be made."""
        import yaml

        recipe = {
            "id": 5,
            "name": "Chimichurri",
            "description": "Fresh herb sauce",
            "cook_time": 0,
            "prep_time": 10,
            "time": 10,
            "yields": 4,
            "source": "",
            "visibility": 0,
            "household_id": 1,
            "items": [
                {"id": 1, "name": "parsley", "description": "2 cups", "optional": False}
            ],
            "tags": [{"id": 1, "name": "sauce"}],
        }

        with patch("kowl.commands.recipe.client") as mock_c, \
             patch("kowl.commands.recipe._open_editor") as mock_editor:
            mock_c.get_recipe.return_value = recipe
            # Return the same YAML (no changes)
            from kowl.commands.recipe import _recipe_to_yaml_dict
            yaml_dict = _recipe_to_yaml_dict(recipe)
            mock_editor.return_value = yaml.dump(yaml_dict)
            result = runner.invoke(cli, ["recipe", "edit", "5"])

        assert result.exit_code == 0
        mock_c.update_recipe.assert_not_called()
        mock_c.add_recipe_item.assert_not_called()
        mock_c.remove_recipe_item.assert_not_called()

    def test_recipe_edit_change_name(self, runner: CliRunner) -> None:
        """Changing the name should call update_recipe."""
        import yaml

        recipe = {
            "id": 5,
            "name": "Chimichurri",
            "description": "",
            "cook_time": 0,
            "prep_time": 0,
            "time": 0,
            "yields": 0,
            "source": "",
            "visibility": 0,
            "household_id": 1,
            "items": [],
            "tags": [],
        }

        with patch("kowl.commands.recipe.client") as mock_c, \
             patch("kowl.commands.recipe._open_editor") as mock_editor:
            mock_c.get_recipe.return_value = recipe
            mock_c.update_recipe.return_value = {"id": 5, "name": "Chimichurri Verde"}
            edited = {
                "name": "Chimichurri Verde",
                "description": "",
                "cook_time": 0,
                "prep_time": 0,
                "time": 0,
                "yields": 0,
                "source": "",
                "visibility": 0,
                "tags": [],
                "items": [],
            }
            mock_editor.return_value = yaml.dump(edited)
            result = runner.invoke(cli, ["recipe", "edit", "5"])

        assert result.exit_code == 0
        mock_c.update_recipe.assert_called_once_with(5, {"name": "Chimichurri Verde"})

    def test_recipe_edit_add_ingredient(self, runner: CliRunner) -> None:
        """Adding a new ingredient should call add_recipe_item."""
        import yaml

        recipe = {
            "id": 5,
            "name": "Pasta",
            "description": "",
            "cook_time": 0,
            "prep_time": 0,
            "time": 0,
            "yields": 0,
            "source": "",
            "visibility": 0,
            "household_id": 1,
            "items": [],
            "tags": [],
        }

        with patch("kowl.commands.recipe.client") as mock_c, \
             patch("kowl.commands.recipe._open_editor") as mock_editor:
            mock_c.get_recipe.return_value = recipe
            mock_c.add_recipe_item.return_value = {"id": 10, "name": "spaghetti"}
            edited = {
                "name": "Pasta",
                "description": "",
                "cook_time": 0,
                "prep_time": 0,
                "time": 0,
                "yields": 0,
                "source": "",
                "visibility": 0,
                "tags": [],
                "items": [{"name": "spaghetti", "description": "200g", "optional": False}],
            }
            mock_editor.return_value = yaml.dump(edited)
            result = runner.invoke(cli, ["recipe", "edit", "5"])

        assert result.exit_code == 0
        mock_c.add_recipe_item.assert_called_once_with(5, "spaghetti", "200g", False)

    def test_recipe_edit_remove_ingredient(self, runner: CliRunner) -> None:
        """Removing an ingredient from YAML should call remove_recipe_item."""
        import yaml

        recipe = {
            "id": 5,
            "name": "Pasta",
            "description": "",
            "cook_time": 0,
            "prep_time": 0,
            "time": 0,
            "yields": 0,
            "source": "",
            "visibility": 0,
            "household_id": 1,
            "items": [
                {"id": 7, "name": "spaghetti", "description": "200g", "optional": False}
            ],
            "tags": [],
        }

        with patch("kowl.commands.recipe.client") as mock_c, \
             patch("kowl.commands.recipe._open_editor") as mock_editor:
            mock_c.get_recipe.return_value = recipe
            mock_c.remove_recipe_item.return_value = {}
            edited = {
                "name": "Pasta",
                "description": "",
                "cook_time": 0,
                "prep_time": 0,
                "time": 0,
                "yields": 0,
                "source": "",
                "visibility": 0,
                "tags": [],
                "items": [],  # removed spaghetti
            }
            mock_editor.return_value = yaml.dump(edited)
            result = runner.invoke(cli, ["recipe", "edit", "5"])

        assert result.exit_code == 0
        mock_c.remove_recipe_item.assert_called_once_with(5, 7)
