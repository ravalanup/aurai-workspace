"""aurai-workspace command line.

  aurai-workspace validate realm/aurai-realm.yaml
  aurai-workspace plan     realm/aurai-realm.yaml --base-url http://localhost:8080
  aurai-workspace apply    realm/aurai-realm.yaml --base-url http://localhost:8080

Credentials come from the environment, never from the command line:
  KEYCLOAK_ADMIN_USER / KEYCLOAK_ADMIN_PASSWORD   Keycloak admin (apply and plan)
  <client secret_env>                              each client's secret, named in the realm file
  AURAI_DEMO_PASSWORD                              password given to newly created demo users (optional)
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

from .keycloak import KeycloakAdmin, KeycloakError
from .realm import RealmError, load_realm, validate


def _load_valid(path: str) -> dict | None:
    document = load_realm(path)
    problems = validate(document)
    for problem in problems:
        print(f"{path}: error: {problem}", file=sys.stderr)
    return None if problems else document


def cmd_validate(args: argparse.Namespace) -> int:
    document = _load_valid(args.realm_file)
    if document is None:
        return 1
    print(
        f"{args.realm_file}: ok ({len(document['roles'])} roles, {len(document['groups'])} groups, "
        f"{len(document.get('users', []))} users)"
    )
    return 0


def _admin(args: argparse.Namespace) -> KeycloakAdmin:
    user = os.environ.get("KEYCLOAK_ADMIN_USER", "")
    password = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "")
    if not user or not password:
        raise RealmError("set KEYCLOAK_ADMIN_USER and KEYCLOAK_ADMIN_PASSWORD")
    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout)
    return KeycloakAdmin(client, username=user, password=password)


def _run(args: argparse.Namespace, *, apply: bool) -> int:
    document = _load_valid(args.realm_file)
    if document is None:
        return 1
    try:
        admin = _admin(args)
        actions = admin.reconcile(document, apply=apply, demo_password=os.environ.get("AURAI_DEMO_PASSWORD") or None)
    except (RealmError, KeycloakError, httpx.HTTPError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for action in actions:
        print(action)
    changes = sum(1 for a in actions if a.verb != "ok")
    print(f"{'applied' if apply else 'planned'}: {changes} change(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aurai-workspace", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check a realm file without contacting Keycloak")
    p.add_argument("realm_file")
    p.set_defaults(func=cmd_validate)

    for name, apply in (("plan", False), ("apply", True)):
        p = sub.add_parser(name, help=("create and update" if apply else "show what apply would change"))
        p.add_argument("realm_file")
        p.add_argument("--base-url", required=True, help="Keycloak base URL, for example http://localhost:8080")
        p.add_argument("--timeout", type=float, default=30.0)
        p.set_defaults(func=lambda a, apply=apply: _run(a, apply=apply))

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RealmError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
