import pytest

from aurai_workspace.keycloak import KeycloakAdmin, KeycloakError
from aurai_workspace.realm import RealmError

from .fake_keycloak import FakeKeycloak

ENV = {"OPEN_WEBUI_CLIENT_SECRET": "client-secret"}


def admin_for(fake: FakeKeycloak) -> KeycloakAdmin:
    return KeycloakAdmin(fake.client(), username="admin", password=fake.admin_password)


def verbs(actions):
    return [a.verb for a in actions]


def test_plan_on_empty_keycloak_changes_nothing(realm):
    fake = FakeKeycloak()
    actions = admin_for(fake).reconcile(realm, apply=False, environ=ENV)
    assert set(verbs(actions)) == {"create"}
    assert fake.realms == {}
    assert all(method == "GET" or "token" in path for method, path in fake.calls)


def test_apply_creates_everything(realm):
    fake = FakeKeycloak()
    admin_for(fake).reconcile(realm, apply=True, environ=ENV, demo_password="demo-pass")
    assert "aurai" in fake.realms
    assert set(fake.roles["aurai"]) == {"member", "builder", "admin"}
    assert set(fake.groups["aurai"]) == {
        "workspace-members",
        "workspace-builders",
        "workspace-admins",
        "knowledge-ops",
        "knowledge-hr",
        "knowledge-finance",
        "approvers-ops",
        "approvers-finance",
    }
    client = next(iter(fake.clients["aurai"].values()))
    assert client["clientId"] == "open-webui" and client["secret"] == "client-secret"
    assert len(fake.users["aurai"]) == 8
    assert set(fake.passwords.values()) == {"demo-pass"}


def test_group_roles_and_user_membership(realm):
    fake = FakeKeycloak()
    admin_for(fake).reconcile(realm, apply=True, environ=ENV)
    groups = fake.groups["aurai"]
    builders = groups["workspace-builders"]["id"]
    assert fake.group_roles[f"aurai/{builders}"] == {"member", "builder"}
    devon = next(u for u in fake.users["aurai"].values() if u["username"] == "devon.park")
    assert fake.user_groups[devon["id"]] == {"workspace-builders"}


def test_approvers_get_their_group_and_no_roles(realm):
    fake = FakeKeycloak()
    admin_for(fake).reconcile(realm, apply=True, environ=ENV)
    groups = fake.groups["aurai"]
    for name in ("approvers-ops", "approvers-finance"):
        assert fake.group_roles.get(f"aurai/{groups[name]['id']}", set()) == set()
    rosa = next(u for u in fake.users["aurai"].values() if u["username"] == "rosa.delgado")
    assert fake.user_groups[rosa["id"]] == {"workspace-members", "approvers-ops"}


def test_apply_is_idempotent(realm):
    fake = FakeKeycloak()
    admin = admin_for(fake)
    admin.reconcile(realm, apply=True, environ=ENV)
    writes = [c for c in fake.calls if c[0] in ("POST", "PUT") and "token" not in c[1]]
    second = admin.reconcile(realm, apply=True, environ=ENV)
    assert set(verbs(second)) == {"ok"}
    assert [c for c in fake.calls if c[0] in ("POST", "PUT") and "token" not in c[1]] == writes


def test_plan_after_apply_reports_no_changes(realm):
    fake = FakeKeycloak()
    admin = admin_for(fake)
    admin.reconcile(realm, apply=True, environ=ENV)
    assert set(verbs(admin.reconcile(realm, apply=False))) == {"ok"}


def test_drift_is_repaired(realm):
    fake = FakeKeycloak()
    admin = admin_for(fake)
    admin.reconcile(realm, apply=True, environ=ENV)
    next(iter(fake.clients["aurai"].values()))["redirectUris"] = ["http://localhost:1/other"]
    fake.realms["aurai"]["registrationAllowed"] = True
    plan = admin.reconcile(realm, apply=False)
    assert ("update", "client") in {(a.verb, a.kind) for a in plan}
    assert ("update", "realm") in {(a.verb, a.kind) for a in plan}
    admin.reconcile(realm, apply=True, environ=ENV)
    assert fake.realms["aurai"]["registrationAllowed"] is False
    assert next(iter(fake.clients["aurai"].values()))["redirectUris"] == realm["clients"][0]["redirect_uris"]


def test_removed_entries_are_never_deleted(realm):
    fake = FakeKeycloak()
    admin = admin_for(fake)
    admin.reconcile(realm, apply=True, environ=ENV)
    realm["users"] = realm["users"][:1]
    admin.reconcile(realm, apply=True, environ=ENV)
    assert len(fake.users["aurai"]) == 8
    assert not any(method == "DELETE" for method, _ in fake.calls)


def test_apply_without_client_secret_fails_before_changing_clients(realm):
    fake = FakeKeycloak()
    with pytest.raises(RealmError):
        admin_for(fake).reconcile(realm, apply=True, environ={})
    assert fake.clients["aurai"] == {}


def test_bad_admin_password(realm):
    fake = FakeKeycloak()
    admin = KeycloakAdmin(fake.client(), username="admin", password="wrong")
    with pytest.raises(KeycloakError):
        admin.reconcile(realm, apply=False)
