from aurai_workspace.cli import main


def test_validate_ok(realm_file, capsys):
    assert main(["validate", str(realm_file)]) == 0
    assert "ok (3 roles, 8 groups, 8 users)" in capsys.readouterr().out


def test_validate_reports_problems(tmp_path, realm_file, capsys):
    broken = tmp_path / "realm.yaml"
    broken.write_text(realm_file.read_text().replace("roles: [member, builder]", "roles: [member, ghost]"))
    assert main(["validate", str(broken)]) == 1
    assert "unknown role ghost" in capsys.readouterr().err


def test_plan_requires_admin_credentials(realm_file, monkeypatch, capsys):
    monkeypatch.delenv("KEYCLOAK_ADMIN_USER", raising=False)
    monkeypatch.delenv("KEYCLOAK_ADMIN_PASSWORD", raising=False)
    assert main(["plan", str(realm_file), "--base-url", "http://keycloak.test"]) == 1
    assert "KEYCLOAK_ADMIN_USER" in capsys.readouterr().err
