"""An in-memory stand-in for the parts of Keycloak's admin API that aurai-workspace uses."""

from __future__ import annotations

import json
import re
import uuid

import httpx


class FakeKeycloak:
    def __init__(self, admin_password: str = "admin-pass") -> None:
        self.admin_password = admin_password
        self.realms: dict[str, dict] = {}
        self.roles: dict[str, dict[str, dict]] = {}
        self.groups: dict[str, dict[str, dict]] = {}
        self.group_roles: dict[str, set[str]] = {}
        self.clients: dict[str, dict[str, dict]] = {}
        self.users: dict[str, dict[str, dict]] = {}
        self.user_groups: dict[str, set[str]] = {}
        self.passwords: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    def client(self) -> httpx.Client:
        return httpx.Client(base_url="http://keycloak.test", transport=httpx.MockTransport(self.handle))

    # -- routing -----------------------------------------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        self.calls.append((method, path))

        if path == "/realms/master/protocol/openid-connect/token":
            form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            if form.get("password") != self.admin_password:
                return httpx.Response(401, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "token"})
        if request.headers.get("authorization") != "Bearer token":
            return httpx.Response(401)

        body = json.loads(request.content) if request.content else None
        params = dict(request.url.params)

        if path == "/admin/realms" and method == "POST":
            self.realms[body["realm"]] = body
            for store in (self.roles, self.groups, self.clients, self.users):
                store[body["realm"]] = {}
            return httpx.Response(201)

        m = re.fullmatch(r"/admin/realms/([^/]+)", path)
        if m:
            realm = m.group(1)
            if realm not in self.realms:
                return httpx.Response(404)
            if method == "GET":
                return httpx.Response(200, json=self.realms[realm])
            if method == "PUT":
                self.realms[realm] = body
                return httpx.Response(204)

        m = re.fullmatch(r"/admin/realms/([^/]+)/roles(?:/([^/]+))?", path)
        if m:
            realm, name = m.groups()
            if name is None and method == "GET":
                return httpx.Response(200, json=list(self.roles[realm].values()))
            if name is None and method == "POST":
                self.roles[realm][body["name"]] = {"id": str(uuid.uuid4()), **body}
                return httpx.Response(201)
            if name and method == "GET":
                role = self.roles[realm].get(name)
                return httpx.Response(200, json=role) if role else httpx.Response(404)

        m = re.fullmatch(r"/admin/realms/([^/]+)/groups", path)
        if m:
            realm = m.group(1)
            if method == "GET":
                search = params.get("search")
                items = [g for g in self.groups[realm].values() if not search or search in g["name"]]
                return httpx.Response(200, json=items)
            if method == "POST":
                self.groups[realm][body["name"]] = {"id": str(uuid.uuid4()), "name": body["name"]}
                return httpx.Response(201)

        m = re.fullmatch(r"/admin/realms/([^/]+)/groups/([^/]+)/role-mappings/realm", path)
        if m:
            realm, group_id = m.groups()
            key = f"{realm}/{group_id}"
            if method == "GET":
                names = self.group_roles.get(key, set())
                return httpx.Response(200, json=[{"name": n} for n in sorted(names)])
            if method == "POST":
                self.group_roles.setdefault(key, set()).update(r["name"] for r in body)
                return httpx.Response(204)

        m = re.fullmatch(r"/admin/realms/([^/]+)/clients(?:/([^/]+))?", path)
        if m:
            realm, client_pk = m.groups()
            if client_pk is None and method == "GET":
                wanted = params.get("clientId")
                items = [c for c in self.clients[realm].values() if c["clientId"] == wanted]
                return httpx.Response(200, json=items)
            if client_pk is None and method == "POST":
                pk = str(uuid.uuid4())
                self.clients[realm][pk] = {"id": pk, **body}
                return httpx.Response(201)
            if client_pk and method == "PUT":
                self.clients[realm][client_pk] = {"id": client_pk, **body}
                return httpx.Response(204)

        m = re.fullmatch(r"/admin/realms/([^/]+)/users", path)
        if m:
            realm = m.group(1)
            if method == "GET":
                items = [u for u in self.users[realm].values() if u["username"] == params.get("username")]
                return httpx.Response(200, json=items)
            if method == "POST":
                uid = str(uuid.uuid4())
                self.users[realm][uid] = {"id": uid, **body}
                return httpx.Response(
                    201, headers={"Location": f"http://keycloak.test/admin/realms/{realm}/users/{uid}"}
                )

        m = re.fullmatch(r"/admin/realms/([^/]+)/users/([^/]+)/reset-password", path)
        if m and method == "PUT":
            self.passwords[m.group(2)] = body["value"]
            return httpx.Response(204)

        m = re.fullmatch(r"/admin/realms/([^/]+)/users/([^/]+)/groups(?:/([^/]+))?", path)
        if m:
            realm, uid, gid = m.groups()
            if gid is None and method == "GET":
                names = self.user_groups.get(uid, set())
                return httpx.Response(200, json=[{"name": n} for n in sorted(names)])
            if gid and method == "PUT":
                name = next(g["name"] for g in self.groups[realm].values() if g["id"] == gid)
                self.user_groups.setdefault(uid, set()).add(name)
                return httpx.Response(204)

        return httpx.Response(404, json={"unhandled": f"{method} {path}"})
