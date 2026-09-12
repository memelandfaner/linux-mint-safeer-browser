"""EasyList network rules -> WebKit content blocker JSON (WebKitUserContentFilterStore, Safari format).

Source of truth: clients/python/safeer_webkit_filters.py in safeer-threat-intel; Safeer Browser for Linux ships
an identical copy as core/webkit_filters.py.

What is converted: ||host^ anchors, |start and end| anchors, * wildcards, ^ separators, @@ exceptions
(ignore-previous-rules), third-party / first-party, domain= (if-domain or unless-domain, never both), the
resource types, $document exceptions (the whole page) and $important (emitted after the exceptions so they
win). WebKit's rule compiler accepts only a small regex subset (no alternation, no lookaround, no \d-style
classes), so the generated url-filters use just ^ $ . * + ? [] and quantified groups, the forms AdGuard's
Safari converter has used for years. /regex/ rules, cosmetic rules and options the content blocker cannot
express (redirect, csp, removeparam, rewrite, popup ...) are skipped, never guessed.

Rule order matters to WebKit: ignore-previous-rules only cancels rules that came before it, so the output is
blocks, then exceptions, then important blocks, then one allow-everything rule for the real banks' domains.
"""

from __future__ import annotations

import json
import re

TYPE_MAP = {
    "script": "script", "image": "image", "stylesheet": "style-sheet", "font": "font", "media": "media",
    "object": "media", "xmlhttprequest": "raw", "subdocument": "document", "websocket": "raw",
    "ping": "raw", "other": "raw", "xhr": "raw", "css": "style-sheet", "frame": "document",
}
ALL_TYPES = ("document", "image", "style-sheet", "script", "font", "raw", "svg-document", "media")
_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
_DOMAIN_OPTION = re.compile(r"^[a-z0-9.-]+$")
# ABP "^" = a character that is not a letter, digit or one of _ - . % (or the end of the address). WebKit has
# no alternation, so: inside a pattern a separator character; at the end of a pattern "separator then anything,
# or the end" as an optional group with the $ anchor.
SEPARATOR_CLASS = "[/:?=&#;,+@!~]"
SEPARATOR_AT_END = "(" + SEPARATOR_CLASS + ".*)?$"
HOST_PREFIX = "^[a-z][a-z0-9+.-]*://([a-z0-9-]+\\.)*"


def _escape(text: str) -> str:
    return re.sub(r"([.+?(){}\[\]\\$^|*])", r"\\\1", text)


def abp_to_regex(pattern: str) -> str | None:
    """Adblock Plus pattern -> regex for url-filter (case-insensitive by default in WebKit)."""
    p = pattern
    out = ""
    if p.startswith("||"):
        out = HOST_PREFIX
        p = p[2:]
    elif p.startswith("|"):
        out = "^"
        p = p[1:]
    end = False
    if p.endswith("|"):
        end = True
        p = p[:-1]
    if p in ("", "*"):
        if not out and not end:
            return None
        return out + ".*" + ("$" if end else "")
    if any(ord(ch) > 126 or ord(ch) < 32 for ch in p):
        return None  # WebKit url-filters are ASCII only
    last = len(p) - 1
    for i, ch in enumerate(p):
        if ch == "*":
            out += ".*"
        elif ch == "^":
            out += SEPARATOR_AT_END if i == last and not end else SEPARATOR_CLASS
        else:
            out += _escape(ch)
    if end and not out.endswith("$"):
        out += "$"
    return out


def parse_rule(line: str):
    """One network rule -> (trigger, action) or None (comment, cosmetic, unsupported)."""
    line = line.strip()
    if not line or line[0] in "![" or "##" in line or "#@#" in line or "#?#" in line or "#$#" in line or "#%#" in line:
        return None
    exception = line.startswith("@@")
    if exception:
        line = line[2:]
    regex_rule = len(line) > 2 and line.startswith("/") and (line.endswith("/") or "/$" in line)
    if regex_rule:
        cut = line.rfind("/$")
        pattern, options = (line[:cut + 1], line[cut + 2:]) if cut > 0 else (line, "")
    else:
        cut = line.rfind("$")
        pattern, options = (line[:cut], line[cut + 1:]) if cut > 0 else (line, "")
    types, negated_types = [], []
    load_type = None
    important = False
    if_domain, unless_domain = [], []
    document_only = False
    for option in ([o for o in options.split(",") if o] if options else []):
        negated = option.startswith("~")
        name = option[1:] if negated else option
        lname = name.lower()
        if lname in ("third-party", "3p"):
            load_type = "first-party" if negated else "third-party"
        elif lname in ("first-party", "1p"):
            load_type = "third-party" if negated else "first-party"
        elif lname == "important":
            important = True
        elif lname in ("match-case", "generichide", "genericblock", "elemhide", "ghide", "ehide"):
            continue
        elif lname.startswith("domain="):
            for d in lname[7:].split("|"):
                if d.startswith("~"):
                    unless_domain.append(d[1:])
                elif d:
                    if_domain.append(d)
        elif lname in ("document", "doc"):
            if negated:
                return None
            document_only = True
        elif lname in TYPE_MAP:
            (negated_types if negated else types).append(TYPE_MAP[lname])
        else:
            return None  # redirect=, csp=, removeparam=, rewrite=, popup, header= ...
    if if_domain and unless_domain:
        return None  # WebKit allows one of if-domain / unless-domain per rule
    if any(not _DOMAIN_OPTION.match(d) for d in if_domain + unless_domain):
        return None
    if document_only and not exception:
        return None  # blocking whole pages is not a job for the ad list
    if regex_rule:
        return None  # WebKit's regex subset is too small to take arbitrary /regex/ rules safely
    url_filter = abp_to_regex(pattern.lower())
    if url_filter is None:
        return None
    resource_types = sorted({t for t in types} - set(negated_types)) if types else None
    if not types and negated_types:
        resource_types = sorted(set(ALL_TYPES) - set(negated_types) - {"document"})
    if resource_types == []:
        return None
    trigger = {"url-filter": url_filter}
    if resource_types is not None:
        trigger["resource-type"] = resource_types
    elif not exception or not document_only:
        # a rule without a type applies to every request except the page itself (ABP semantics)
        trigger["resource-type"] = [t for t in ALL_TYPES if t != "document"]
    if load_type:
        trigger["load-type"] = [load_type]
    if if_domain:
        trigger["if-domain"] = ["*" + d for d in if_domain]
    if unless_domain:
        trigger["unless-domain"] = ["*" + d for d in unless_domain]
    if document_only:
        # @@||site^$document: everything on that page is allowed
        host = pattern.lower().lstrip("|").rstrip("^/")
        if pattern.lower().startswith("||") and _HOST.match(host):
            trigger = {"url-filter": ".*", "if-domain": ["*" + host]}
        else:
            trigger.pop("resource-type", None)
            trigger["resource-type"] = list(ALL_TYPES)
    action = {"type": "ignore-previous-rules" if exception else "block"}
    return {"trigger": trigger, "action": action, "_important": important and not exception}


def convert(lines, never_block_domains=(), max_rules: int = 150000) -> list:
    """EasyList lines -> ordered WebKit content blocker rules (blocks, exceptions, important, bank allowance)."""
    blocks, exceptions, important = [], [], []
    for line in lines:
        rule = parse_rule(line)
        if rule is None:
            continue
        flag = rule.pop("_important")
        if rule["action"]["type"] == "ignore-previous-rules":
            exceptions.append(rule)
        elif flag:
            important.append(rule)
        else:
            blocks.append(rule)
    rules = blocks + exceptions + important
    domains = sorted({d.lower().strip(".") for d in never_block_domains if d})
    if domains:
        rules.append({"trigger": {"url-filter": ".*", "if-domain": ["*" + d for d in domains]},
                      "action": {"type": "ignore-previous-rules"}})
    return rules[:max_rules]


def to_json(rules) -> str:
    return json.dumps(rules, ensure_ascii=True, separators=(",", ":"))
