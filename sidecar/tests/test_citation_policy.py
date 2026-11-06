"""Citation policy: loader, validator, and the read-only endpoints (M0)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _tmp import TemporaryDirectory  # noqa: E402

from app import citation_policy as cp  # noqa: E402
from app import config, main, pages  # noqa: E402


def _policy(**over):
    """A minimal valid policy; callers override one section per test."""
    p = {
        "schema": 1,
        "sources": {
            "lib": {"tier": "B", "role": "cite", "locator_scheme": "page"},
            "rev": {"tier": "A", "role": "cite", "locator_scheme": "mediawiki-rev"},
            "tpl": {"role": "template"},
            "chk": {"role": "verify"},
        },
        "weight_profiles": {"equal": {}},
        "channels": [{"source": "lib", "kind": "local-file", "address": "/tmp"}],
        "rules": [{"when": {}, "cite": ["lib"], "weight_profile": "equal"}],
    }
    p.update(over)
    return p


class PolicyTestBase(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("SOCRATIC_POLICY", "SOCRATIC_SOURCES")}
        for k in self._env:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cp.reload()


class TestBuiltin(PolicyTestBase):
    def test_builtin_is_valid(self):
        self.assertEqual(cp.validate(cp._builtin()), [])

    def test_builtin_has_a_catch_all_rule(self):
        rules = cp._builtin()["rules"]
        self.assertEqual([r["when"] for r in rules].count({}), 1)

    def test_builtin_is_the_default(self):
        cp.reload()
        self.assertEqual(cp.origins(), ["builtin"])
        self.assertIsNone(cp.last_error())

    def test_version_is_twelve_hex_and_stable(self):
        v = cp.version()
        self.assertEqual(len(v), 12)
        int(v, 16)
        self.assertEqual(v, cp.version())

    def test_effective_reports_what_is_enforced(self):
        payload = cp.effective()
        self.assertFalse(payload["enforced"])          # ranking still not policy-driven
        self.assertEqual(payload["enforced_parts"],
                         {"channels": True, "tier": True, "routing": True,
                          "ranking": False})
        self.assertEqual(payload["policy_version"], cp.version())
        self.assertIn("M3", payload["note"])


class TestValidate(PolicyTestBase):
    def assertRejected(self, policy, needle):
        errs = cp.validate(policy)
        self.assertTrue(errs, "expected errors, got none")
        self.assertTrue(any(needle in e for e in errs),
                        "no error mentions %r; got %r" % (needle, errs))

    def test_unknown_source_in_cite(self):
        p = _policy()
        p["rules"] = [{"when": {}, "cite": ["nope"]}]
        self.assertRejected(p, "must name a source with role=cite")

    def test_empty_cite(self):
        p = _policy()
        p["rules"] = [{"when": {}, "cite": []}]
        self.assertRejected(p, "non-empty ordered list")

    def test_cite_source_without_scheme(self):
        p = _policy()
        p["sources"]["lib"]["locator_scheme"] = None
        self.assertRejected(p, "cite sources need one of")

    def test_template_source_cannot_carry_a_locator(self):
        p = _policy()
        p["sources"]["tpl"]["locator_scheme"] = "page"
        self.assertRejected(p, "cannot carry a locator")

    def test_require_field_not_carried_by_scheme(self):
        p = _policy()
        p["rules"] = [{"when": {}, "cite": ["lib"],
                       "require": {"locator": ["edition"]}}]
        self.assertRejected(p, "no cited source's locator scheme")

    def test_require_field_ok_when_scheme_carries_it(self):
        p = _policy()
        p["sources"]["docs"] = {"tier": "A", "role": "cite",
                                "locator_scheme": "edition-page"}
        p["rules"] = [{"when": {}, "cite": ["docs"],
                       "require": {"locator": ["edition"]}}]
        self.assertEqual(cp.validate(p), [])

    def test_unknown_weight_profile(self):
        p = _policy()
        p["rules"] = [{"when": {}, "cite": ["lib"], "weight_profile": "ghost"}]
        self.assertRejected(p, "unknown profile")

    def test_negative_weight(self):
        p = _policy(weight_profiles={"w": {"lib": -1}})
        self.assertRejected(p, "number >= 0")

    def test_weight_for_unknown_source(self):
        p = _policy(weight_profiles={"w": {"ghost": 1.0}})
        self.assertRejected(p, "unknown source")

    def test_missing_catch_all(self):
        p = _policy()
        p["rules"] = [{"when": {"subject": "math"}, "cite": ["lib"]}]
        self.assertRejected(p, "catch-all rule")

    def test_secret_in_channel_is_rejected(self):
        p = _policy()
        p["channels"] = [{"source": "lib", "kind": "cloud-object",
                          "address": "s3://b", "token": "ghp_deadbeef"}]
        self.assertRejected(p, "secrets belong in the environment")

    def test_auth_env_must_be_a_name(self):
        p = _policy()
        p["channels"] = [{"source": "lib", "kind": "cloud-object",
                          "address": "s3://b", "auth_env": "ghp_deadbeef"}]
        self.assertRejected(p, "not its value")

    def test_unknown_channel_source(self):
        p = _policy()
        p["channels"] = [{"source": "ghost", "kind": "local-file",
                          "address": "/tmp"}]
        self.assertRejected(p, "unknown source")

    def test_unknown_channel_kind(self):
        p = _policy()
        p["channels"] = [{"source": "lib", "kind": "floppy", "address": "x"}]
        self.assertRejected(p, "must be one of")

    def test_fallback_toward_typo(self):
        p = _policy()
        p["rules"] = [{"when": {}, "cite": ["lib"],
                       "fallback": {"toward": "downwards"}}]
        self.assertRejected(p, "earlier or later")


class TestLoader(PolicyTestBase):
    def test_user_file_overrides_and_is_versioned(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "policy.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("weight_profiles:\n  equal: {}\n"
                         "  strict: {library-pdf: 2.0}\n")
            before = cp.version()
            os.environ["SOCRATIC_POLICY"] = path
            ok, errs = cp.reload()
            self.assertTrue(ok, errs)
            self.assertIn(path, cp.origins())
            self.assertIn("strict", cp.current()["weight_profiles"])
            self.assertNotEqual(before, cp.version())

    def test_bad_file_keeps_the_previous_policy(self):
        with TemporaryDirectory() as d:
            good = os.path.join(d, "good.yaml")
            with open(good, "w", encoding="utf-8") as fh:
                fh.write("weight_profiles:\n  equal: {}\n"
                         "  strict: {library-pdf: 2.0}\n")
            os.environ["SOCRATIC_POLICY"] = good
            self.assertTrue(cp.reload()[0])
            version = cp.version()

            bad = os.path.join(d, "bad.yaml")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("rules: []\n")          # drops the required catch-all
            os.environ["SOCRATIC_POLICY"] = bad
            ok, errs = cp.reload()
            self.assertFalse(ok)
            self.assertTrue(errs)
            self.assertIsNotNone(cp.last_error())
            self.assertEqual(cp.version(), version)   # previous policy retained
            self.assertIn("strict", cp.current()["weight_profiles"])

    def test_missing_file_is_an_error_not_a_crash(self):
        os.environ["SOCRATIC_POLICY"] = os.path.join("Z:\\", "nope", "policy.yaml")
        ok, errs = cp.reload()
        self.assertFalse(ok)
        self.assertTrue(errs)

    def test_off_returns_to_builtin(self):
        os.environ["SOCRATIC_POLICY"] = "off"
        ok, _ = cp.reload()
        self.assertTrue(ok)
        self.assertEqual(cp.origins(), ["builtin"])

    def test_channels_file_can_add_channels(self):
        with TemporaryDirectory() as d:
            pol = os.path.join(d, "policy.yaml")
            with open(pol, "w", encoding="utf-8") as fh:
                fh.write("weight_profiles:\n  equal: {}\n")
            ch = os.path.join(d, "sources.local.yaml")
            with open(ch, "w", encoding="utf-8") as fh:
                fh.write("channels:\n"
                         "  - {source: library-pdf, kind: local-file, address: '%s'}\n"
                         % d.replace("\\", "/"))
            os.environ["SOCRATIC_POLICY"] = pol
            os.environ["SOCRATIC_SOURCES"] = ch
            ok, errs = cp.reload()
            self.assertTrue(ok, errs)
            self.assertEqual([c["source"] for c in cp.channels()], ["library-pdf"])


class TestChannels(PolicyTestBase):
    def test_availability_without_network(self):
        with TemporaryDirectory() as d:
            db = os.path.join(d, "x.db")
            with open(db, "wb") as fh:
                fh.write(b"SQLite format 3\x00")
            policy = _policy(channels=[
                {"source": "lib", "kind": "local-file", "address": d},
                {"source": "lib", "kind": "local-file", "address": d + "_missing"},
                {"source": "lib", "kind": "rag-sqlite",
                 "address": "sqlite:///" + db.replace("\\", "/") + "#a"},
                {"source": "lib", "kind": "rag-sqlite",
                 "address": "sqlite:///" + d.replace("\\", "/") + "/nope.db#a"},
                {"source": "rev", "kind": "public-api",
                 "address": "https://example.invalid/api"},
            ])
            self.assertEqual(cp.validate(policy), [])
            avail = cp._availability
            self.assertEqual(avail(policy["channels"][0]), "ready")
            self.assertEqual(avail(policy["channels"][1]), "missing")
            self.assertEqual(avail(policy["channels"][2]), "ready")
            self.assertEqual(avail(policy["channels"][3]), "missing")
            self.assertEqual(avail(policy["channels"][4]), "unprobed")

    def test_sqlite_address_strips_the_uri_prefix(self):
        self.assertEqual(cp.sqlite_path("sqlite:///D:/x/y.db#library"),
                         "D:/x/y.db")
        self.assertEqual(cp.sqlite_path("sqlite:///tmp/y.db"), "/tmp/y.db")
        self.assertEqual(cp.sqlite_path("plain.db"), "plain.db")

    def test_capabilities_by_kind(self):
        self.assertIn("page_render", cp.CAPABILITIES["local-file"])
        self.assertIn("search", cp.CAPABILITIES["rag-sqlite"])
        self.assertNotIn("page_render", cp.CAPABILITIES["rag-sqlite"])


class TestResolve(PolicyTestBase):
    def test_subject_rule_wins_over_catch_all(self):
        policy = _policy(rules=[
            {"when": {"subject": "math"}, "cite": ["lib"]},
            {"when": {}, "cite": ["rev"]},
        ])
        self.assertEqual(cp.validate(policy), [])
        rule = None
        for r in policy["rules"]:
            if r["when"].get("subject") == "math":
                rule = r
        self.assertEqual(rule["cite"], ["lib"])

    def test_effective_rules_are_ordered(self):
        cp.reload()
        rules = cp.effective()["rules"]
        self.assertTrue(rules)
        self.assertEqual(rules[-1]["when"], {})


class TestEndpoints(PolicyTestBase):
    def test_policy_endpoint(self):
        payload = main.v1_policy()
        self.assertIn("policy_version", payload)
        self.assertIn("sources", payload)
        self.assertIn("channels", payload)
        self.assertFalse(payload["enforced"])

    def test_channels_endpoint(self):
        payload = main.v1_channels()
        self.assertEqual(payload["policy_version"], cp.version())
        for row in payload["channels"]:
            self.assertIn("capabilities", row)
            self.assertIn(row["availability"], ("ready", "missing", "unprobed"))

    def test_reload_endpoint(self):
        payload = main.v1_policy_reload()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["policy_version"], cp.version())


class TestTier(PolicyTestBase):
    """M2: the citation tier is read from the policy instead of a constant."""

    def test_v1_sources_are_b_and_estimated(self):
        self.assertEqual(cp.tier_for_source("library"), ("B", True))
        self.assertEqual(cp.tier_for_source("steadman"), ("B", True))
        self.assertEqual(cp.tier_for_source("teubner_conte"), ("B", True))

    def test_v2_source_family_maps_to_a(self):
        self.assertEqual(cp.tier_for_source("wikisource:zh"), ("A", False))
        self.assertEqual(cp.tier_for_source("cts"), ("A", False))

    def test_unknown_source_is_reported_not_invented(self):
        self.assertEqual(cp.tier_for_source("ghost:xx"), ("unknown", True))
        self.assertEqual(cp.tier_for_source(None), ("unknown", True))

    def test_policy_override_changes_the_tier(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "policy.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("sources:\n"
                         "  library-pdf: {tier: C, role: cite, locator_scheme: page,"
                         " tier_estimated: false}\n"
                         "channels: []\n"
                         "routing:\n  rules: []\n"
                         "  default_prefer: [library-pdf]\n"
                         "rules:\n"
                         "  - {when: {}, cite: [library-pdf]}\n")
            os.environ["SOCRATIC_POLICY"] = path
            ok, errs = cp.reload()
            self.assertTrue(ok, errs)
            self.assertEqual(cp.tier_for_source("library"), ("C", False))

    def test_tier_estimated_must_be_boolean(self):
        p = _policy()
        p["sources"]["lib"]["tier_estimated"] = "yes"
        errs = cp.validate(p)
        self.assertTrue(any("tier_estimated" in e for e in errs), errs)


class TestRouting(PolicyTestBase):
    """M3: routing comes from the policy table, in the same decision order."""

    def test_classical_chinese_prefers_v2(self):
        d = cp.route("史記 黃帝")
        self.assertEqual(d["reason"], "classical-zh")
        self.assertEqual(d["prefer"][0], "wikisource")

    def test_latin_work_prefers_v2(self):
        self.assertEqual(cp.route("Iliad book 1")["reason"], "v2-work")
        self.assertEqual(cp.route("Aeneid 1.1")["reason"], "v2-work")

    def test_greek_work_name_matches_too(self):
        # the old keyword table only carried the Latin transliterations
        self.assertEqual(cp.route("Ἰλιάς")["reason"], "v2-work")

    def test_greek_quote_uses_the_fallback_rule(self):
        self.assertEqual(cp.route("μῆνιν ἄειδε θεά")["reason"], "greek-quote")

    def test_long_greek_query_falls_through(self):
        self.assertEqual(cp.route("μ" * 100)["reason"], "default")

    def test_plain_query_uses_the_default_preference(self):
        d = cp.route("微分")
        self.assertEqual(d["reason"], "default")
        self.assertEqual(d["prefer"], ["library-pdf"])

    def test_catalogue_mapping(self):
        self.assertEqual(cp.catalogue_of("wikisource"), "v2")
        self.assertEqual(cp.catalogue_of("library-pdf"), "v1")
        self.assertIsNone(cp.catalogue_of("ghost"))

    def test_federated_route_keeps_the_reported_reasons(self):
        from app import federated
        self.assertEqual(federated._route("史記"), ("classical-zh", True))
        self.assertEqual(federated._route("微分"), ("v1-default", False))
        self.assertEqual(federated._route("Ἰλιάς"), ("v2-work", True))

    def test_policy_can_drop_every_route_rule(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "policy.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("routing:\n  rules: []\n"
                         "  default_prefer: [library-pdf]\n")
            os.environ["SOCRATIC_POLICY"] = path
            ok, errs = cp.reload()
            self.assertTrue(ok, errs)
            self.assertEqual(cp.route("史記")["reason"], "default")

    def test_unknown_prefer_source_is_rejected(self):
        p = _policy(routing={"rules": [{"id": "x", "any_of": "zh-history",
                                        "prefer": ["ghost"]}],
                              "default_prefer": ["lib"]},
                    markers={"zh-history": ["史記"]})
        errs = cp.validate(p)
        self.assertTrue(any("prefer.ghost" in e for e in errs), errs)

    def test_unknown_marker_list_is_rejected(self):
        p = _policy(routing={"rules": [{"id": "x", "any_of": "nope",
                                        "prefer": ["lib"]}],
                              "default_prefer": ["lib"]})
        errs = cp.validate(p)
        self.assertTrue(any("unknown marker list" in e for e in errs), errs)

    def test_a_rule_needs_a_matcher(self):
        p = _policy(routing={"rules": [{"id": "x", "prefer": ["lib"]}],
                              "default_prefer": ["lib"]})
        errs = cp.validate(p)
        self.assertTrue(any("needs any_of or regex" in e for e in errs), errs)

    def test_regex_must_compile(self):
        p = _policy(routing={"rules": [{"id": "x", "regex": "[",
                                        "prefer": ["lib"]}],
                              "default_prefer": ["lib"]})
        errs = cp.validate(p)
        self.assertTrue(any("regex" in e for e in errs), errs)


class TestMerge(PolicyTestBase):
    """M4: merge mode, per-catalogue weights and anchor marking."""

    def test_default_plan_is_rrf_and_ignores_weights(self):
        plan = cp.merge_plan()
        self.assertEqual(plan["mode"], "rrf")
        self.assertEqual(plan["order"], ["v1", "v2"])
        self.assertEqual(plan["anchor"], "v1")
        self.assertEqual(plan["weights"], {})     # rrf never weights

    def test_weighted_plan_reads_the_profile_per_catalogue(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "policy.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("weight_profiles:\n"
                         "  equal: {}\n"
                         "  textbook-first: {library-pdf: 1.0, wikisource: 0.4}\n"
                         "rules:\n"
                         "  - when: {}\n"
                         "    cite: [library-pdf, wikisource]\n"
                         "    merge: {mode: weighted}\n"
                         "    weight_profile: textbook-first\n")
            os.environ["SOCRATIC_POLICY"] = path
            ok, errs = cp.reload()
            self.assertTrue(ok, errs)
            plan = cp.merge_plan()
            self.assertEqual(plan["mode"], "weighted")
            self.assertEqual(plan["weights"], {"v1": 1.0, "v2": 0.4})

    def test_tiered_order_puts_the_anchor_catalogue_first(self):
        from app import federated
        fused = {("v2", 1): 5.0, ("v1", 2): 1.0}
        best = {("v2", 1): {"schema": "v2", "score": 5.0},
                ("v1", 2): {"schema": "v1", "score": 1.0}}
        self.assertEqual(
            federated._order_fused(fused, best, {"mode": "tiered",
                                                 "order": ["v1", "v2"]}),
            [("v1", 2), ("v2", 1)])
        self.assertEqual(
            federated._order_fused(fused, best, {"mode": "rrf"}),
            [("v2", 1), ("v1", 2)])

    def test_anchor_marking_preserves_the_rest_of_the_citation(self):
        from app import federated
        results = [{"schema": "v1", "citation": {"tier": "B"}},
                   {"schema": "v2", "citation": {"tier": "A"}}]
        federated._mark_anchor(results, "v1")
        self.assertEqual(results[0]["citation"]["role_in_answer"], "anchor")
        self.assertEqual(results[1]["citation"]["role_in_answer"], "corroborating")
        self.assertEqual(results[0]["citation"]["tier"], "B")

    def test_unknown_merge_mode_is_rejected(self):
        p = _policy()
        p["rules"] = [{"when": {}, "cite": ["lib"], "merge": {"mode": "magic"}}]
        errs = cp.validate(p)
        self.assertTrue(any("merge.mode" in e for e in errs), errs)

    def test_merge_must_be_a_mapping(self):
        p = _policy()
        p["rules"] = [{"when": {}, "cite": ["lib"], "merge": "rrf"}]
        errs = cp.validate(p)
        self.assertTrue(any("merge: must be a mapping" in e for e in errs), errs)


class TestMergeEquivalence(PolicyTestBase):
    """The default policy must reproduce the pre-M4 merge numerically."""

    PAYLOADS = [
        {"schema": "v1", "results": [{"chunk_id": 1, "score": 0.9},
                                     {"chunk_id": 2, "score": 0.8}]},
        {"schema": "v2", "results": [{"chunk_id": 3, "score": 0.95},
                                     {"chunk_id": 1, "score": 0.7}]},
    ]

    def test_default_merge_is_the_old_rrf(self):
        from app import federated
        old_fused, best = {}, {}
        for p in self.PAYLOADS:
            for rank, hit in enumerate(p["results"]):
                key = (p["schema"], hit["chunk_id"])
                old_fused[key] = old_fused.get(key, 0.0) + 1.0 / (60 + rank + 1)
                if key not in best or hit["score"] > best[key]["score"]:
                    best[key] = hit
        expected = sorted(old_fused,
                          key=lambda k: (-old_fused[k], -best[k]["score"]))

        old_v1, old_pub = federated.config.V1_DB, federated.config.PUBLIC_DB
        old_exists, old_run = federated.os.path.exists, federated._run_one
        seq = iter([dict(p) for p in self.PAYLOADS])
        federated.config.V1_DB, federated.config.PUBLIC_DB = "v1.db", "pub.db"
        federated.os.path.exists = lambda p: True
        federated._run_one = lambda *a, **k: dict(next(seq))
        try:
            out = federated.search_all("q", limit=10)
        finally:
            federated._run_one, federated.os.path.exists = old_run, old_exists
            federated.config.V1_DB, federated.config.PUBLIC_DB = old_v1, old_pub

        got = [(r["schema"], r["chunk_id"]) for r in out["results"]]
        self.assertEqual(got, expected)
        self.assertEqual(out["merge"]["mode"], "rrf")
        self.assertEqual(out["merge"]["anchor"], "v1")
        roles = {r["schema"]: r["citation"]["role_in_answer"] for r in out["results"]}
        self.assertEqual(roles, {"v1": "anchor", "v2": "corroborating"})


class TestM1Serving(unittest.TestCase):
    """M1: page roots and the render gate are derived from the channel table."""

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("SOCRATIC_POLICY", "SOCRATIC_SOURCES")}
        for k in self._env:
            os.environ.pop(k, None)
        self._roots = dict(pages.ROOTS)
        cp.reload()
        pages.refresh_roots()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cp.reload()
        pages.ROOTS.clear()
        pages.ROOTS.update(self._roots)

    def _write_policy(self, directory, body):
        path = os.path.join(directory, "policy.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.environ["SOCRATIC_POLICY"] = path
        ok, errs = cp.reload()
        self.assertTrue(ok, errs)
        pages.refresh_roots()
        return path

    def test_default_roots_are_the_legacy_layout(self):
        self.assertEqual(pages.ROOTS["library"],
                         os.path.join(config.LIBRARY, "PDF"))
        self.assertEqual(pages.ROOTS["steadman"],
                         os.path.join(config.LIBRARY, "PDF-new", "Steadman"))
        self.assertEqual(pages.ROOTS["teubner_conte"],
                         os.path.join(config.LIBRARY, "teubner"))

    def test_roots_follow_the_local_file_channels(self):
        with TemporaryDirectory() as d:
            self._write_policy(
                d,
                "channels:\n"
                "  - {source: library-pdf, kind: local-file, address: '%s'}\n"
                % d.replace("\\", "/"))
            self.assertEqual(os.path.abspath(pages.ROOTS["library"]),
                             os.path.abspath(d))
            # a source the policy does not describe keeps the legacy default
            self.assertEqual(pages.ROOTS["steadman"],
                             os.path.join(config.LIBRARY, "PDF-new", "Steadman"))

    def test_capability_gate_blocks_a_search_only_source(self):
        with TemporaryDirectory() as d:
            self._write_policy(
                d,
                "channels:\n"
                "  - {source: library-pdf, kind: rag-sqlite, address: 'sqlite:///x.db'}\n"
                "  - {source: steadman, kind: local-file, address: '%s'}\n"
                % d.replace("\\", "/"))
            self.assertNotIn("page_render", cp.capabilities("library-pdf"))
            with self.assertRaises(cp.CapabilityMissing):
                pages.render("library", "anything.pdf", 1)
            # a render-capable source passes the gate and then fails on the book
            with self.assertRaises(FileNotFoundError):
                pages.render("steadman", "nope.pdf", 1)

    def test_pages_endpoint_answers_422_for_a_missing_capability(self):
        with TemporaryDirectory() as d:
            self._write_policy(
                d,
                "channels:\n"
                "  - {source: library-pdf, kind: rag-sqlite, address: 'sqlite:///x.db'}\n")
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as ctx:
                main.v1_pages(source="library", book="x.pdf", page=1,
                              dpi=150, bbox=None)
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertEqual(ctx.exception.detail["code"], "capability_missing")
            self.assertEqual(ctx.exception.detail["need"], ["page_render"])

    def test_channels_report_whether_serving_uses_them(self):
        payload = main.v1_channels()
        used = [r for r in payload["channels"] if r.get("in_use")]
        self.assertTrue(all(r["kind"] in ("local-file", "rag-sqlite") for r in used))
        self.assertEqual(payload["serving"]["db"], config.DB)
        self.assertTrue(any(r["source"] == "library-pdf" and r["in_use"]
                            for r in payload["channels"]))

    def test_reload_reports_the_page_roots(self):
        payload = main.v1_policy_reload()
        self.assertTrue(payload["ok"])
        self.assertEqual(os.path.abspath(payload["page_roots"]["library"]),
                         os.path.abspath(pages.ROOTS["library"]))


if __name__ == "__main__":
    unittest.main()
