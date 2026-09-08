"""Test suite — stdlib unittest, no network, no third-party deps.

Run:  python3 -m unittest discover -s tests -v
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Base(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="aiquota_t_")
        os.environ["AIQUOTA_HOME"] = self.home
        # Keep tests hermetic: never pick up the developer's real credentials.
        os.environ["AIQUOTA_NO_AUTODISCOVER"] = "1"
        for k in ("ANTHROPIC_TOKEN", "AIQUOTA_CLAUDE_TOKEN",
                  "ANTHROPIC_API_KEY", "AIQUOTA_CODEX_TOKEN"):
            os.environ.pop(k, None)
        for m in [m for m in sys.modules if m.startswith("aiquota")]:
            del sys.modules[m]

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)
        os.environ.pop("AIQUOTA_HOME", None)
        os.environ.pop("AIQUOTA_NO_AUTODISCOVER", None)

    def run_cli(self, *args):
        from aiquota.cli import main
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()


class TestConfig(Base):
    def test_creates_config_with_secure_perms(self):
        from aiquota.core import config_path, load_config
        load_config()
        self.assertTrue(os.path.exists(config_path()))
        mode = os.stat(config_path()).st_mode & 0o777
        self.assertEqual(mode, 0o600, "config may hold tokens; must be 0600")

    def test_roundtrip(self):
        from aiquota.core import load_config, save_config
        c = load_config()
        c["services"]["x"] = {"adapter": "manual", "enabled": True}
        save_config(c)
        self.assertIn("x", load_config()["services"])


class TestAddRemove(Base):
    def test_add_then_remove(self):
        code, *_ = self.run_cli("add", "midjourney", "--adapter", "manual")
        self.assertEqual(code, 0)
        from aiquota.core import load_config
        self.assertIn("midjourney", load_config()["services"])

        code, out, _ = self.run_cli("remove", "midjourney", "-y")
        self.assertEqual(code, 0)
        self.assertIn("removed", out)
        # reload from disk, not cached module state
        for m in [m for m in sys.modules if m.startswith("aiquota")]:
            del sys.modules[m]
        from aiquota.core import load_config as lc2
        self.assertNotIn("midjourney", lc2()["services"])

    def test_remove_alias_rm(self):
        self.run_cli("add", "foo", "--adapter", "manual")
        code, *_ = self.run_cli("rm", "foo", "-y")
        self.assertEqual(code, 0)

    def test_remove_multiple(self):
        self.run_cli("add", "a", "--adapter", "manual")
        self.run_cli("add", "b", "--adapter", "manual")
        code, out, _ = self.run_cli("rm", "a", "b", "-y")
        self.assertEqual(code, 0)
        from aiquota.core import load_config
        svcs = load_config()["services"]
        self.assertNotIn("a", svcs)
        self.assertNotIn("b", svcs)

    def test_remove_unknown_fails(self):
        code, _, err = self.run_cli("rm", "ghost", "-y")
        self.assertEqual(code, 1)
        self.assertIn("not tracked", err)

    def test_remove_is_atomic_on_partial_miss(self):
        """If one name is bad, nothing should be removed."""
        self.run_cli("add", "keep", "--adapter", "manual")
        code, _, _ = self.run_cli("rm", "keep", "ghost", "-y")
        self.assertEqual(code, 1)
        from aiquota.core import load_config
        self.assertIn("keep", load_config()["services"])

    def test_add_duplicate_rejected_without_force(self):
        self.run_cli("add", "dup", "--adapter", "manual")
        code, _, err = self.run_cli("add", "dup", "--adapter", "manual")
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)

    def test_add_unknown_adapter_rejected(self):
        code, _, err = self.run_cli("add", "x", "--adapter", "nope")
        self.assertEqual(code, 1)
        self.assertIn("no adapter", err)

    def test_remove_purges_cache(self):
        from aiquota.core import _write_cache, _read_cache
        self.run_cli("add", "cached", "--adapter", "manual")
        _write_cache({"cached": {"at": 9e9, "result": {}}})
        self.run_cli("rm", "cached", "-y")
        self.assertNotIn("cached", _read_cache())


class TestEnableDisable(Base):
    def test_disable_hides_from_status(self):
        self.run_cli("add", "hf", "--adapter", "manual",
                     "--set", "credits=10", "--set", "credits_total=20")
        code, out, _ = self.run_cli("disable", "hf")
        self.assertEqual(code, 0)
        _, out, _ = self.run_cli("status", "--json")
        names = [s["name"] for s in json.loads(out)["services"]]
        self.assertNotIn("hf", names)

        self.run_cli("enable", "hf")
        _, out, _ = self.run_cli("status", "--json")
        self.assertIn("hf", [s["name"] for s in json.loads(out)["services"]])


class TestSet(Base):
    def test_set_coerces_types(self):
        self.run_cli("add", "hf", "--adapter", "manual")
        self.run_cli("set", "hf", "credits=555", "enabled=true", "note=hello")
        from aiquota.core import load_config
        s = load_config()["services"]["hf"]
        self.assertEqual(s["credits"], 555)
        self.assertIs(s["enabled"], True)
        self.assertEqual(s["note"], "hello")

    def test_set_redacts_secrets_in_output(self):
        self.run_cli("add", "c", "--adapter", "manual")
        _, out, _ = self.run_cli("set", "c", "token=supersecret123")
        self.assertNotIn("supersecret123", out)
        self.assertIn("***", out)

    def test_set_unknown_service_fails(self):
        code, _, err = self.run_cli("set", "ghost", "x=1")
        self.assertEqual(code, 1)


class TestManualAdapter(Base):
    def test_credits_percentage(self):
        self.run_cli("add", "hf", "--adapter", "manual", "--plan", "Creator",
                     "--set", "credits=555", "--set", "credits_total=1500")
        _, out, _ = self.run_cli("status", "hf", "--json")
        s = json.loads(out)["services"][0]
        self.assertEqual(s["tier"], "manual")
        self.assertAlmostEqual(s["windows"][0]["used_pct"], 63.0, places=1)

    def test_service_name_from_key_not_plan(self):
        """Card should read 'Higgsfield', not 'Creator'."""
        self.run_cli("add", "higgsfield", "--adapter", "manual",
                     "--plan", "Creator", "--set", "credits=1",
                     "--set", "credits_total=2")
        _, out, _ = self.run_cli("status", "higgsfield", "--json")
        s = json.loads(out)["services"][0]
        self.assertEqual(s["service"], "Higgsfield")
        self.assertEqual(s["plan"], "Creator")

    def test_used_limit_windows(self):
        self.run_cli("add", "mj", "--adapter", "manual",
                     "--set", "used=140", "--set", "limit=900")
        _, out, _ = self.run_cli("status", "mj", "--json")
        w = json.loads(out)["services"][0]["windows"][0]
        self.assertAlmostEqual(w["used_pct"], 15.6, places=1)

    def test_divide_by_zero_is_safe(self):
        self.run_cli("add", "z", "--adapter", "manual",
                     "--set", "credits=5", "--set", "credits_total=0")
        code, out, _ = self.run_cli("status", "z", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["services"][0]["windows"], [])

    def test_pct_clamped(self):
        self.run_cli("add", "over", "--adapter", "manual",
                     "--set", "used=999", "--set", "limit=10")
        _, out, _ = self.run_cli("status", "over", "--json")
        self.assertLessEqual(json.loads(out)["services"][0]["windows"][0]["used_pct"], 100.0)


class TestUnconfigured(Base):
    def test_missing_creds_is_unconfigured_not_crash(self):
        self.run_cli("add", "claude")
        code, out, _ = self.run_cli("status", "claude", "--json")
        self.assertEqual(code, 0)
        s = json.loads(out)["services"][0]
        self.assertIn(s["tier"], ("unconfigured", "error"))
        self.assertTrue(s.get("error") or s.get("note"))


class TestAdapterIsolation(Base):
    def test_broken_adapter_cannot_crash_run(self):
        d = os.path.join(self.home, "adapters")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "boom.py"), "w") as f:
            f.write("from aiquota.core import Adapter, register\n"
                    "@register\n"
                    "class Boom(Adapter):\n"
                    "    name='boom'\n"
                    "    service='Boom'\n"
                    "    def probe(self, conf):\n"
                    "        raise RuntimeError('kaboom')\n")
        self.run_cli("add", "boom", "--adapter", "boom")
        self.run_cli("add", "ok", "--adapter", "manual",
                     "--set", "credits=1", "--set", "credits_total=2")
        code, out, _ = self.run_cli("status", "--json")
        self.assertEqual(code, 0, "one bad adapter must not kill the run")
        svcs = {s["name"]: s for s in json.loads(out)["services"]}
        self.assertEqual(svcs["boom"]["tier"], "error")
        self.assertIn("kaboom", svcs["boom"]["error"])
        self.assertEqual(svcs["ok"]["tier"], "manual")

    def test_user_adapter_is_discovered(self):
        d = os.path.join(self.home, "adapters")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "custom.py"), "w") as f:
            f.write("from aiquota.core import Adapter, Result, Window, register, LIVE\n"
                    "@register\n"
                    "class Custom(Adapter):\n"
                    "    name='custom'\n"
                    "    service='Custom'\n"
                    "    summary='test'\n"
                    "    def probe(self, conf):\n"
                    "        return Result(name='custom', service='Custom', tier=LIVE,\n"
                    "                      windows=[Window(label='W', used_pct=42.0)])\n")
        code, out, _ = self.run_cli("adapters", "--json")
        self.assertIn("custom", json.loads(out))
        self.run_cli("add", "custom")
        _, out, _ = self.run_cli("status", "custom", "--json")
        s = json.loads(out)["services"][0]
        self.assertEqual(s["tier"], "live")
        self.assertEqual(s["windows"][0]["used_pct"], 42.0)


class TestCache(Base):
    def test_ttl_zero_forces_refresh(self):
        self.run_cli("add", "hf", "--adapter", "manual",
                     "--set", "credits=1", "--set", "credits_total=2")
        _, out, _ = self.run_cli("status", "--json", "--ttl", "0")
        self.assertFalse(json.loads(out)["any_cached"])

    def test_manual_results_not_cached(self):
        """Manual values change by hand; caching them would show stale data."""
        self.run_cli("add", "hf", "--adapter", "manual",
                     "--set", "credits=100", "--set", "credits_total=200")
        self.run_cli("status", "--json")
        self.run_cli("set", "hf", "credits=50")
        _, out, _ = self.run_cli("status", "hf", "--json")
        s = json.loads(out)["services"][0]
        self.assertAlmostEqual(s["windows"][0]["used_pct"], 75.0, places=1)


class TestCLIShape(Base):
    def test_bare_invocation_is_status(self):
        code, out, _ = self.run_cli()
        self.assertEqual(code, 0)

    def test_global_flag_before_subcommand(self):
        code, _, _ = self.run_cli("--color", "never", "list")
        self.assertEqual(code, 0)

    def test_bare_with_global_flag_is_status(self):
        code, out, _ = self.run_cli("--color", "never")
        self.assertEqual(code, 0)
        self.assertNotIn("positional arguments", out)

    def test_compact_output_is_one_line(self):
        self.run_cli("add", "hf", "--adapter", "manual",
                     "--set", "credits=1", "--set", "credits_total=4")
        _, out, _ = self.run_cli("status", "--compact")
        self.assertEqual(len(out.strip().splitlines()), 1)

    def test_exit_code_threshold(self):
        self.run_cli("add", "hot", "--adapter", "manual",
                     "--set", "used=95", "--set", "limit=100")
        code, *_ = self.run_cli("status", "--exit-code", "--threshold", "80")
        self.assertEqual(code, 2)
        code, *_ = self.run_cli("status", "--exit-code", "--threshold", "99")
        self.assertEqual(code, 0)


class TestCredentialConsent(Base):
    """Reading another application's credential file must be opt-in.

    Regression test for a real incident: the ChatGPT adapter silently found
    ~/.codex/auth.json and sent that token to a remote endpoint without the
    user ever configuring the service.
    """

    def setUp(self):
        super().setUp()
        # Simulate another app's login sitting on the machine.
        self.fake_codex = os.path.join(self.home, "codex_auth.json")
        with open(self.fake_codex, "w") as f:
            json.dump({"tokens": {"access_token": "tok", "account_id": "acct"}}, f)
        os.environ.pop("AIQUOTA_NO_AUTODISCOVER", None)

    def test_does_not_borrow_credentials_by_default(self):
        self.run_cli("add", "chatgpt")
        self.run_cli("set", "chatgpt", f'auth_files=["{self.fake_codex}"]')
        code, out, _ = self.run_cli("status", "chatgpt", "--json")
        self.assertEqual(code, 0)
        s = json.loads(out)["services"][0]
        self.assertEqual(s["tier"], "unconfigured",
                         "must NOT use another app's token without opt-in")
        self.assertIn("opt-in", (s.get("note") or "").lower())

    def test_opt_in_enables_discovery(self):
        self.run_cli("add", "chatgpt")
        self.run_cli("set", "chatgpt", f'auth_files=["{self.fake_codex}"]',
                     "autodiscover=true")
        from aiquota.adapters.chatgpt import _auth
        tok, acct, source = _auth({"auth_files": [self.fake_codex],
                                   "autodiscover": True})
        self.assertEqual(tok, "tok")
        self.assertIn("borrowed", source)

    def test_claude_does_not_borrow_by_default(self):
        from aiquota.adapters.claude import _token
        self.assertIsNone(_token({}), "must not scan credential files by default")

    def test_env_var_still_works_without_optin(self):
        os.environ["AIQUOTA_CODEX_TOKEN"] = "explicit"
        try:
            from aiquota.adapters.chatgpt import _auth
            tok, _, source = _auth({})
            self.assertEqual(tok, "explicit")
            self.assertEqual(source, "env")
        finally:
            os.environ.pop("AIQUOTA_CODEX_TOKEN", None)


class TestHTML(Base):
    def test_html_escapes_and_writes(self):
        from aiquota.render import render_html
        d = {"generated_at": 0, "services": [{
            "name": "x", "service": "<script>alert(1)</script>", "plan": "",
            "tier": "manual", "windows": [], "note": "", "error": None,
            "extra": {}}]}
        h = render_html(d)
        self.assertNotIn("<script>alert", h)
        self.assertIn("&lt;script&gt;", h)

    def test_write_html_file(self):
        self.run_cli("add", "hf", "--adapter", "manual",
                     "--set", "credits=1", "--set", "credits_total=2")
        p = os.path.join(self.home, "w.html")
        code, *_ = self.run_cli("status", "--html", p)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(p))
        with open(p) as f:
            self.assertIn("<!doctype html>", f.read().lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
