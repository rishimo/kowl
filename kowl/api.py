"""KitchenOwl API client.

All methods raise KowlAPIError on failure. Callers are responsible for
catching that exception and presenting it to the user.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests

from .config import config


class KowlAPIError(Exception):
    """Raised when an API request fails."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class KitchenOwlClient:
    """Thin wrapper around the KitchenOwl REST API."""

    def __init__(self) -> None:
        self.base_url = config.url
        self.api_key = config.api_key
        self._session = requests.Session()
        if self.api_key:
            self._session.headers["Authorization"] = f"Bearer {self.api_key}"
        self._session.headers["Content-Type"] = "application/json"
        self._session.headers["Accept"] = "application/json"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> Any:
        """Perform an HTTP request and return parsed JSON.

        Raises KowlAPIError on any non-2xx response or network failure.
        """
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                timeout=30,
            )
        except requests.exceptions.ConnectionError:
            raise KowlAPIError(f"Cannot connect to {self.base_url}")
        except requests.exceptions.Timeout:
            raise KowlAPIError(f"Request timed out connecting to {self.base_url}")
        except requests.exceptions.RequestException as exc:
            raise KowlAPIError(str(exc))

        if response.status_code == 401:
            raise KowlAPIError(
                "Authentication failed. Check KITCHENOWL_API_KEY", status_code=401
            )
        if response.status_code == 404:
            raise KowlAPIError(
                f"Not found: {path}", status_code=404
            )
        if not response.ok:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise KowlAPIError(
                f"HTTP {response.status_code}: {detail}", status_code=response.status_code
            )

        # Some DELETE endpoints return empty body
        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except json.JSONDecodeError:
            return {}

    def _get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, body: Any = None) -> Any:
        return self._request("POST", path, json_body=body)

    def _delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # ------------------------------------------------------------------
    # Household
    # ------------------------------------------------------------------

    def list_households(self) -> List[Dict[str, Any]]:
        """Return list of households the authenticated user belongs to."""
        return self._get("/household")

    # ------------------------------------------------------------------
    # Recipes
    # ------------------------------------------------------------------

    def list_recipes(self, household_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/household/{household_id}/recipe")

    def get_recipe(self, recipe_id: int) -> Dict[str, Any]:
        return self._get(f"/recipe/{recipe_id}")

    def create_recipe(self, household_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/household/{household_id}/recipe", data)

    def update_recipe(self, recipe_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/recipe/{recipe_id}", data)

    def delete_recipe(self, recipe_id: int) -> Dict[str, Any]:
        return self._delete(f"/recipe/{recipe_id}")

    def search_recipes(self, household_id: int, query: str) -> List[Dict[str, Any]]:
        return self._post(f"/household/{household_id}/recipe/search", {"query": query})

    def scrape_recipe(self, household_id: int, url: str) -> Dict[str, Any]:
        return self._post(f"/household/{household_id}/scrape", {"url": url})

    # ------------------------------------------------------------------
    # Recipe items (ingredients)
    # ------------------------------------------------------------------

    def add_recipe_item(
        self, recipe_id: int, name: str, description: str = "", optional: bool = False
    ) -> Dict[str, Any]:
        return self._post(
            f"/recipe/{recipe_id}/items",
            {"name": name, "description": description, "optional": optional},
        )

    def remove_recipe_item(self, recipe_id: int, item_id: int) -> Dict[str, Any]:
        return self._delete(f"/recipe/{recipe_id}/items/{item_id}")

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def list_tags(self, household_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/household/{household_id}/tag")

    def create_tag(self, household_id: int, name: str) -> Dict[str, Any]:
        return self._post(f"/household/{household_id}/tag", {"name": name})

    # ------------------------------------------------------------------
    # Shopping lists
    # ------------------------------------------------------------------

    def list_shopping_lists(self, household_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/household/{household_id}/shoppinglist")

    def create_shopping_list(self, household_id: int, name: str) -> Dict[str, Any]:
        return self._post(f"/household/{household_id}/shoppinglist", {"name": name})

    def delete_shopping_list(self, list_id: int) -> Dict[str, Any]:
        return self._delete(f"/shoppinglist/{list_id}")

    def list_shopping_items(self, list_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/shoppinglist/{list_id}/items")

    def add_shopping_item(
        self, list_id: int, name: str, description: str = ""
    ) -> Dict[str, Any]:
        return self._post(
            f"/shoppinglist/{list_id}/items",
            {"name": name, "description": description},
        )

    def remove_shopping_item(self, list_id: int, item_id: int) -> Dict[str, Any]:
        return self._delete(f"/shoppinglist/{list_id}/items/{item_id}")

    # ------------------------------------------------------------------
    # Planner
    # ------------------------------------------------------------------

    def list_planner(self, household_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/household/{household_id}/planner")

    def add_planner_entry(
        self, household_id: int, recipe_id: int, day: str
    ) -> Dict[str, Any]:
        return self._post(
            f"/household/{household_id}/planner",
            {"recipe_id": recipe_id, "day": day},
        )

    def remove_planner_entry(
        self, household_id: int, recipe_id: int, day: str
    ) -> Dict[str, Any]:
        return self._delete(f"/household/{household_id}/planner")

    # ------------------------------------------------------------------
    # Expenses
    # ------------------------------------------------------------------

    def list_expenses(self, household_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/household/{household_id}/expense")

    def create_expense(
        self,
        household_id: int,
        name: str,
        amount: float,
        paid_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"name": name, "amount": amount}
        if paid_by:
            body["paid_by"] = paid_by
        return self._post(f"/household/{household_id}/expense", body)

    def delete_expense(self, expense_id: int) -> Dict[str, Any]:
        return self._delete(f"/expense/{expense_id}")

    # ------------------------------------------------------------------
    # Household items (ingredients catalogue)
    # ------------------------------------------------------------------

    def list_items(self, household_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/household/{household_id}/item")


# Module-level singleton
client = KitchenOwlClient()
