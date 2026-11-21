import copy

import pytest

from aurai_workspace.realm import RealmError, client_representation, client_secret, realm_representation, validate


def test_shipped_realm_is_valid(realm):
    assert validate(realm) == []


def test_unknown_role_in_group(realm):
    realm["groups"][0]["roles"].append("superuser")
    assert any("unknown role superuser" in p for p in validate(realm))


def test_unknown_group_for_user(realm):
    realm["users"][0]["groups"] = ["nope"]
    assert any("unknown group nope" in p for p in validate(realm))


def test_duplicates_are_reported(realm):
    realm["roles"].append(copy.deepcopy(realm["roles"][0]))
    realm["users"].append(copy.deepcopy(realm["users"][0]))
    problems = validate(realm)
    assert any("duplicate role member" in p for p in problems)
    assert any("duplicate username" in p for p in problems)


@pytest.mark.parametrize(
    "uri,fragment",
    [
        ("http://workspace.example.com/cb", "must use https"),
        ("https://*.example.com/cb", "wildcard"),
        ("ftp://example.com/cb", "not an http(s) URL"),
    ],
)
def test_bad_redirect_uris(realm, uri, fragment):
    realm["clients"][0]["redirect_uris"] = [uri]
    assert any(fragment in p for p in validate(realm))


def test_localhost_http_is_allowed(realm):
    realm["clients"][0]["redirect_uris"] = ["http://localhost:3100/oauth/oidc/callback"]
    assert validate(realm) == []


def test_schema_rejects_unknown_keys_and_inline_secrets(realm):
    realm["clients"][0]["secret"] = "hunter2"
    assert validate(realm)


def test_users_carry_no_passwords(realm):
    assert all("password" not in user for user in realm["users"])


def test_client_secret_comes_from_environment(realm):
    client = realm["clients"][0]
    assert client_secret(client, {"OPEN_WEBUI_CLIENT_SECRET": "s3cret"}) == "s3cret"
    with pytest.raises(RealmError):
        client_secret(client, {})


def test_client_representation_has_the_claims_gateway_and_ui_need(realm):
    rep = client_representation(realm["clients"][0], "s3cret")
    assert rep["publicClient"] is False
    assert rep["standardFlowEnabled"] is True
    assert rep["directAccessGrantsEnabled"] is False
    mappers = {m["name"]: m for m in rep["protocolMappers"]}
    assert mappers["groups"]["config"]["claim.name"] == "groups"
    assert mappers["groups"]["config"]["full.path"] == "false"
    assert mappers["roles"]["config"]["claim.name"] == "roles"
    assert mappers["audience"]["config"]["included.custom.audience"] == "litellm"


def test_realm_representation_defaults():
    rep = realm_representation({"realm": "x"})
    assert rep["registrationAllowed"] is False and rep["bruteForceProtected"] is True
