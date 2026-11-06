"""Citation policy: logical sources, channels, and per-subject rules.

M0 scope: the data model, the loader, the validator and the read-only
endpoints. **Nothing in the serving path reads this module yet**, so behaviour
is unchanged; `enforced` in the payload says so explicitly.

Design notes live in docs/CITATION-POLICY.md and docs/CITATION-POLICY-PLAN.md.
The three abstract pieces:

  Source   identity, trust tier, role (cite|template|verify), locator scheme
  Channel  how the same source is reached (local file, RAG db, API, cloud)
  Rule     subject x doc_kind -> ordered sources, fallback direction, weights

Precedence, later wins: builtin -> packaged policy.yaml -> user file
(SOCRATIC_POLICY) -> channels file (SOCRATIC_SOURCES) -> env. `SOCRATIC_POLICY=off`
returns to the builtin table, which mirrors today's behaviour.
"""
import hashlib
import json
import os
import re
import threading
import unicodedata

from . import config

SCHEMA = 1

TIERS = ("A", "B", "C", "D")
ROLES = ("cite", "template", "verify")

#: how results from several catalogues are combined (M4)
#: rrf      — today's behaviour: plain reciprocal-rank fusion, weights ignored
#: weighted — the same fusion with a per-catalogue weight from the rule's profile
#: tiered   — the anchor catalogue fills the list first, others only top it up
MERGE_MODES = ("rrf", "weighted", "tiered")

#: locator scheme -> the locator fields that scheme can carry
SCHEMES = {
    "page": set(),                 # book + page number is the identity
    "mediawiki-rev": {"revision"},
    "cts-urn": {"urn"},
    "edition-page": {"edition"},
    "measure": {"measure"},
    "doi": {"doi"},
}

#: channel kind -> capabilities it provides
CAPABILITIES = {
    "local-file": {"page_render", "verify"},
    "rag-sqlite": {"search", "verify"},
    "public-api": {"search", "verify"},
    "dataset-dir": {"search"},
    "cloud-object": {"page_render", "verify"},
}

KINDS = tuple(CAPABILITIES)

_AUTH_ENV = re.compile(r"^[A-Z_][A-Z0-9_]*$")

_LOCK = threading.Lock()
_STATE = {"policy": None, "origins": [], "error": None, "version": None}


def _builtin():
    """The table that mirrors today's behaviour.

    One logical source per catalogue root, one channel per way it is reached
    today (config/pages). No subject rules yet: `cite` lists the routable set,
    not a merge order, because merging arrives in M4.
    """
    from . import translate          # lazy: keeps the import graph acyclic
    return {
        "schema": SCHEMA,
        "sources": {
            "library-pdf": {"tier": "B", "tier_estimated": True, "role": "cite",
                            "catalogue": "v1", "locator_scheme": "page",
                            "display": "自扫 PDF（原页）"},
            "steadman": {"tier": "B", "tier_estimated": True, "role": "cite",
                         "catalogue": "v1", "locator_scheme": "page",
                         "display": "Steadman 教学本"},
            "teubner-conte": {"tier": "B", "tier_estimated": True, "role": "cite",
                              "catalogue": "v1", "locator_scheme": "page",
                              "display": "Teubner Aeneis"},
            "wikisource": {"tier": "A", "role": "cite", "catalogue": "v2",
                           "locator_scheme": "mediawiki-rev",
                           "display": "Wikisource 校对本"},
            "cts": {"tier": "A", "role": "cite", "catalogue": "v2",
                    "locator_scheme": "cts-urn", "display": "Perseus CTS"},
        },
        # Routing hints are data now: the old keyword tables lived in federated.py.
        "markers": {
            "zh-history": list(translate.ZH_HISTORY_MARKERS),
            "v2-works": ["iliad", "aeneid", "homer", "virgil", "vergil",
                         "Ἰλιάς", "Ἰλιάδος", "Αἰνειάς", "Αἰνείας", "Αἰνειάδος"],
        },
        "routing": {
            "rules": [
                {"id": "classical-zh", "any_of": "zh-history",
                 "prefer": ["wikisource", "cts"]},
                {"id": "v2-work", "any_of": "v2-works",
                 "prefer": ["wikisource", "cts"]},
                {"id": "greek-quote", "regex": "[\u0370-\u03ff\u1f00-\u1fff]",
                 "max_query_len": 80, "prefer": ["wikisource", "cts"]},
            ],
            "default_prefer": ["library-pdf"],
        },
        "channels": [
            {"source": "library-pdf", "kind": "local-file",
             "address": os.path.join(config.LIBRARY, "PDF"),
             "prefer_when": "always"},
            {"source": "library-pdf", "kind": "rag-sqlite",
             "address": "sqlite:///" + config.V1_DB.replace("\\", "/") + "#library"},
            {"source": "steadman", "kind": "local-file",
             "address": os.path.join(config.LIBRARY, "PDF-new", "Steadman"),
             "prefer_when": "always"},
            {"source": "teubner-conte", "kind": "local-file",
             "address": os.path.join(config.LIBRARY, "teubner"),
             "prefer_when": "always"},
            {"source": "wikisource", "kind": "rag-sqlite",
             "address": "sqlite:///" + config.PUBLIC_DB.replace("\\", "/") + "#wikisource"},
            {"source": "cts", "kind": "rag-sqlite",
             "address": "sqlite:///" + config.PUBLIC_DB.replace("\\", "/") + "#cts"},
        ],
        "weight_profiles": {"equal": {}},
        "rules": [
            {"when": {}, "cite": ["library-pdf", "steadman", "teubner-conte",
                                  "wikisource", "cts"],
             "merge": {"mode": "rrf"},
             "weight_profile": "equal"},
        ],
    }


def _merge(base, overlay):
    """Shallow merge by section: a section present in the overlay replaces it."""
    out = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
           for k, v in base.items()}
    for k, v in (overlay or {}).items():
        out[k] = v
    return out


def _read_yaml(path):
    try:
        import yaml
    except ImportError:                 # pragma: no cover - install-time issue
        raise RuntimeError(
            "policy files need PyYAML (pip install PyYAML); "
            "the builtin policy works without it")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("%s: top level must be a mapping" % path)
    return data


def _user_policy_path():
    raw = os.environ.get("SOCRATIC_POLICY", "").strip()
    if raw.lower() == "off":
        return None
    if raw:
        return raw
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for p in (os.path.join(here, "policy.local.yaml"),
              os.path.join(os.environ.get("APPDATA", ""),
                           "socratic-tutor", "policy.local.yaml")):
        if p and os.path.exists(p):
            return p
    return None


def _channels_path(policy_path):
    raw = os.environ.get("SOCRATIC_SOURCES", "").strip()
    if raw:
        return raw
    if policy_path:
        p = os.path.join(os.path.dirname(policy_path), "sources.local.yaml")
        if os.path.exists(p):
            return p
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(here, "sources.local.yaml")
    return p if os.path.exists(p) else None


def validate(policy):
    """Return a list of human-readable problems; empty means valid."""
    errs = []
    if not isinstance(policy, dict):
        return ["policy: top level must be a mapping"]
    sources = policy.get("sources") or {}
    if not isinstance(sources, dict) or not sources:
        return ["sources: at least one source is required"]
    for sid, src in sources.items():
        if not isinstance(src, dict):
            errs.append("sources.%s: must be a mapping" % sid)
            continue
        role = src.get("role")
        if role not in ROLES:
            errs.append("sources.%s.role: must be one of %s" % (sid, ", ".join(ROLES)))
        scheme = src.get("locator_scheme")
        if role == "cite":
            if scheme not in SCHEMES:
                errs.append("sources.%s.locator_scheme: cite sources need one of %s"
                            % (sid, ", ".join(sorted(SCHEMES))))
        elif scheme is not None:
            errs.append("sources.%s.locator_scheme: %s sources cannot carry a locator"
                        % (sid, role))
        tier = src.get("tier")
        if tier is not None and tier not in TIERS:
            errs.append("sources.%s.tier: must be one of %s" % (sid, ", ".join(TIERS)))
        est = src.get("tier_estimated")
        if est is not None and not isinstance(est, bool):
            errs.append("sources.%s.tier_estimated: must be true or false" % sid)
        cat = src.get("catalogue")
        if cat is not None and cat not in ("v1", "v2"):
            errs.append("sources.%s.catalogue: must be v1 or v2" % sid)

    profiles = policy.get("weight_profiles") or {}
    if not isinstance(profiles, dict):
        errs.append("weight_profiles: must be a mapping")
        profiles = {}
    for name, weights in profiles.items():
        if not isinstance(weights, dict):
            errs.append("weight_profiles.%s: must be a mapping" % name)
            continue
        for sid, w in weights.items():
            if sid not in sources:
                errs.append("weight_profiles.%s.%s: unknown source" % (name, sid))
            if not isinstance(w, (int, float)) or isinstance(w, bool) or w < 0:
                errs.append("weight_profiles.%s.%s: must be a number >= 0" % (name, sid))

    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        return errs + ["rules: a non-empty list is required"]
    seen_catch_all = 0
    for i, rule in enumerate(rules):
        where = "rules[%d]" % i
        if not isinstance(rule, dict):
            errs.append("%s: must be a mapping" % where)
            continue
        when = rule.get("when")
        if not isinstance(when, dict):
            errs.append("%s.when: must be a mapping (use {} for the catch-all)" % where)
            when = {}
        if not when:
            seen_catch_all += 1
        cite = rule.get("cite")
        if not isinstance(cite, list) or not cite:
            errs.append("%s.cite: a non-empty ordered list is required" % where)
            cite = []
        for sid in cite:
            if sources.get(sid, {}).get("role") != "cite":
                errs.append("%s.cite.%s: must name a source with role=cite" % (where, sid))
        for field, role in (("template", "template"), ("verify", "verify")):
            for sid in rule.get(field) or []:
                if sources.get(sid, {}).get("role") != role:
                    errs.append("%s.%s.%s: must name a source with role=%s"
                                % (where, field, sid, role))
        fb = rule.get("fallback")
        if isinstance(fb, dict):
            if fb.get("toward") not in (None, "earlier", "later"):
                errs.append("%s.fallback.toward: must be earlier or later" % where)
        elif isinstance(fb, list):
            for sid in fb:
                if sid not in sources:
                    errs.append("%s.fallback.%s: unknown source" % (where, sid))
        elif fb is not None:
            errs.append("%s.fallback: must be a mapping or a list" % where)
        req = (rule.get("require") or {}).get("locator") or []
        for field in req:
            carriers = [s for s, meta in sources.items()
                        if s in cite and field in SCHEMES.get(meta.get("locator_scheme"), set())]
            if not carriers:
                errs.append("%s.require.locator.%s: no cited source's locator scheme "
                            "carries that field" % (where, field))
        prof = rule.get("weight_profile")
        if prof is not None and prof not in profiles:
            errs.append("%s.weight_profile: unknown profile %r" % (where, prof))
        merge = rule.get("merge")
        if merge is not None:
            if not isinstance(merge, dict):
                errs.append("%s.merge: must be a mapping" % where)
            elif merge.get("mode") not in (None,) + MERGE_MODES:
                errs.append("%s.merge.mode: must be one of %s"
                            % (where, ", ".join(MERGE_MODES)))
    if seen_catch_all == 0:
        errs.append("rules: a catch-all rule ({when: {}}) is required")

    channels = policy.get("channels") or []
    if not isinstance(channels, list):
        errs.append("channels: must be a list")
        channels = []
    for i, ch in enumerate(channels):
        where = "channels[%d]" % i
        if not isinstance(ch, dict):
            errs.append("%s: must be a mapping" % where)
            continue
        if ch.get("source") not in sources:
            errs.append("%s.source: unknown source %r" % (where, ch.get("source")))
        if ch.get("kind") not in KINDS:
            errs.append("%s.kind: must be one of %s" % (where, ", ".join(KINDS)))
        env = ch.get("auth_env")
        if env is not None and not _AUTH_ENV.match(str(env)):
            errs.append("%s.auth_env: must be the NAME of an environment "
                        "variable, not its value" % where)
        for leak in ("auth", "token", "password", "secret"):
            if leak in ch:
                errs.append("%s.%s: secrets belong in the environment, "
                            "name it with auth_env" % (where, leak))

    markers = policy.get("markers") or {}
    if not isinstance(markers, dict):
        errs.append("markers: must be a mapping")
        markers = {}
    for name, values in markers.items():
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            errs.append("markers.%s: must be a list of strings" % name)

    routing = policy.get("routing") or {}
    if not isinstance(routing, dict):
        errs.append("routing: must be a mapping")
        routing = {}
    for i, rule in enumerate(routing.get("rules") or []):
        where = "routing.rules[%d]" % i
        if not isinstance(rule, dict):
            errs.append("%s: must be a mapping" % where)
            continue
        ref = rule.get("any_of")
        if ref is None and not rule.get("regex"):
            errs.append("%s: needs any_of or regex" % where)
        if isinstance(ref, str) and ref not in markers:
            errs.append("%s.any_of: unknown marker list %r" % (where, ref))
        if isinstance(ref, list) and not all(isinstance(x, str) for x in ref):
            errs.append("%s.any_of: must be a marker-list name or strings" % where)
        if rule.get("regex"):
            try:
                re.compile(str(rule["regex"]))
            except re.error as e:
                errs.append("%s.regex: %s" % (where, e))
        for sid in rule.get("prefer") or []:
            if sid not in sources:
                errs.append("%s.prefer.%s: unknown source" % (where, sid))
    for sid in routing.get("default_prefer") or []:
        if sid not in sources:
            errs.append("routing.default_prefer.%s: unknown source" % sid)
    return errs


def _canonical(policy):
    return json.dumps(policy, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def version(policy=None):
    if policy is None:
        if _STATE["policy"] is not None and _STATE["version"]:
            return _STATE["version"]
        policy = current()
    return hashlib.sha1(_canonical(policy).encode("utf-8")).hexdigest()[:12]


def _load():
    policy, origins = _builtin(), ["builtin"]
    path = _user_policy_path()
    if path:
        policy = _merge(policy, _read_yaml(path))
        origins.append(path)
    ch_path = _channels_path(path)
    if ch_path:
        data = _read_yaml(ch_path)
        if "channels" in data:
            policy["channels"] = data["channels"]
            origins.append(ch_path)
        if "sources" in data:          # a channels file may add sources too
            policy["sources"] = {**policy.get("sources", {}), **data["sources"]}
    return policy, origins


def reload():
    """Re-read the files. Returns (ok, errors); a bad file keeps the old policy."""
    global _STATE

    def keep(policy, origins, error):
        global _STATE
        _STATE = {"policy": policy, "origins": origins, "error": error,
                  "version": version(policy)}

    try:
        policy, origins = _load()
        errs = validate(policy)
    except Exception as e:              # parse error, unreadable file, ...
        with _LOCK:
            msg = "%s: %s" % (type(e).__name__, e)
            keep(_STATE["policy"] or _builtin(),
                 _STATE["origins"] or ["builtin"], msg)
        return False, [msg]
    with _LOCK:
        if errs:
            keep(_STATE["policy"] or _builtin(),
                 _STATE["origins"] or ["builtin"], "; ".join(errs))
            return False, errs
        keep(policy, origins, None)
    return True, []


def current():
    """The effective policy (loads once on first use)."""
    if _STATE["policy"] is None:
        reload()
    return _STATE["policy"] or _builtin()


def last_error():
    return _STATE["error"]


def origins():
    return list(_STATE["origins"] or ["builtin"])


def enforce_flag():
    """M0: nothing reads the policy yet; M1/M2 flip individual switches."""
    return False


def resolve(subject=None, doc_kind=None):
    """Pick the first matching rule. No serving path calls this yet."""
    for rule in current().get("rules") or []:
        when = rule.get("when") or {}
        if when.get("subject") not in (None, subject):
            continue
        if when.get("doc_kind") not in (None, doc_kind):
            continue
        return rule
    return None


def _availability(ch):
    kind, addr = ch.get("kind"), str(ch.get("address") or "")
    if kind in ("local-file", "dataset-dir"):
        return "ready" if addr and os.path.exists(addr) else "missing"
    if kind == "rag-sqlite":
        path = sqlite_path(addr)
        return "ready" if path and os.path.exists(path) else "missing"
    return "unprobed"          # network channels are not probed


def channels():
    """Resolved channel view for diagnostics (never touches the network)."""
    out = []
    for ch in current().get("channels") or []:
        if not isinstance(ch, dict):
            continue
        kind = ch.get("kind")
        out.append({
            "source": ch.get("source"),
            "kind": kind,
            "address": ch.get("address"),
            "capabilities": sorted(CAPABILITIES.get(kind, set())),
            "prefer_when": ch.get("prefer_when") or "always",
            "auth_env": ch.get("auth_env"),
            "availability": _availability(ch),
            "options": ch.get("options") or {},
        })
    return out


# ── serving-path accessors (M1) ───────────────────────────────────────────────

#: pages.py speaks these source names; the policy uses logical source ids
PAGES_SOURCE = {"library": "library-pdf", "steadman": "steadman",
                "teubner_conte": "teubner-conte"}


class CapabilityMissing(RuntimeError):
    """A serving path needs a capability that no channel of that source provides."""

    def __init__(self, source, need, channels_):
        self.source = source
        self.need = sorted(need)
        self.channels = channels_
        have = ", ".join("%s:%s" % (c.get("kind"), _availability(c))
                         for c in channels_) or "none"
        super().__init__("source %r provides no channel with %s (channels: %s)"
                         % (source, ", ".join(self.need), have))

    def detail(self):
        return {
            "code": "capability_missing",
            "source": self.source,
            "need": self.need,
            "channels": [{"kind": c.get("kind"), "address": c.get("address"),
                          "availability": _availability(c)} for c in self.channels],
            "hint": "为该源增加一条提供该能力的通道，或改选其它源",
        }


def source_channels(source_id):
    return [c for c in (current().get("channels") or [])
            if isinstance(c, dict) and c.get("source") == source_id]


def capabilities(source_id):
    caps = set()
    for c in source_channels(source_id):
        caps |= CAPABILITIES.get(c.get("kind"), set())
    return caps


def require(source_id, *need):
    """Raise CapabilityMissing unless every capability is provided by a channel."""
    chans = source_channels(source_id)
    caps = capabilities(source_id)
    missing = set(need) - caps
    if missing:
        raise CapabilityMissing(source_id, missing, chans)
    return True


def tier_for_source(source_id):
    """Catalogue source id -> (tier, estimated) from the policy's source table.

    v2 rows carry ids such as `wikisource:zh`; the policy names the family, so
    the part before the first ':' is tried too. A source the policy does not
    describe reports `unknown`/estimated instead of an invented tier.
    """
    srcs = current().get("sources") or {}
    alias = PAGES_SOURCE.get(source_id, source_id)
    for cand in (alias, str(source_id or "").split(":", 1)[0]):
        meta = srcs.get(cand)
        if isinstance(meta, dict) and meta.get("tier"):
            return meta["tier"], bool(meta.get("tier_estimated", False))
    return "unknown", True


def enforced_parts():
    """Which parts of the serving path read the policy, per milestone."""
    return {"channels": True, "tier": True, "routing": True, "ranking": False}


# ── routing (M3) ─────────────────────────────────────────────────────────────

def _norm(text):
    """Casefold, strip diacritics, unify sigma: `Ἰλιάς` -> `ιλιασ`."""
    s = unicodedata.normalize("NFD", str(text or "").casefold())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.replace("ς", "σ").replace("ϲ", "σ")


def catalogue_of(source_id):
    """Which catalogue a logical source belongs to (v1 private / v2 public)."""
    meta = (current().get("sources") or {}).get(source_id) or {}
    return meta.get("catalogue")


def route(query):
    """Pick the routing rule for a query from the policy. No probing here.

    Rules are evaluated in order; the first hit wins. Matching is
    diacritic-insensitive, so a Greek work name reaches the same rule as its
    Latin transliteration (the old keyword table only had the Latin forms).
    """
    pol = current()
    markers = pol.get("markers") or {}
    conf = pol.get("routing") or {}
    q = _norm(query)
    for rule in conf.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        ref = rule.get("any_of")
        names = markers.get(ref, []) if isinstance(ref, str) else (ref or [])
        hit = any(_norm(name) and _norm(name) in q for name in names)
        if not hit and rule.get("regex"):
            try:
                hit = bool(re.search(str(rule["regex"]), str(query or "")))
            except re.error:
                hit = False
            limit = rule.get("max_query_len")
            if hit and limit and len(str(query or "").casefold()) > int(limit):
                hit = False
        if hit:
            return {"reason": rule.get("id") or "route",
                    "prefer": list(rule.get("prefer") or [])}
    return {"reason": "default",
            "prefer": list(conf.get("default_prefer") or [])}


def merge_plan(subject=None, doc_kind=None):
    """How to combine catalogue results, taken from the matching rule (M4).

    Weights are per catalogue: a rule names logical sources, so a catalogue's
    weight is the weight of the first of its sources in `cite` (see
    CITATION-POLICY-PLAN §1.6). `rrf` ignores weights entirely, which is why the
    default is numerically identical to the pre-M4 merge.
    """
    rule = resolve(subject, doc_kind) or {}
    conf = rule.get("merge") or {}
    mode = str(conf.get("mode") or "rrf")
    if mode not in MERGE_MODES:
        mode = "rrf"
    cite = list(rule.get("cite") or [])
    order = []
    for sid in cite:
        cat = catalogue_of(sid)
        if cat and cat not in order:
            order.append(cat)
    weights = {}
    if mode == "weighted":
        profile = ((current().get("weight_profiles") or {})
                   .get(rule.get("weight_profile")) or {})
        for sid in cite:
            cat = catalogue_of(sid)
            if cat and cat not in weights:
                weights[cat] = float(profile.get(sid, 1.0))
    return {"mode": mode, "cite": cite, "order": order,
            "anchor": order[0] if order else None, "weights": weights}


def local_roots():
    """pages source name -> local directory, taken from local-file channels."""
    roots = {}
    for pages_name, sid in PAGES_SOURCE.items():
        for c in source_channels(sid):
            if c.get("kind") == "local-file" and c.get("address"):
                roots[pages_name] = c["address"]
                break
    return roots


def sqlite_path(address):
    """`sqlite:///` + a database path (+ optional `#anchor`) -> the filesystem path.

    The triple slash is URI syntax, not a filesystem root: a POSIX path keeps
    its leading slash, a Windows drive letter loses the extra one.
    """
    a = str(address or "")
    if a.startswith("sqlite://"):
        a = a[len("sqlite://"):]
    a = a.split("#", 1)[0]
    if re.match(r"^/[A-Za-z]:", a):     # Windows keeps no leading slash
        a = a[1:]
    return a


def effective():
    """The /v1/policy payload: what is in force, and where each layer came from."""
    pol = current()
    return {
        "schema": SCHEMA,
        "policy_version": version(pol),
        "enforced": enforce_flag(),
        "enforced_parts": enforced_parts(),
        "note": "M3: routing, page roots, the render gate and the citation tier "
                "come from the policy; ranking still uses the existing merge. "
                "See docs/CITATION-POLICY-PLAN.md.",
        "origins": origins(),
        "last_reload_error": last_error(),
        "sources": pol.get("sources") or {},
        "channels": channels(),
        "weight_profiles": pol.get("weight_profiles") or {},
        "routing": {"rules": (pol.get("routing") or {}).get("rules") or [],
                    "default_prefer": (pol.get("routing") or {}).get("default_prefer") or []},
        "rules": pol.get("rules") or [],
    }
