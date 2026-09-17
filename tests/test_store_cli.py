"""Unit tests for `impactos store` login, provisioning and access wrappers.

These exercise the CLI logic without a network or a live Supabase project: HTTP
is stubbed, so the tests prove request construction, the refresh-on-401 retry,
the provisioning gate and secret-smuggling refusals, and the explicit
access-denied mapping — the halves that do not need a running cluster. Live
sign-in and live provisioning are proven separately (see docs/store.md).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cli.impactos_agent import store


def _make_project(with_route: bool = False, with_migrations: bool = False) -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "workspace").mkdir()
    if with_route:
        (root / "operating-notes").mkdir()
        (root / "operating-notes" / "routes.md").write_text(
            "# Routes\n\nstore_route: enabled\n", encoding="utf-8")
    if with_migrations:
        (root / "store" / "migrations").mkdir(parents=True)
        (root / "store" / "migrations" / "0001_x.sql").write_text("select 1;", encoding="utf-8")
    return root


class ProvisionGateTest(unittest.TestCase):
    def test_refuses_without_a_recorded_route(self):
        root = _make_project(with_route=False)
        args = mock.Mock(project_ref="ref123", api_url=None)
        result = store.provision(root, args, argv=[], environ={})
        self.assertEqual(result.verdict, "fail")
        self.assertIn("no store route choice recorded", result.errors[0])

    def test_refuses_a_secret_on_argv(self):
        root = _make_project(with_route=True)
        args = mock.Mock(project_ref="ref123", api_url=None)
        result = store.provision(
            root, args, argv=["store", "provision", "--service-role-key", "sk"], environ={})
        self.assertEqual(result.verdict, "fail")
        self.assertIn("command line", result.errors[0])

    def test_refuses_a_secret_in_the_environment(self):
        root = _make_project(with_route=True)
        args = mock.Mock(project_ref="ref123", api_url=None)
        result = store.provision(
            root, args, argv=[], environ={"SUPABASE_DB_PASSWORD": "hunter2"})
        self.assertEqual(result.verdict, "fail")
        self.assertIn("environment", result.errors[0])

    def test_refuses_without_a_keychain_token(self):
        root = _make_project(with_route=True, with_migrations=True)
        args = mock.Mock(project_ref="ref123", api_url=None)
        with mock.patch.object(store, "_read_personal_access_token", return_value=None):
            result = store.provision(root, args, argv=[], environ={})
        self.assertEqual(result.verdict, "fail")
        self.assertIn("personal access token", result.errors[0])

    def test_applies_migrations_without_any_secret(self):
        root = _make_project(with_route=True, with_migrations=True)
        args = mock.Mock(project_ref="ref123", api_url=None)
        with mock.patch.object(store, "_read_personal_access_token", return_value="pat"), \
             mock.patch.object(store, "_management_query", return_value=(201, b"[]")) as mq, \
             mock.patch.object(store, "_fetch_publishable_key", return_value="pub_key"):
            result = store.provision(root, args, argv=[], environ={})
        self.assertEqual(result.verdict, "pass", result.errors)
        self.assertEqual(result.data["applied"], ["0001_x.sql"])
        self.assertFalse(result.data["service_role_used"])
        self.assertFalse(result.data["db_password_used"])
        mq.assert_called_once()
        # config recorded the publishable key, never a secret
        config = json.loads((root / "workspace" / "config.json").read_text())
        self.assertEqual(config["store"]["project_ref"], "ref123")
        self.assertEqual(config["store"]["publishable_key"], "pub_key")
        self.assertNotIn("service_role_key", json.dumps(config))


class SecretGuardTest(unittest.TestCase):
    def test_argv_secret_detection(self):
        self.assertIsNotNone(store._argv_secret(["--db-password=abc"]))
        self.assertIsNotNone(store._argv_secret(["--service_role_key", "x"]))
        self.assertIsNone(store._argv_secret(["--project-ref", "abc"]))

    def test_env_secret_detection(self):
        self.assertEqual(store._env_secret({"PGPASSWORD": "x"}), "PGPASSWORD")
        self.assertIsNone(store._env_secret({"HOME": "/x"}))


class LoginTest(unittest.TestCase):
    def _seed_config(self, root):
        (root / "workspace" / "config.json").write_text(json.dumps(
            {"store": {"api_url": "https://x.supabase.co", "publishable_key": "pub"}}),
            encoding="utf-8")

    def test_password_grant_stores_session_and_prints_role(self):
        root = _make_project()
        self._seed_config(root)
        args = mock.Mock(email="staff@example.org", password="pw", token=None,
                         otp_request=False, api_url=None, publishable_key=None)

        def fake_http(method, url, headers, body=None):
            if "grant_type=password" in url:
                return 200, json.dumps({
                    "access_token": "at", "refresh_token": "rt",
                    "user": {"id": "u1", "email": "staff@example.org"}}).encode()
            if "/rest/v1/user_role" in url:
                return 200, json.dumps([{"app_role": {"name": "staff"}}]).encode()
            raise AssertionError(f"unexpected {url}")

        with mock.patch.object(store, "_http", side_effect=fake_http):
            result = store.login(root, args)
        self.assertEqual(result.verdict, "pass", result.errors)
        self.assertEqual(result.data["roles"], ["staff"])
        self.assertFalse(result.data["service_role_used"])
        config = json.loads((root / "workspace" / "config.json").read_text())
        self.assertEqual(config["store"]["session"]["access_token"], "at")

    def test_refresh_on_401_retries_once(self):
        root = _make_project()
        (root / "workspace" / "config.json").write_text(json.dumps({"store": {
            "api_url": "https://x.supabase.co", "publishable_key": "pub",
            "session": {"access_token": "old", "refresh_token": "rt"}}}), encoding="utf-8")
        calls = {"rest": 0}

        def fake_http(method, url, headers, body=None):
            if "grant_type=refresh_token" in url:
                return 200, json.dumps({"access_token": "new", "refresh_token": "rt2"}).encode()
            if "/rest/v1/thing" in url:
                calls["rest"] += 1
                if calls["rest"] == 1:
                    return 401, b"{}"
                return 200, b"[]"
            raise AssertionError(url)

        with mock.patch.object(store, "_http", side_effect=fake_http):
            status, _ = store.authed_request(root, "GET", "/rest/v1/thing")
        self.assertEqual(status, 200)
        self.assertEqual(calls["rest"], 2)
        config = json.loads((root / "workspace" / "config.json").read_text())
        self.assertEqual(config["store"]["session"]["access_token"], "new")


class AccessTest(unittest.TestCase):
    def _seed(self, root):
        (root / "workspace" / "config.json").write_text(json.dumps({"store": {
            "api_url": "https://x.supabase.co", "publishable_key": "pub",
            "session": {"access_token": "at", "refresh_token": "rt"}}}), encoding="utf-8")

    def test_access_check_unknown_company_is_distinct(self):
        root = _make_project()
        self._seed(root)
        args = mock.Mock(company="not-a-uuid")
        result = store.access_check(root, args)
        self.assertEqual(result.verdict, "fail")
        self.assertIn("unknown company", result.errors[0])

    def test_access_check_denied_vs_granted(self):
        root = _make_project()
        self._seed(root)
        good = mock.Mock(company="2a2a2a2a-0000-4000-8000-0000000000aa")
        with mock.patch.object(store, "_http", return_value=(200, b"true")):
            granted = store.access_check(root, good)
        self.assertEqual(granted.verdict, "pass")
        with mock.patch.object(store, "_http", return_value=(200, b"false")):
            denied = store.access_check(root, good)
        self.assertEqual(denied.verdict, "fail")
        self.assertIn("access denied", denied.errors[0])

    def test_access_end_requires_a_valid_user_uuid(self):
        root = _make_project()
        self._seed(root)
        args = mock.Mock(user="nope", role="helper", at=None)
        result = store.access_end(root, args)
        self.assertEqual(result.verdict, "fail")
        self.assertIn("valid --user", result.errors[0])


if __name__ == "__main__":
    unittest.main()
