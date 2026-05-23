"""Tests for the KitchenOwl API client (kowl.api).

All HTTP calls are mocked so no real network traffic is made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from kowl.api import KitchenOwlClient, KowlAPIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int = 200, json_data: object = None, text: str = "") -> MagicMock:
    """Build a mock requests.Response."""
    mock = MagicMock(spec=requests.Response)
    mock.status_code = status_code
    mock.ok = status_code < 400
    if json_data is not None:
        mock.content = json.dumps(json_data).encode()
        mock.json.return_value = json_data
    else:
        mock.content = text.encode()
        mock.json.side_effect = ValueError("No JSON")
    mock.text = text or (json.dumps(json_data) if json_data else "")
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client() -> KitchenOwlClient:
    """Return a fresh API client with a dummy key."""
    client = KitchenOwlClient.__new__(KitchenOwlClient)
    client.base_url = "https://kitchenowl.example.com/api"
    client.api_key = "test-token"
    import requests as req
    client._session = req.Session()
    client._session.headers.update(
        {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    )
    return client


# ---------------------------------------------------------------------------
# _request error handling
# ---------------------------------------------------------------------------


class TestRequestErrorHandling:
    def test_401_raises_auth_error(self, api_client: KitchenOwlClient) -> None:
        mock_resp = _mock_response(401, {"message": "Unauthorized"})
        with patch.object(api_client._session, "request", return_value=mock_resp):
            with pytest.raises(KowlAPIError) as exc_info:
                api_client._get("/some/path")
        assert "Authentication failed" in str(exc_info.value)
        assert exc_info.value.status_code == 401

    def test_404_raises_not_found(self, api_client: KitchenOwlClient) -> None:
        mock_resp = _mock_response(404, {"message": "Not Found"})
        with patch.object(api_client._session, "request", return_value=mock_resp):
            with pytest.raises(KowlAPIError) as exc_info:
                api_client._get("/recipe/9999")
        assert "Not found" in str(exc_info.value)
        assert exc_info.value.status_code == 404

    def test_500_raises_generic_error(self, api_client: KitchenOwlClient) -> None:
        mock_resp = _mock_response(500, {"error": "internal"})
        with patch.object(api_client._session, "request", return_value=mock_resp):
            with pytest.raises(KowlAPIError) as exc_info:
                api_client._get("/recipe/1")
        assert "500" in str(exc_info.value)

    def test_connection_error_raises_kowl_error(self, api_client: KitchenOwlClient) -> None:
        with patch.object(
            api_client._session,
            "request",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            with pytest.raises(KowlAPIError) as exc_info:
                api_client._get("/household")
        assert "Cannot connect to" in str(exc_info.value)

    def test_timeout_raises_kowl_error(self, api_client: KitchenOwlClient) -> None:
        with patch.object(
            api_client._session,
            "request",
            side_effect=requests.exceptions.Timeout(),
        ):
            with pytest.raises(KowlAPIError) as exc_info:
                api_client._get("/household")
        assert "timed out" in str(exc_info.value)

    def test_204_returns_empty_dict(self, api_client: KitchenOwlClient) -> None:
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 204
        mock_resp.ok = True
        mock_resp.content = b""
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client._delete("/recipe/1")
        assert result == {}


# ---------------------------------------------------------------------------
# Household
# ---------------------------------------------------------------------------


class TestHousehold:
    def test_list_households(self, api_client: KitchenOwlClient) -> None:
        data = [{"id": 1, "name": "Home"}]
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.list_households()
        assert result == data


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


class TestRecipes:
    def test_list_recipes(self, api_client: KitchenOwlClient) -> None:
        data = [{"id": 1, "name": "Pasta"}, {"id": 2, "name": "Pizza"}]
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.list_recipes(1)
        assert result == data
        call_args = mock_req.call_args
        assert "/household/1/recipe" in call_args[0][1]

    def test_get_recipe(self, api_client: KitchenOwlClient) -> None:
        data = {"id": 5, "name": "Risotto", "items": [], "tags": []}
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.get_recipe(5)
        assert result["name"] == "Risotto"

    def test_create_recipe(self, api_client: KitchenOwlClient) -> None:
        body = {"name": "Tacos", "description": "Easy tacos"}
        created = {"id": 10, **body}
        mock_resp = _mock_response(200, created)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.create_recipe(1, body)
        assert result["id"] == 10
        call_kwargs = mock_req.call_args
        assert call_kwargs[1]["json"] == body

    def test_update_recipe(self, api_client: KitchenOwlClient) -> None:
        updated = {"id": 5, "name": "Updated Risotto"}
        mock_resp = _mock_response(200, updated)
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.update_recipe(5, {"name": "Updated Risotto"})
        assert result["name"] == "Updated Risotto"

    def test_delete_recipe(self, api_client: KitchenOwlClient) -> None:
        mock_resp = _mock_response(204, None, "")
        mock_resp.content = b""
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.delete_recipe(5)
        assert result == {}

    def test_search_recipes(self, api_client: KitchenOwlClient) -> None:
        data = [{"id": 3, "name": "Soup"}]
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.search_recipes(1, "soup")
        assert result == data
        assert mock_req.call_args[1]["json"] == {"query": "soup"}


# ---------------------------------------------------------------------------
# Recipe items
# ---------------------------------------------------------------------------


class TestRecipeItems:
    def test_add_recipe_item(self, api_client: KitchenOwlClient) -> None:
        data = {"id": 20, "name": "garlic", "description": "2 cloves", "optional": False}
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.add_recipe_item(5, "garlic", "2 cloves", False)
        assert result["name"] == "garlic"
        assert mock_req.call_args[1]["json"]["name"] == "garlic"

    def test_remove_recipe_item(self, api_client: KitchenOwlClient) -> None:
        mock_resp = _mock_response(204, None, "")
        mock_resp.content = b""
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.remove_recipe_item(5, 20)
        assert result == {}
        url = mock_req.call_args[0][1]
        assert "/recipe/5/items/20" in url


# ---------------------------------------------------------------------------
# Shopping lists
# ---------------------------------------------------------------------------


class TestShopping:
    def test_list_shopping_lists(self, api_client: KitchenOwlClient) -> None:
        data = [{"id": 1, "name": "Weekly"}]
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.list_shopping_lists(1)
        assert result == data

    def test_list_shopping_items(self, api_client: KitchenOwlClient) -> None:
        data = [{"id": 1, "name": "Milk"}, {"id": 2, "name": "Eggs"}]
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.list_shopping_items(1)
        assert len(result) == 2

    def test_add_shopping_item(self, api_client: KitchenOwlClient) -> None:
        data = {"id": 5, "name": "Butter", "description": "250g"}
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.add_shopping_item(1, "Butter", "250g")
        assert result["name"] == "Butter"
        assert mock_req.call_args[1]["json"]["name"] == "Butter"

    def test_remove_shopping_item(self, api_client: KitchenOwlClient) -> None:
        mock_resp = _mock_response(204, None, "")
        mock_resp.content = b""
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.remove_shopping_item(1, 5)
        assert result == {}
        url = mock_req.call_args[0][1]
        assert "/shoppinglist/1/items/5" in url


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


class TestExpenses:
    def test_list_expenses(self, api_client: KitchenOwlClient) -> None:
        data = [{"id": 1, "name": "Groceries", "amount": 45.50}]
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.list_expenses(1)
        assert result == data

    def test_create_expense_with_paid_by(self, api_client: KitchenOwlClient) -> None:
        data = {"id": 3, "name": "Dinner", "amount": 80.0, "paid_by": "alice"}
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.create_expense(1, "Dinner", 80.0, "alice")
        assert result["paid_by"] == "alice"
        body = mock_req.call_args[1]["json"]
        assert body["paid_by"] == "alice"
        assert body["amount"] == 80.0

    def test_create_expense_without_paid_by(self, api_client: KitchenOwlClient) -> None:
        data = {"id": 4, "name": "Lunch", "amount": 12.5}
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.create_expense(1, "Lunch", 12.5)
        body = mock_req.call_args[1]["json"]
        assert "paid_by" not in body

    def test_delete_expense(self, api_client: KitchenOwlClient) -> None:
        mock_resp = _mock_response(204, None, "")
        mock_resp.content = b""
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.delete_expense(3)
        assert result == {}
        url = mock_req.call_args[0][1]
        assert "/expense/3" in url


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TestTags:
    def test_list_tags(self, api_client: KitchenOwlClient) -> None:
        data = [{"id": 1, "name": "dinner"}, {"id": 2, "name": "quick"}]
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.list_tags(1)
        assert len(result) == 2

    def test_create_tag(self, api_client: KitchenOwlClient) -> None:
        data = {"id": 3, "name": "vegan"}
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.create_tag(1, "vegan")
        assert result["name"] == "vegan"
        assert mock_req.call_args[1]["json"]["name"] == "vegan"


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class TestPlanner:
    def test_list_planner(self, api_client: KitchenOwlClient) -> None:
        data = [{"day": "Monday", "recipe": {"id": 1, "name": "Pasta"}}]
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp):
            result = api_client.list_planner(1)
        assert result[0]["day"] == "Monday"

    def test_add_planner_entry(self, api_client: KitchenOwlClient) -> None:
        data = {"id": 1, "recipe_id": 5, "day": "Tuesday"}
        mock_resp = _mock_response(200, data)
        with patch.object(api_client._session, "request", return_value=mock_resp) as mock_req:
            result = api_client.add_planner_entry(1, 5, "Tuesday")
        assert result["day"] == "Tuesday"
        body = mock_req.call_args[1]["json"]
        assert body["recipe_id"] == 5
        assert body["day"] == "Tuesday"
