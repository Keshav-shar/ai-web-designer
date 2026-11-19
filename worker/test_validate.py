"""python -m pytest worker/test_validate.py  (or: python worker/test_validate.py)"""
import validate as v

OK = {"assets/abc123abc123.webp"}


def errs(html, sid="hero"):
    return v.check(html, sid, OK)[1]


def test_clean_section_passes():
    html = ('<section id="hero" class="container-x py-24 bg-[var(--surface)]"><h1 class="font-heading '
            'text-[length:var(--fs-8)] text-[var(--text)]">Soft light</h1>'
            '<img src="assets/abc123abc123.webp" alt="pastel aurora gradient"><a class="btn btn-primary" '
            'href="#pricing">Start</a></section>')
    out, e = v.check(html, "hero", OK)
    assert e == [] and out.startswith('<section id="hero"')


def test_fences_are_stripped():
    assert errs('```html\n<section id="hero"><p>Hi</p></section>\n```') == []


def test_script_rejected():
    assert any("<script>" in x for x in errs('<section id="hero"><script>alert(1)</script></section>'))


def test_event_handler_rejected():
    assert any("event handler" in x for x in errs('<section id="hero"><a href="#a" onclick="x()">a</a></section>'))


def test_external_src_rejected():
    assert any("not one of the images" in x for x in errs('<section id="hero"><img src="https://x.io/a.png" alt="a"></section>'))


def test_external_link_and_js_rejected():
    assert errs('<section id="hero"><a href="https://evil.example">x</a></section>')
    assert errs('<section id="hero"><a href="javascript:alert(1)">x</a></section>')


def test_hex_and_named_colours_rejected():
    assert errs('<section id="hero" class="bg-pink-200">x</section>')
    assert errs('<section id="hero" class="md:text-white">x</section>')
    assert errs('<section id="hero" class="bg-[#ffccee]">x</section>')
    assert errs('<section id="hero" style="color:#fff">x</section>')
    assert errs('<section id="hero" style="background: rgb(1,2,3)">x</section>')


def test_theme_var_classes_allowed():
    assert errs('<section id="hero" class="text-[var(--text)] from-[var(--visual-1)] md:bg-[var(--surface)]/60">x</section>') == []


def test_wrong_id_and_extra_root_rejected():
    assert errs('<section id="other">x</section>')
    # chatter after the last </section> is trimmed by strip_fences; a second root between sections is not
    assert errs('<section id="hero">x</section><div>y</div><section id="hero">z</section>')


def test_trailing_chatter_is_trimmed():
    out, e = v.check('Here you go:\n<section id="hero">x</section>\nHope this helps!', "hero", OK)
    assert e == [] and out == '<section id="hero">x</section>'


def test_missing_alt_and_placeholder_rejected():
    assert errs('<section id="hero"><img src="assets/abc123abc123.webp"></section>')
    assert errs('<section id="hero"><p>Lorem ipsum dolor</p></section>')


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok  ", name)
            except AssertionError:
                fails += 1
                print("FAIL", name)
    sys.exit(1 if fails else 0)
