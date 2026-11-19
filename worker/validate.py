"""validate.py - check one model-written <section> against contracts/prompts/section.md's hard rules.

check(html, section_id, allowed_srcs) -> (clean_html | None, errors). Rejected output is retried with the errors,
then replaced by a fallback; nothing that fails here reaches a page.
"""
from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

BANNED_TAGS = {"script", "style", "iframe", "object", "embed", "link", "meta", "base", "frame", "frameset",
               "applet", "noscript", "template", "portal"}
VOID = {"area", "br", "col", "hr", "img", "input", "source", "track", "wbr"}
COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(rgb|rgba|hsl|hsla|oklch|oklab|lab|lch)\s*\(", re.I)
NAMED_COLOR_CLASS = re.compile(
    r"(?<![\w-])(?:[a-z0-9]+:)*(bg|text|border|from|via|to|ring|fill|stroke|shadow|outline|decoration|divide|"
    r"placeholder|caret|accent)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|"
    r"cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)(-\d{2,3})?(/\d+)?(?![\w-])")
ARBITRARY_HEX = re.compile(r"\[[^\]]*#[0-9a-fA-F]{3,8}[^\]]*\]")
URL_IN_STYLE = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.I)


class _P(HTMLParser):
    def __init__(self, allowed: set[str]):
        super().__init__(convert_charrefs=True)
        self.allowed = allowed
        self.errors: list[str] = []
        self.out: list[str] = []
        self.stack: list[str] = []
        self.roots: list[tuple[str, dict]] = []
        self.skip = 0                                # depth inside a banned element (dropped from output)
        self.text_outside = False

    def _attrs(self, tag, attrs):
        keep = []
        for k, v in attrs:
            k = k.lower()
            v = v or ""
            if k.startswith("on"):
                self.errors.append(f"<{tag}> has an event handler attribute '{k}'")
                continue
            if k in ("srcset", "formaction", "xlink:href", "ping", "background", "poster"):
                self.errors.append(f"<{tag}> uses a banned attribute '{k}'")
                continue
            if k == "src":
                if v not in self.allowed:
                    self.errors.append(f"<{tag}> src '{v[:60]}' is not one of the images you may use")
                    continue
            if k == "href":
                if v.strip().lower().startswith("javascript:") or not (v.startswith("#") or v.startswith("mailto:")):
                    self.errors.append(f"link '{v[:60]}' is not an in-page anchor or mailto:")
                    v = "#"
            if k == "action" and v not in ("", "#"):
                self.errors.append(f"form action '{v[:60]}' must be '#'")
                v = "#"
            if k == "style":
                if COLOR_LITERAL.search(v):
                    self.errors.append(f"inline style uses a literal colour ('{COLOR_LITERAL.search(v).group(0)}'); use var(--...)")
                for u in URL_IN_STYLE.findall(v):
                    if u not in self.allowed:
                        self.errors.append(f"style url('{u[:60]}') is not an allowed image")
                if re.search(r"expression\(|@import|javascript:", v, re.I):
                    self.errors.append("inline style contains a banned construct")
                    continue
            if k == "class":
                m = NAMED_COLOR_CLASS.search(v) or ARBITRARY_HEX.search(v)
                if m:
                    self.errors.append(f"class '{m.group(0)}' hard-codes a colour; use the theme variables")
            keep.append((k, v))
        return keep

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.skip or tag in BANNED_TAGS:
            if not self.skip:
                self.errors.append(f"<{tag}> is not allowed")
            if tag not in VOID:
                self.skip += 1
            return
        attrs = self._attrs(tag, attrs)
        if not self.stack:
            self.roots.append((tag, dict(attrs)))
        if tag == "img" and not dict(attrs).get("alt", "").strip():
            self.errors.append("an <img> has no descriptive alt text")
        self.out.append(f"<{tag}" + "".join(f' {k}="{escape(v, quote=True)}"' for k, v in attrs) + ">")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID and not self.skip and self.stack and self.stack[-1] == tag.lower():
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip:
            if tag not in VOID:
                self.skip -= 1
            return
        if tag in VOID:
            return
        if tag in self.stack:
            while self.stack:
                t = self.stack.pop()
                self.out.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data):
        if self.skip:
            return
        if not self.stack and data.strip():
            self.text_outside = True
            return
        self.out.append(escape(data, quote=False))

    def handle_comment(self, data):
        pass


def strip_fences(text: str) -> str:
    t = text.strip()
    m = re.search(r"```(?:html)?\s*(.*?)```", t, re.S | re.I)
    if m:
        t = m.group(1).strip()
    i = t.lower().find("<section")
    j = t.lower().rfind("</section>")
    return t[i:j + len("</section>")] if i >= 0 and j > i else t


def check(html: str, section_id: str, allowed_srcs: set[str]) -> tuple[str | None, list[str]]:
    p = _P(allowed_srcs)
    p.feed(strip_fences(html))
    p.close()
    while p.stack:
        p.out.append(f"</{p.stack.pop()}>")
    errs = list(dict.fromkeys(p.errors))
    if len(p.roots) != 1 or p.roots[0][0] != "section":
        errs.append(f"expected exactly one root <section>, got {[r[0] for r in p.roots] or 'nothing'}")
    elif p.roots[0][1].get("id") != section_id:
        errs.append(f'root <section> must have id="{section_id}"')
    if p.text_outside:
        errs.append("text outside the <section> element")
    body = "".join(p.out)
    if re.search(r"lorem ipsum|\[placeholder\]", body, re.I):
        errs.append("placeholder copy (lorem ipsum / [placeholder])")
    return (None if errs else body), errs
