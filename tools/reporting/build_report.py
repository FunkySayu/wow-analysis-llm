#!/usr/bin/env python3
r"""Template + bundle + payload -> one self-contained report HTML.

    python3 tools/warcraftlogs/run.py mage -r <REPORT> -a <ACTOR> -f raid --json -o scratch/mage.json
    cd tools/reporting && npm run build
    python3 tools/reporting/build_report.py scratch/mage.json -o reports/arcane_barrage.html \
        --title "Arcane Barrage audit" --subtitle "Funkywand, Venomous Abyss, 14 pulls"

Written in Python rather than PowerShell on purpose. The PowerShell build scripts
this replaces had to remember `.Replace()` over `-replace`, because `-replace`
treats the payload as a regex and silently mangles every `$` and `\` in a 160 KB
JS bundle (.claude/knowledge/method/building-reports.md). `str.replace` has no such
edge, and this runs the same under WSL, Git Bash and PowerShell.

Every substitution is literal and every one is verified afterwards - the failure
mode being guarded against is not a crash, it is a report that opens fine and is
subtly wrong.
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATE = os.path.join(ROOT, "reports", "_checks_template.html")
BUNDLE = os.path.join(ROOT, "tools", "reporting", "dist", "viz.iife.js")

PLACEHOLDERS = ("<!--TITLE-->", "<!--SUBTITLE-->", "<!--INTRO-->",
                "/*VIZBUNDLE*/", "/*PAYLOAD*/")


def read(path, what):
    if not os.path.exists(path):
        sys.exit(f"no {what} at {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def escape_json(text):
    """JSON text -> safe to sit inside a <script> element.

    An HTML parser ends a script at the first literal `</script`, wherever it
    occurs - including inside a JSON string - and `<!--` opens a comment in a
    classic script. Both would truncate the page. `<` can only appear inside a
    JSON *string*, and `\\u003c` is that same character to any JSON parser, so
    escaping every one of them is both sufficient and lossless.
    """
    return text.replace("<", "\\u003c")


SCRIPT_END = re.compile(r"</(?=script)", re.I)


def escape_bundle(js):
    """Same problem, but the bundle is JS source, not a JSON string.

    A blanket `</` -> `<\\/` would corrupt real JS (`a < /re/` is a comparison
    against a regex literal), so only the exact `</script` sequence is split -
    which in valid JS can only occur inside a string, a template or a regex,
    where the extra backslash is inert. `<!--` has no safe rewrite in source
    position, so it is rejected rather than mangled; nothing esbuild emits
    contains it, and if that ever changes it should fail loudly here.
    """
    if "<!--" in js:
        sys.exit("the bundle contains `<!--`, which opens a comment inside a "
                 "<script> - it cannot be inlined safely")
    return SCRIPT_END.sub("<\\\\/", js)


def build(payload_path, out_path, title, subtitle, intro_path=None,
          template_path=TEMPLATE, bundle_path=BUNDLE):
    html = read(template_path, "template")
    bundle = read(bundle_path, "bundle (run `npm run build` in tools/reporting first)")
    raw = read(payload_path, "payload")

    payload = json.loads(raw)                       # fail here, not in the browser
    checks = payload.get("checks", [])
    if not checks:
        print("warning: payload has no checks in it", file=sys.stderr)

    intro = read(intro_path, "intro") if intro_path else ""
    if not subtitle:
        ctx = payload.get("context") or {}
        subtitle = (f"{ctx.get('actor')} · report {ctx.get('report')} · "
                    f"{len(ctx.get('fights') or [])} fight(s) "
                    f"[{ctx.get('selector')}] · generated {payload.get('generated')}")

    for token, value in (("<!--TITLE-->", title),
                         ("<!--SUBTITLE-->", subtitle),
                         ("<!--INTRO-->", intro),
                         ("/*VIZBUNDLE*/", escape_bundle(bundle)),
                         # Compact, so the payload is exactly one line and can be
                         # validated by reading that line.
                         ("/*PAYLOAD*/", escape_json(
                             json.dumps(payload, separators=(",", ":"))))):
        html = html.replace(token, value)

    # --- validation: cheap, and each of these has caught a real bug ------------
    left = [p for p in PLACEHOLDERS if p in html]
    if left:
        sys.exit(f"placeholder(s) survived into the output: {', '.join(left)}")
    m = re.search(r"^\s*const PAYLOAD = (.+);$", html, re.M)
    if not m:
        sys.exit("could not find the `const PAYLOAD = ...;` line in the output")
    try:
        embedded = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        sys.exit(f"the embedded payload is not valid JSON: {exc}")
    if [c["id"] for c in embedded.get("checks", [])] != [c["id"] for c in checks]:
        sys.exit("the embedded payload does not round-trip to the source payload")
    if "WCLViz.render(" not in html or "var WCLViz" not in html:
        sys.exit("the bundle does not define WCLViz - is dist/viz.iife.js current?")
    # One `</script` too many means an escape was missed, and the browser
    # truncates the page from that point on - silently, with no error anywhere.
    expected = len(SCRIPT_END.findall(read(template_path, "template")))
    if len(SCRIPT_END.findall(html)) != expected:
        sys.exit(f"expected {expected} `</script` in the output, found "
                 f"{len(SCRIPT_END.findall(html))} - an escape was missed")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print(f"wrote {out_path}  ({len(html) / 1024:.0f} KB, "
          f"{len(checks)} check(s): {', '.join(c['id'] for c in checks)})")
    unported = payload.get("unported") or []
    if unported:
        print(f"  text-only, not in this report: {', '.join(unported)}")
    return out_path


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("payload", help="JSON written by `run.py ... --json`")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--title", default="Log check report")
    p.add_argument("--subtitle", default="", help="defaults to the payload's own context line")
    p.add_argument("--intro", help="path to an HTML fragment for the intro block")
    p.add_argument("--template", default=TEMPLATE)
    p.add_argument("--bundle", default=BUNDLE)
    a = p.parse_args()
    build(a.payload, a.out, a.title, a.subtitle, a.intro, a.template, a.bundle)


if __name__ == "__main__":
    main()
