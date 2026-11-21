"""Realm definition: load, validate and turn into Keycloak representations."""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator


class RealmError(ValueError):
    """The realm definition is invalid."""


def load_schema() -> dict[str, Any]:
    text = resources.files("aurai_workspace").joinpath("schemas/realm.schema.json").read_text(encoding="utf-8")
    return json.loads(text)


def load_realm(path: str | Path) -> dict[str, Any]:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise RealmError(f"{path}: expected a mapping at the top level")
    return document


def validate(document: dict[str, Any]) -> list[str]:
    """Return a list of problems; empty means the realm definition is valid."""
    validator = Draft202012Validator(load_schema())
    problems = [
        f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]
    if problems:
        return problems

    roles = {r["name"] for r in document["roles"]}
    groups = {g["name"] for g in document["groups"]}

    for duplicate in _duplicates(r["name"] for r in document["roles"]):
        problems.append(f"roles: duplicate role {duplicate}")
    for duplicate in _duplicates(g["name"] for g in document["groups"]):
        problems.append(f"groups: duplicate group {duplicate}")
    for duplicate in _duplicates(u["username"] for u in document.get("users", [])):
        problems.append(f"users: duplicate username {duplicate}")

    for group in document["groups"]:
        for role in group["roles"]:
            if role not in roles:
                problems.append(f"groups/{group['name']}: unknown role {role}")
    for user in document.get("users", []):
        for group in user["groups"]:
            if group not in groups:
                problems.append(f"users/{user['username']}: unknown group {group}")
    for client in document["clients"]:
        for uri in client["redirect_uris"] + client.get("web_origins", []):
            problems.extend(_check_uri(client["client_id"], uri))
    return problems


def _duplicates(values) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes


def _check_uri(client_id: str, uri: str) -> list[str]:
    parsed = urlparse(uri)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return [f"clients/{client_id}: {uri!r} is not an http(s) URL"]
    if parsed.hostname == "*" or "*" in parsed.netloc:
        return [f"clients/{client_id}: wildcard hosts are not allowed ({uri})"]
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
        return [f"clients/{client_id}: {uri} must use https (http is allowed for localhost only)"]
    return []


def client_secret(client: dict[str, Any], environ: dict[str, str] | None = None) -> str:
    """Read a client's secret from its environment variable."""
    env = os.environ if environ is None else environ
    value = env.get(client["secret_env"], "")
    if not value:
        raise RealmError(f"environment variable {client['secret_env']} is not set for client {client['client_id']}")
    return value


def realm_representation(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "realm": document["realm"],
        "displayName": document.get("display_name", document["realm"]),
        "enabled": True,
        "registrationAllowed": document.get("registration_allowed", False),
        "loginWithEmailAllowed": document.get("login_with_email_allowed", True),
        "accessTokenLifespan": document.get("access_token_lifespan_seconds", 900),
        "bruteForceProtected": True,
    }


def client_representation(client: dict[str, Any], secret: str) -> dict[str, Any]:
    """Confidential OIDC client using the authorization code flow, with the claims Open WebUI and LiteLLM need."""
    mappers = [
        _mapper(
            "groups",
            "oidc-group-membership-mapper",
            {
                "claim.name": "groups",
                "full.path": "false",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
            },
        ),
        _mapper(
            "roles",
            "oidc-usermodel-realm-role-mapper",
            {
                "claim.name": "roles",
                "multivalued": "true",
                "jsonType.label": "String",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
            },
        ),
    ]
    if client.get("audience"):
        mappers.append(
            _mapper(
                "audience",
                "oidc-audience-mapper",
                {
                    "included.custom.audience": client["audience"],
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                },
            )
        )
    return {
        "clientId": client["client_id"],
        "name": client.get("name", client["client_id"]),
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "secret": secret,
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "redirectUris": client["redirect_uris"],
        "webOrigins": client.get("web_origins", []),
        "protocolMappers": mappers,
    }


def _mapper(name: str, mapper_type: str, config: dict[str, str]) -> dict[str, Any]:
    return {"name": name, "protocol": "openid-connect", "protocolMapper": mapper_type, "config": config}
