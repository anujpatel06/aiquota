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
from unittest import mock
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


class TestLink(Base):
    """`link` is the consent gate: it must never link without an explicit yes."""

    def setUp(self):
        super().setUp()
        self.fake = os.path.join(self.home, "codex_auth.json")
        with open(self.fake, "w") as f:
            json.dump({"auth_mode": "chatgpt",
                       "tokens": {"access_token": "tok", "account_id": "acct1234"}}, f)

    def _link(self, stdin_text, *args):
        """Run cmd_link with piped stdin."""
        from aiquota.cli import main
        import io
        from contextlib import redirect_stdout, redirect_stderr
        old = sys.stdin
        sys.stdin = io.StringIO(stdin_text)
        out, err = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = main(["link", *args])
        finally:
            sys.stdin = old
        return code, out.getvalue(), err.getvalue()

    def test_list_only_changes_nothing(self):
        from aiquota.core import load_config
        before = json.dumps(load_config(), sort_keys=True)
        code, out, _ = self._link("", "--list")
        self.assertEqual(code, 0)
        for m in [m for m in sys.modules if m.startswith("aiquota")]:
            del sys.modules[m]
        from aiquota.core import load_config as lc
        self.assertEqual(before, json.dumps(lc(), sort_keys=True))

    def test_empty_input_cancels(self):
        code, out, _ = self._link("\n")
        self.assertEqual(code, 0)
        self.assertIn("cancel", out.lower())

    def test_declining_links_nothing(self):
        code, out, _ = self._link("1\nn\n")
        self.assertEqual(code, 0)
        self.assertIn("cancel", out.lower())
        from aiquota.core import load_config
        for s in load_config().get("services", {}).values():
            self.assertNotIn("autodiscover", s)
            self.assertNotIn("token_files", s)

    def test_manual_option_always_offered(self):
        """A platform not in the catalog must still be addable."""
        _, out, _ = self._link("", "--list")
        self.assertIn("something else", out.lower())

    def test_unlink_clears_credentials_but_keeps_service(self):
        from aiquota.core import load_config, save_config
        cfg = load_config()
        cfg["services"]["chatgpt"] = {"adapter": "chatgpt", "enabled": True,
                                      "autodiscover": True}
        save_config(cfg)
        code, out, _ = self.run_cli("unlink", "chatgpt")
        self.assertEqual(code, 0)
        for m in [m for m in sys.modules if m.startswith("aiquota")]:
            del sys.modules[m]
        from aiquota.core import load_config as lc
        svc = lc()["services"]["chatgpt"]
        self.assertNotIn("autodiscover", svc)
        self.assertIn("chatgpt", lc()["services"], "service should remain tracked")

    def test_unlink_unknown_fails(self):
        code, _, err = self.run_cli("unlink", "ghost")
        self.assertEqual(code, 1)

    def test_detect_does_not_return_secrets(self):
        """detect() output is printed to the screen — it must not leak tokens."""
        from aiquota.core import load_adapters, registry
        load_adapters()
        for name, ad in registry().items():
            for f in (ad.detect() or []):
                blob = json.dumps(f)
                self.assertNotIn("sk-ant-", blob)
                self.assertNotIn("eyJhbGci", blob)


class TestCatalog(Base):
    """The catalog is the browse-and-add surface. It must stay honest."""

    def test_catalog_entries_wellformed(self):
        from aiquota.catalog import CATALOG
        keys = set()
        for e in CATALOG:
            for field in ("key", "name", "adapter", "support", "note", "login"):
                self.assertIn(field, e, f"{e.get('name')} missing {field}")
            self.assertIn(e["support"], ("live", "manual", "soon"))
            self.assertNotIn(e["key"], keys, "duplicate catalog key")
            keys.add(e["key"])

    def test_live_entries_have_a_real_adapter(self):
        """A 'live' badge is a promise — it needs an adapter that can fetch."""
        from aiquota.catalog import CATALOG
        from aiquota.core import load_adapters, registry
        load_adapters()
        reg = registry()
        for e in CATALOG:
            if e["support"] == "live":
                self.assertIn(e["adapter"], reg,
                              f"{e['name']} claims live but has no adapter")

    def test_non_live_entries_use_manual_adapter(self):
        """Anything we can't fetch must render as manual, never as live."""
        from aiquota.catalog import CATALOG
        for e in CATALOG:
            if e["support"] != "live":
                self.assertEqual(e["adapter"], "manual",
                                 f"{e['name']} must be manual until fetchable")

    def test_link_list_shows_whole_catalog(self):
        from aiquota.catalog import CATALOG
        from aiquota.cli import main
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            main(["link", "--list", "--color", "never"])
        text = out.getvalue()
        for e in CATALOG:
            self.assertIn(e["name"], text, f"{e['name']} missing from picker")

    def test_link_filter_by_name(self):
        from aiquota.cli import main
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            main(["link", "higgsfield", "--list", "--color", "never"])
        text = out.getvalue()
        self.assertIn("Higgsfield", text)
        self.assertNotIn("Midjourney", text)

    def test_manual_add_stores_only_user_values(self):
        """Skipping every field must NOT invent numbers."""
        from aiquota.cli import main
        import io
        from contextlib import redirect_stdout
        from aiquota.catalog import sorted_catalog
        # Pick a genuinely manual platform by name rather than by menu
        # position — positions shift whenever a platform gains an adapter.
        entries = sorted_catalog()
        idx = next(i for i, e in enumerate(entries, start=1)
                   if e["adapter"] == "manual")
        old = sys.stdin
        sys.stdin = io.StringIO(f"{idx}\n\n\n\n\n")   # pick it, skip all fields
        try:
            with redirect_stdout(io.StringIO()):
                main(["link", "--color", "never"])
        finally:
            sys.stdin = old
        from aiquota.core import load_config
        svcs = load_config()["services"]
        added = [v for k, v in svcs.items() if v.get("adapter") == "manual"]
        self.assertTrue(added, "should have added something")
        for v in added:
            self.assertIsNone(v.get("credits"))
            self.assertIsNone(v.get("credits_total"))


class TestApiKeyAdapters(Base):
    """ElevenLabs/OpenRouter use official APIs — a key is the whole login."""

    def test_unconfigured_without_key(self):
        for name in ("elevenlabs", "openrouter"):
            self.run_cli("add", name)
            code, out, _ = self.run_cli("status", name, "--json")
            self.assertEqual(code, 0)
            s = json.loads(out)["services"][0]
            self.assertEqual(s["tier"], "unconfigured")
            self.assertIn("API key", s.get("note", "") + (s.get("error") or ""))

    def test_adapters_expose_api_key_metadata(self):
        """The picker keys off api_key_label to show the paste-a-key flow."""
        from aiquota.core import load_adapters, registry
        load_adapters()
        reg = registry()
        for name in ("elevenlabs", "openrouter"):
            ad = reg[name]
            self.assertTrue(getattr(ad, "api_key_label", None))
            self.assertTrue(getattr(ad, "api_key_help", None))

    def test_elevenlabs_parses_documented_shape(self):
        from aiquota.adapters import elevenlabs as el
        payload = {"tier": "starter", "character_count": 2500,
                   "character_limit": 10000, "status": "active",
                   "next_character_count_reset_unix": 1790000000}
        orig = el.get_json
        el.get_json = lambda *a, **k: (200, payload)
        try:
            r = el.ElevenLabsAdapter().probe({"api_key": "x"})
        finally:
            el.get_json = orig
        self.assertEqual(r.tier, "live")
        self.assertAlmostEqual(r.windows[0].used_pct, 25.0, places=1)
        self.assertEqual(r.extra["remaining"], 7500)

    def test_openrouter_no_limit_does_not_fake_a_percentage(self):
        """limit=null means no cap — inventing a denominator would be a lie."""
        from aiquota.adapters import openrouter as orr
        payload = {"data": {"usage": 12.5, "limit": None,
                            "limit_remaining": None, "label": "k"}}
        orig = orr.get_json
        orr.get_json = lambda *a, **k: (200, payload)
        try:
            r = orr.OpenRouterAdapter().probe({"api_key": "x"})
        finally:
            orr.get_json = orig
        self.assertEqual(r.tier, "live")
        self.assertEqual(r.windows, [], "must not invent a percentage")
        self.assertIn("12.5", r.extra["spent"])

    def test_bad_key_reports_clearly(self):
        from aiquota.adapters import elevenlabs as el
        orig = el.get_json
        el.get_json = lambda *a, **k: (401, None)
        try:
            r = el.ElevenLabsAdapter().probe({"api_key": "bad"})
        finally:
            el.get_json = orig
        self.assertEqual(r.tier, "error")
        self.assertIn("invalid", r.error.lower())


class TestPickerForm(Base):
    def test_ask_form_maps_fields_and_skips_blanks(self):
        from aiquota import picker
        orig = picker.ask
        picker.ask = lambda *a, **k: "Pro, 500, , 2026-10-01"
        try:
            vals = picker.ask_form("t", "p", [
                ("plan", "plan"), ("credits", "remaining"),
                ("credits_total", "total"), ("renews_on", "renews")])
        finally:
            picker.ask = orig
        self.assertEqual(vals["plan"], "Pro")
        self.assertEqual(vals["credits"], "500")
        self.assertNotIn("credits_total", vals, "blank must be skipped")
        self.assertEqual(vals["renews_on"], "2026-10-01")

    def test_cancel_returns_none(self):
        from aiquota import picker
        orig = picker.ask
        picker.ask = lambda *a, **k: None
        try:
            self.assertIsNone(picker.ask_form("t", "p", [("a", "a")]))
        finally:
            picker.ask = orig

    def test_dialog_error_is_not_treated_as_cancel(self):
        """A permissions failure must never look like the user clicking Cancel."""
        from aiquota import picker
        import subprocess as sp

        class FakeProc:
            returncode = 1
            stdout = ""
            stderr = "execution error: Not authorized to send Apple events (-1743)"

        orig = sp.run
        sp.run = lambda *a, **k: FakeProc()
        try:
            with self.assertRaises(picker.DialogError):
                picker.osa('display dialog "x"')
        finally:
            sp.run = orig


class TestIsLinked(Base):
    """'added' must mean a credential exists — not merely a config entry.

    Regression: the default config ships claude/chatgpt entries, so the picker
    showed ChatGPT as 'added' when nothing had ever been linked.
    """

    def test_bare_config_entry_is_not_linked(self):
        from aiquota.core import is_linked
        self.assertFalse(is_linked({"adapter": "chatgpt", "enabled": True}))
        self.assertFalse(is_linked({"adapter": "chatgpt", "enabled": True,
                                    "plan": "ChatGPT"}))

    def test_credentials_count_as_linked(self):
        from aiquota.core import is_linked
        for conf in (
            {"adapter": "claude", "token_files": ["~/.hermes/.env::X"]},
            {"adapter": "chatgpt", "autodiscover": True},
            {"adapter": "openrouter", "api_key": "sk-x"},
            {"adapter": "copilot", "token": "gho_x"},
        ):
            self.assertTrue(is_linked(conf), conf)

    def test_empty_manual_is_not_linked(self):
        from aiquota.core import is_linked
        self.assertFalse(is_linked({"adapter": "manual", "service": "Suno"}))

    def test_filled_manual_is_linked(self):
        from aiquota.core import is_linked
        self.assertTrue(is_linked({"adapter": "manual", "credits": 500}))
        self.assertTrue(is_linked({"adapter": "manual",
                                   "renews_on": "2026-10-01"}))

    def test_linked_services_matches_reality(self):
        from aiquota.core import linked_services, save_config, load_config
        cfg = load_config()
        cfg["services"] = {
            "claude": {"adapter": "claude", "token_files": ["x"]},
            "chatgpt": {"adapter": "chatgpt", "plan": "ChatGPT"},
            "suno": {"adapter": "manual", "service": "Suno"},
            "runway": {"adapter": "manual", "credits": 100},
        }
        save_config(cfg)
        self.assertEqual(linked_services(), {"claude", "runway"})

    def test_picker_added_flag_uses_linked(self):
        """The picker's 'added' pill must not appear for unlinked services."""
        from aiquota.core import save_config, load_config, linked_services
        cfg = load_config()
        cfg["services"] = {"chatgpt": {"adapter": "chatgpt", "plan": "ChatGPT"}}
        save_config(cfg)
        self.assertNotIn("chatgpt", linked_services())


class TestLoginPolicy(Base):
    """Authentication method is a per-provider POLICY, not a UI preference.

    Anthropic restricts OAuth to its own applications and banned third-party
    tools' users in April 2026. A browser sign-in for Claude would put real
    accounts at risk, so it must stay structurally impossible rather than
    depending on someone remembering.
    """

    def test_claude_must_not_offer_browser_login(self):
        from aiquota.login_policy import may_browser_login, policy_for
        self.assertFalse(may_browser_login("claude"))
        policy, why, source = policy_for("claude")
        self.assertEqual(policy, "own-credential")
        self.assertTrue(why, "a refusal must explain itself")
        self.assertIn("claude.com", source)

    def test_openrouter_may_browser_login(self):
        """OpenRouter documents a PKCE flow for third-party apps."""
        from aiquota.login_policy import may_browser_login
        self.assertTrue(may_browser_login("openrouter"))

    def test_unknown_platforms_default_to_manual(self):
        from aiquota.login_policy import policy_for, may_browser_login
        self.assertEqual(policy_for("some-new-service")[0], "manual")
        self.assertFalse(may_browser_login("some-new-service"))

    def test_every_policy_entry_cites_a_source(self):
        from aiquota.login_policy import LOGIN_POLICY
        for key, (policy, why, source) in LOGIN_POLICY.items():
            self.assertIn(policy, ("browser", "own-credential", "manual"), key)
            self.assertTrue(why.strip(), f"{key} has no rationale")
            self.assertTrue(source.startswith("http"), f"{key} has no source")

    def test_browser_login_captures_nothing_by_default(self):
        """The module must not read credentials merely on import."""
        from aiquota import browser_login
        self.assertTrue(hasattr(browser_login, "login_and_capture"))
        # No global state that could hold a session.
        for attr in ("SESSION", "COOKIES", "TOKEN"):
            self.assertFalse(hasattr(browser_login, attr))


class TestClaudeProbeOrder(Base):
    """Reading usage must not require an inference call.

    Anthropic's Jan 2026 enforcement rejects subscription tokens used for
    "other API requests" outside Claude Code. The /v1/messages header route
    is exactly that traffic, and it also spends quota to measure quota, so
    the read-only usage endpoint has to be tried first.
    """

    def _adapter(self):
        from aiquota.core import load_adapters, registry
        load_adapters()
        return registry()["claude"]

    def test_usage_endpoint_is_tried_before_inference(self):
        ad = self._adapter()
        calls = []

        def fake_usage(_self, conf, tok):
            calls.append("usage")
            from aiquota.core import LIVE, Window
            r = ad.make(conf, tier=LIVE)
            r.windows.append(Window(key="five_hour", label="5-hour session",
                                    used_pct=12.0, resets_at=""))
            return r

        def fake_headers(_self, conf, tok):
            calls.append("inference")
            return ad.make(conf, tier="error")

        with mock.patch.object(type(ad), "_via_oauth_usage", fake_usage), \
             mock.patch.object(type(ad), "_via_headers", fake_headers):
            r = ad.probe({"token": "x", "_key": "claude"})

        self.assertEqual(calls, ["usage"],
                         "must not make an inference call when usage works")
        self.assertEqual(r.tier, "live")

    def test_falls_back_when_token_lacks_scope(self):
        """setup-token credentials are inference-only; fallback must remain."""
        ad = self._adapter()
        calls = []

        def fake_usage(_self, conf, tok):
            calls.append("usage")
            r = ad.make(conf, tier="error")
            r.error = "token lacks user:profile scope"
            return r

        def fake_headers(_self, conf, tok):
            calls.append("inference")
            from aiquota.core import LIVE
            return ad.make(conf, tier=LIVE)

        with mock.patch.object(type(ad), "_via_oauth_usage", fake_usage), \
             mock.patch.object(type(ad), "_via_headers", fake_headers):
            ad.probe({"token": "x", "_key": "claude"})
        self.assertEqual(calls, ["usage", "inference"])

    def test_usage_endpoint_only_never_falls_back(self):
        ad = self._adapter()
        calls = []
        with mock.patch.object(type(ad), "_via_oauth_usage",
                               lambda s, c, t: (calls.append("usage"),
                                                ad.make(c, tier="error"))[1]), \
             mock.patch.object(type(ad), "_via_headers",
                               lambda s, c, t: (calls.append("inference"),
                                                ad.make(c, tier="live"))[1]):
            ad.probe({"token": "x", "usage_endpoint_only": True,
                      "_key": "claude"})
        self.assertEqual(calls, ["usage"])

    def test_null_buckets_do_not_crash(self):
        """Every window in the response may be null."""
        ad = self._adapter()
        body = {"five_hour": {"utilization": 35.0, "resets_at": None},
                "seven_day": None, "seven_day_opus": None,
                "extra_usage": {"used_credits": 250.0, "currency": "EUR"}}
        with mock.patch("aiquota.adapters.claude.get_json",
                        return_value=(200, body)):
            r = ad._via_oauth_usage({"_key": "claude"}, "tok")
        self.assertEqual(r.tier, "live")
        self.assertEqual(len(r.windows), 1)
        self.assertEqual(r.windows[0].used_pct, 35.0)
        self.assertEqual(r.windows[0].resets_at, "")
        self.assertEqual(r.extra["extra_usage_spend"], 2.50)  # cents


class TestChatGPTAccountId(Base):
    def test_account_id_recovered_from_jwt(self):
        """auth.json often has account_id: null; the claim is in the JWT."""
        import base64 as b64
        from aiquota.adapters.chatgpt import _account_from_jwt
        payload = {"https://api.openai.com/auth":
                   {"chatgpt_account_id": "acct-123"}}
        raw = b64.urlsafe_b64encode(
            json.dumps(payload).encode()).decode().rstrip("=")
        self.assertEqual(_account_from_jwt(f"hdr.{raw}.sig"), "acct-123")

    def test_malformed_jwt_returns_none(self):
        from aiquota.adapters.chatgpt import _account_from_jwt
        for bad in (None, "", "notajwt", "a.b", "a.!!!.c"):
            self.assertIsNone(_account_from_jwt(bad))


class TestSessionAdapters(Base):
    """Platforms whose quota is only visible to a signed-in dashboard.

    These were 'manual entry' purely because nobody had looked. Probing the
    dashboards' own endpoints unauthenticated returns 401 (route exists,
    wants a session), not 404 — so a sign-in the user performs themselves
    can read them.
    """

    def _ad(self, name):
        from aiquota.core import load_adapters, registry
        load_adapters()
        return registry()[name]

    def test_all_four_are_registered_and_offer_browser_login(self):
        from aiquota.login_policy import may_browser_login
        for n in ("cursor", "suno", "grok", "runway"):
            ad = self._ad(n)
            self.assertTrue(ad.browser_login["url"].startswith("https://"), n)
            self.assertTrue(ad.browser_login["want"], f"{n}: no cookie named")
            self.assertTrue(may_browser_login(n), f"{n} must offer sign-in")

    def test_unconfigured_without_a_session(self):
        for n in ("cursor", "suno", "grok", "runway"):
            r = self._ad(n).probe({"_key": n})
            self.assertEqual(r.tier, "unconfigured", n)

    def test_cursor_parses_documented_shape(self):
        ad = self._ad("cursor")
        body = {"gpt-4": {"numRequests": 125, "maxRequestUsage": 500},
                "startOfMonth": "2026-09-01T00:00:00Z"}
        with mock.patch("aiquota.adapters.session_based.get_json",
                        return_value=(200, body)):
            r = ad.probe({"_key": "cursor", "session": {"x": "y"}})
        self.assertEqual(r.tier, "live")
        self.assertEqual(r.windows[0].used_pct, 25.0)

    def test_suno_parses_credits(self):
        ad = self._ad("suno")
        body = {"total_credits_left": 250, "monthly_limit": 1000,
                "subscription_type": "Pro"}
        with mock.patch("aiquota.adapters.session_based.get_json",
                        return_value=(200, body)):
            r = ad.probe({"_key": "suno", "session": {"__session": "z"}})
        self.assertEqual(r.tier, "live")
        self.assertEqual(r.windows[0].used_pct, 75.0)
        self.assertEqual(r.plan, "Pro")

    def test_expired_session_says_so(self):
        ad = self._ad("cursor")
        with mock.patch("aiquota.adapters.session_based.get_json",
                        return_value=(401, {})):
            r = ad.probe({"_key": "cursor", "session": {"x": "y"}})
        self.assertEqual(r.tier, "error")
        self.assertIn("sign in again", r.error)

    def test_no_quota_fields_never_fabricates_a_number(self):
        ad = self._ad("suno")
        with mock.patch("aiquota.adapters.session_based.get_json",
                        return_value=(200, {"subscription_type": "Free"})):
            r = ad.probe({"_key": "suno", "session": {"__session": "z"}})
        self.assertEqual(r.windows, [])
        self.assertEqual(r.tier, "error")


class TestStaleEntries(Base):
    """A platform added before its adapter shipped must not stay manual.

    Cursor was added when the catalog still said manual; it then kept showing
    "no values entered yet" even after a live adapter existed.
    """

    def test_detects_manual_entry_with_a_live_adapter(self):
        from aiquota.core import stale_entries
        cfg = {"services": {"cursor": {"adapter": "manual", "note": "x"}}}
        self.assertEqual(stale_entries(cfg), {"cursor": "cursor"})

    def test_genuinely_manual_platforms_are_not_flagged(self):
        from aiquota.core import stale_entries
        cfg = {"services": {"higgsfield": {"adapter": "manual"}}}
        self.assertEqual(stale_entries(cfg), {})

    def test_live_entries_are_not_flagged(self):
        from aiquota.core import stale_entries
        cfg = {"services": {"claude": {"adapter": "claude", "token": "x"}}}
        self.assertEqual(stale_entries(cfg), {})

    def test_session_counts_as_linked(self):
        from aiquota.core import is_linked
        self.assertTrue(is_linked({"adapter": "cursor",
                                   "session": {"tok": "v"}}))
        self.assertFalse(is_linked({"adapter": "cursor", "session": {}}))


class TestPickerRouting(Base):
    """Choosing a sign-in platform must OPEN the login page.

    Regression: picking Cursor showed "No Cursor credential found on this
    Mac — set it up first, then open this again". That is a dead end when
    aiquota can perfectly well open the login page itself. The credential
    scan ran before the browser-login branch and returned early.
    """

    def test_browser_platform_goes_to_sign_in_not_a_dead_end(self):
        from aiquota import picker
        from aiquota.core import load_adapters, registry
        from aiquota.catalog import by_key
        load_adapters()
        called = {}

        def fake_login(cfg, key, e, ad):
            called["key"] = key
            return 0

        # confirm() must NOT be reached — that is the dead-end dialog.
        def boom(*a, **k):
            raise AssertionError("showed a dialog instead of signing in")

        with mock.patch.object(picker, "finish_browser_login", fake_login), \
             mock.patch.object(picker, "confirm", boom):
            picker._handle_choice({"services": {}}, registry(),
                                  by_key("cursor"))
        self.assertEqual(called.get("key"), "cursor")

    def test_policy_blocked_platform_does_not_open_a_login_window(self):
        """Claude must never reach the browser flow."""
        from aiquota import picker
        from aiquota.core import load_adapters, registry
        from aiquota.catalog import by_key
        load_adapters()

        def boom(*a, **k):
            raise AssertionError("opened a login window for Claude")

        with mock.patch.object(picker, "finish_browser_login", boom), \
             mock.patch.object(picker, "confirm", lambda *a, **k: False), \
             mock.patch.object(picker, "ask", lambda *a, **k: ""):
            picker._handle_choice({"services": {}}, registry(),
                                  by_key("claude"))

    def test_every_browser_platform_has_a_reachable_login_url(self):
        from aiquota.core import load_adapters, registry
        from aiquota.login_policy import LOGIN_POLICY
        load_adapters()
        reg = registry()
        for key, (policy, _why, _src) in LOGIN_POLICY.items():
            if policy != "browser":
                continue
            ad = reg.get(key)
            if ad is None:
                continue
            spec = getattr(ad, "browser_login", None)
            if spec is None:
                # OAuth-style platforms (OpenRouter) redirect via PKCE
                # instead of capturing a session cookie.
                self.assertTrue(getattr(ad, "oauth_login", None),
                                f"{key}: no way to sign in at all")
                continue
            self.assertTrue(spec["url"].startswith("https://"), key)
            self.assertTrue(spec["domains"], f"{key}: no cookie domain")


class TestRemoveUI(Base):
    """The × must actually remove, after asking.

    Regression: the widget built AppleScript inside a JS string inside a
    shell command. The click log proved the command ran but the quoting had
    collapsed — `display dialog Remove claude from aiquota?` with no quotes
    is not valid AppleScript, so osascript failed silently and nothing was
    ever removed.
    """

    def _cfg_with(self, *names):
        from aiquota.core import load_config, save_config
        cfg = load_config()
        cfg["services"] = {n: {"adapter": "manual", "service": n.title(),
                               "credits": 1} for n in names}
        save_config(cfg)
        return cfg

    def test_confirming_removes_the_service(self):
        from aiquota import remove_ui
        from aiquota.core import load_config
        self._cfg_with("claude", "chatgpt")
        with mock.patch.object(remove_ui, "confirm", return_value=True), \
             mock.patch.object(remove_ui, "notify"):
            rc = remove_ui.remove("claude")
        self.assertEqual(rc, 0)
        self.assertNotIn("claude", load_config()["services"])
        self.assertIn("chatgpt", load_config()["services"])

    def test_declining_keeps_the_service(self):
        from aiquota import remove_ui
        from aiquota.core import load_config
        self._cfg_with("claude")
        with mock.patch.object(remove_ui, "confirm", return_value=False), \
             mock.patch.object(remove_ui, "notify"):
            rc = remove_ui.remove("claude")
        self.assertEqual(rc, 0)
        self.assertIn("claude", load_config()["services"],
                      "declining must not delete anything")

    def test_unknown_service_reports_and_changes_nothing(self):
        from aiquota import remove_ui
        from aiquota.core import load_config
        self._cfg_with("claude")
        with mock.patch.object(remove_ui, "confirm") as c, \
             mock.patch.object(remove_ui, "notify"):
            rc = remove_ui.remove("nope")
        self.assertEqual(rc, 1)
        c.assert_not_called()
        self.assertIn("claude", load_config()["services"])

    def test_yes_flag_skips_the_dialog(self):
        from aiquota import remove_ui
        self._cfg_with("claude")
        with mock.patch.object(remove_ui, "confirm") as c, \
             mock.patch.object(remove_ui, "notify"):
            remove_ui.main(["claude", "--yes"])
        c.assert_not_called()

    def test_removal_refreshes_the_widget(self):
        """A removed card must not linger until the next 5-minute tick."""
        from aiquota import remove_ui
        self._cfg_with("claude")
        with mock.patch.object(remove_ui, "confirm", return_value=True), \
             mock.patch.object(remove_ui, "notify"), \
             mock.patch.object(remove_ui, "_refresh_widgets") as refresh:
            remove_ui.remove("claude")
        refresh.assert_called_once()

    def test_declining_does_not_refresh(self):
        from aiquota import remove_ui
        self._cfg_with("claude")
        with mock.patch.object(remove_ui, "confirm", return_value=False), \
             mock.patch.object(remove_ui, "notify"), \
             mock.patch.object(remove_ui, "_refresh_widgets") as refresh:
            remove_ui.remove("claude")
        refresh.assert_not_called()

    def test_linking_does_not_ask_for_a_plan_label(self):
        """The provider reports the plan; don't make the user type one.

        Regression: after confirming a link, the picker asked "Plan label
        for Claude? (optional)" — busywork whose answer was worse than what
        the adapter already reads from the API.
        """
        from aiquota import picker
        from aiquota.core import load_adapters, registry
        from aiquota.catalog import by_key
        load_adapters()

        fake = [{"source": "~/.x", "detail": "a token",
                 "config": {"token_files": ["~/.x"]}}]
        cfg = {"services": {}}

        def boom(*a, **k):
            raise AssertionError("asked the user to type something")

        with mock.patch.object(picker, "ask", boom), \
             mock.patch.object(picker, "confirm", return_value=True), \
             mock.patch.object(picker, "notify"), \
             mock.patch.object(picker, "save_config"), \
             mock.patch.object(type(registry()["claude"]), "detect",
                               return_value=fake):
            rc = picker._handle_choice(cfg, registry(), by_key("claude"))
        self.assertEqual(rc, 0)
        self.assertIn("claude", cfg["services"])

    def test_multiple_credentials_let_the_user_choose(self):
        """Two accounts on one Mac must not be resolved by picking [0]."""
        from aiquota import picker
        from aiquota.core import load_adapters, registry
        from aiquota.catalog import by_key
        load_adapters()

        fake = [{"source": "~/.a", "detail": "work", "config": {"token": "a"}},
                {"source": "~/.b", "detail": "personal",
                 "config": {"token": "b"}}]
        cfg = {"services": {}}
        seen = {}

        def fake_choose(options, prompt):
            seen["options"] = options
            return options[1]          # pick the second account

        with mock.patch.object(picker, "choose", fake_choose), \
             mock.patch.object(picker, "confirm", return_value=True), \
             mock.patch.object(picker, "notify"), \
             mock.patch.object(picker, "save_config"), \
             mock.patch.object(type(registry()["claude"]), "detect",
                               return_value=fake):
            picker._handle_choice(cfg, registry(), by_key("claude"))

        self.assertEqual(len(seen["options"]), 2)
        self.assertEqual(cfg["services"]["claude"]["token"], "b")

    def test_widget_passes_one_plain_argument(self):
        """The JSX must not rebuild nested AppleScript."""
        import pathlib
        jsx = pathlib.Path(__file__).parent.parent / \
            "widgets" / "ubersicht" / "aiquota.jsx"
        src = jsx.read_text()
        i = src.index("const removeService")
        block = src[i:i + 400]
        self.assertIn("aiquota-remove", block)
        self.assertNotIn("display dialog", block,
                         "AppleScript must not be built in the widget")


class TestBrowserReadAdapters(Base):
    """Providers only a real browser can reach.

    Perplexity sits behind Cloudflare TLS fingerprinting and Midjourney's
    host refuses Python's TLS, so both are read with an in-page fetch()
    during sign-in rather than by the adapter itself. Verified live: from
    inside Chrome, Perplexity answered 200 with JSON and Midjourney 401 —
    both real app responses, not challenge pages.
    """

    def _ad(self, name):
        from aiquota.core import load_adapters, registry
        load_adapters()
        return registry()[name]

    def test_both_offer_browser_login_with_read_endpoints(self):
        from aiquota.login_policy import may_browser_login
        for n in ("perplexity", "midjourney"):
            ad = self._ad(n)
            spec = ad.browser_login
            self.assertTrue(may_browser_login(n), n)
            self.assertTrue(spec["read"], f"{n}: nothing to read in-page")
            self.assertTrue(all(e.startswith("https://") for e in spec["read"]))

    def test_unconfigured_before_sign_in(self):
        for n in ("perplexity", "midjourney"):
            self.assertEqual(self._ad(n).probe({"_key": n}).tier,
                             "unconfigured")

    def test_perplexity_parses_counters(self):
        ad = self._ad("perplexity")
        ep = ad.endpoints[0]
        conf = {"_key": "perplexity", "session": {"x": "y"},
                "readings": {ep: {"gpt4_limit": 600, "gpt4_used": 150,
                                  "subscription_status": "pro"}}}
        r = ad.probe(conf)
        self.assertEqual(r.tier, "live")
        self.assertEqual(r.windows[0].used_pct, 25.0)
        self.assertEqual(r.plan, "Pro")

    def test_midjourney_parses_fast_minutes(self):
        ad = self._ad("midjourney")
        ep = ad.endpoints[0]
        conf = {"_key": "midjourney", "session": {"x": "y"},
                "readings": {ep: {"fast_time_used": 3, "fast_time_allowance": 15,
                                  "plan": "Standard"}}}
        r = ad.probe(conf)
        self.assertEqual(r.tier, "live")
        self.assertEqual(r.windows[0].used_pct, 20.0)

    def test_missing_counters_never_fabricate_a_number(self):
        ad = self._ad("perplexity")
        conf = {"_key": "perplexity", "session": {"x": "y"},
                "readings": {ad.endpoints[0]: {"subscription_status": "free"}}}
        r = ad.probe(conf)
        self.assertEqual(r.windows, [])
        self.assertIn("no usage counters", r.note)

    def test_signed_in_but_no_readings_is_an_error(self):
        ad = self._ad("perplexity")
        r = ad.probe({"_key": "perplexity", "session": {"x": "y"}})
        self.assertEqual(r.tier, "error")


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
