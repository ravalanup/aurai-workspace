"""Idempotent reconciliation of a realm definition against Keycloak's admin REST API.

`plan` only reads. `apply` creates what is missing and updates what differs. Nothing is deleted: removing
a role, group or user from the definition does not remove it from Keycloak, because deletes in an identity
system should be deliberate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .realm import client_representation, client_secret, realm_representation


class KeycloakError(RuntimeError):
    pass


@dataclass(frozen=True)
class Action:
    verb: str  # create | update | ok
    kind: str
    name: str

    def __str__(self) -> str:
        return f"{self.verb:<7} {self.kind} {self.name}"


class KeycloakAdmin:
    def __init__(self, client: httpx.Client, *, username: str, password: str) -> None:
        self._http = client
        self._username = username
        self._password = password
        self._token: str | None = None

    # -- transport ---------------------------------------------------------------------------------------------

    def login(self) -> None:
        response = self._http.post(
            "/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self._username,
                "password": self._password,
            },
        )
        if response.status_code != 200:
            raise KeycloakError(f"admin login failed (HTTP {response.status_code})")
        self._token = response.json()["access_token"]

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._token is None:
            self.login()
        headers = {"Authorization": f"Bearer {self._token}"}
        return self._http.request(method, f"/admin{path}", headers=headers, **kwargs)

    def _get(self, path: str, **kwargs: Any) -> Any:
        response = self._request("GET", path, **kwargs)
        if response.status_code == 404:
            return None
        self._expect(response, (200,), "GET", path)
        return response.json()

    def _send(self, method: str, path: str, body: Any = None, ok: tuple[int, ...] = (200, 201, 204)) -> httpx.Response:
        response = self._request(method, path, json=body)
        self._expect(response, ok, method, path)
        return response

    @staticmethod
    def _expect(response: httpx.Response, ok: tuple[int, ...], method: str, path: str) -> None:
        if response.status_code not in ok:
            raise KeycloakError(f"{method} {path} failed (HTTP {response.status_code})")

    # -- reconcile ---------------------------------------------------------------------------------------------

    def reconcile(
        self,
        document: dict[str, Any],
        *,
        apply: bool,
        environ: dict[str, str] | None = None,
        demo_password: str | None = None,
    ) -> list[Action]:
        """Compare the definition with Keycloak. With apply=True, make the changes."""
        actions: list[Action] = []
        realm = document["realm"]

        existing = self._get(f"/realms/{realm}")
        desired = realm_representation(document)
        if existing is None:
            actions.append(Action("create", "realm", realm))
            if apply:
                self._send("POST", "/realms", desired)
        elif _differs(existing, desired):
            actions.append(Action("update", "realm", realm))
            if apply:
                self._send("PUT", f"/realms/{realm}", {**existing, **desired})
        else:
            actions.append(Action("ok", "realm", realm))

        # Without the realm there is nothing further to compare in a dry run.
        realm_exists = existing is not None or apply
        if not realm_exists:
            for role in document["roles"]:
                actions.append(Action("create", "role", role["name"]))
            for group in document["groups"]:
                actions.append(Action("create", "group", group["name"]))
            for client in document["clients"]:
                actions.append(Action("create", "client", client["client_id"]))
            for user in document.get("users", []):
                actions.append(Action("create", "user", user["username"]))
            return actions

        actions += self._roles(realm, document, apply)
        actions += self._groups(realm, document, apply)
        actions += self._clients(realm, document, apply, environ)
        actions += self._users(realm, document, apply, demo_password)
        return actions

    def _roles(self, realm: str, document: dict[str, Any], apply: bool) -> list[Action]:
        have = {r["name"] for r in (self._get(f"/realms/{realm}/roles") or [])}
        actions = []
        for role in document["roles"]:
            if role["name"] in have:
                actions.append(Action("ok", "role", role["name"]))
                continue
            actions.append(Action("create", "role", role["name"]))
            if apply:
                self._send(
                    "POST", f"/realms/{realm}/roles", {"name": role["name"], "description": role.get("description", "")}
                )
        return actions

    def _groups(self, realm: str, document: dict[str, Any], apply: bool) -> list[Action]:
        groups = {g["name"]: g for g in (self._get(f"/realms/{realm}/groups") or [])}
        actions = []
        for group in document["groups"]:
            name = group["name"]
            created = name not in groups
            if created:
                actions.append(Action("create", "group", name))
                if apply:
                    self._send("POST", f"/realms/{realm}/groups", {"name": name})
                    groups[name] = self._find_group(realm, name)
            else:
                actions.append(Action("ok", "group", name))

            group_id = groups.get(name, {}).get("id")
            current = set()
            if group_id:
                mapped = self._get(f"/realms/{realm}/groups/{group_id}/role-mappings/realm") or []
                current = {r["name"] for r in mapped}
            missing = [r for r in group["roles"] if r not in current]
            if missing:
                actions.append(Action("update", "group-roles", f"{name}: +{', '.join(missing)}"))
                if apply and group_id:
                    representations = [self._get(f"/realms/{realm}/roles/{r}") for r in missing]
                    self._send("POST", f"/realms/{realm}/groups/{group_id}/role-mappings/realm", representations)
        return actions

    def _find_group(self, realm: str, name: str) -> dict[str, Any]:
        for group in self._get(f"/realms/{realm}/groups", params={"search": name}) or []:
            if group["name"] == name:
                return group
        raise KeycloakError(f"group {name} not found after creation")

    def _clients(
        self, realm: str, document: dict[str, Any], apply: bool, environ: dict[str, str] | None
    ) -> list[Action]:
        actions = []
        for client in document["clients"]:
            client_id = client["client_id"]
            found = self._get(f"/realms/{realm}/clients", params={"clientId": client_id}) or []
            secret = client_secret(client, environ) if apply else "<secret>"
            desired = client_representation(client, secret)
            if not found:
                actions.append(Action("create", "client", client_id))
                if apply:
                    self._send("POST", f"/realms/{realm}/clients", desired)
                continue
            current = found[0]
            drift = _differs(current, {k: v for k, v in desired.items() if k not in ("secret", "protocolMappers")})
            drift = drift or _mappers_differ(current.get("protocolMappers", []), desired["protocolMappers"])
            if drift:
                actions.append(Action("update", "client", client_id))
                if apply:
                    self._send("PUT", f"/realms/{realm}/clients/{current['id']}", {**current, **desired})
            else:
                actions.append(Action("ok", "client", client_id))
        return actions

    def _users(self, realm: str, document: dict[str, Any], apply: bool, demo_password: str | None) -> list[Action]:
        actions = []
        group_ids = {g["name"]: g["id"] for g in (self._get(f"/realms/{realm}/groups") or [])}
        for user in document.get("users", []):
            username = user["username"]
            found = self._get(f"/realms/{realm}/users", params={"username": username, "exact": "true"}) or []
            if found:
                user_id = found[0]["id"]
                actions.append(Action("ok", "user", username))
            else:
                actions.append(Action("create", "user", username))
                user_id = None
                if apply:
                    body = {
                        "username": username,
                        "email": user["email"],
                        "emailVerified": True,
                        "enabled": True,
                        "firstName": user.get("first_name", ""),
                        "lastName": user.get("last_name", ""),
                    }
                    response = self._send("POST", f"/realms/{realm}/users", body)
                    user_id = response.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1] or None
                    if demo_password and user_id:
                        self._send(
                            "PUT",
                            f"/realms/{realm}/users/{user_id}/reset-password",
                            {"type": "password", "value": demo_password, "temporary": False},
                        )
            memberships = set()
            if user_id:
                memberships = {g["name"] for g in (self._get(f"/realms/{realm}/users/{user_id}/groups") or [])}
            for group in user["groups"]:
                if group in memberships:
                    continue
                actions.append(Action("update", "user-group", f"{username} -> {group}"))
                if apply and user_id and group in group_ids:
                    self._send("PUT", f"/realms/{realm}/users/{user_id}/groups/{group_ids[group]}")
        return actions


def _differs(current: dict[str, Any], desired: dict[str, Any]) -> bool:
    return any(current.get(key) != value for key, value in desired.items())


def _mappers_differ(current: list[dict[str, Any]], desired: list[dict[str, Any]]) -> bool:
    by_name = {m["name"]: m for m in current}
    for mapper in desired:
        existing = by_name.get(mapper["name"])
        if existing is None or existing.get("protocolMapper") != mapper["protocolMapper"]:
            return True
        if any(existing.get("config", {}).get(k) != v for k, v in mapper["config"].items()):
            return True
    return False
