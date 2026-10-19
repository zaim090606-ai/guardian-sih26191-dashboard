import palette
from ui import theme


def test_css_has_editorial_tokens_and_pinned_fonts():
    css = theme.build_css()
    for token in ("#FAF6EE", "#14213D", "#A8782A", "Cormorant Garamond", "Inter"):
        assert token in css
    assert theme.FONTS_URL.startswith("https://fonts.googleapis.com/")


def test_css_hides_chrome_keeps_sidebar_and_honours_reduced_motion():
    css = theme.build_css()
    assert "stFooter" in css and "stDecoration" in css
    assert "stSidebarCollapsedControl" not in css and "stExpandSidebarButton" not in css
    reduced = css[css.index("@media (prefers-reduced-motion"):]
    assert "animation:none" in reduced and "transition:none" in reduced
    assert "::selection" in css and "scrollbar" in css and "gd-pill-immediate" in css


def test_overview_steps_html_has_three_inline_svg_cards_and_no_emoji():
    import ui_overview
    html = ui_overview.steps_html()
    assert html.count('class="gd-step"') == 3 and html.count("<svg") == 3
    assert all(ord(ch) < 0x2190 for ch in html)


def test_tier_colors_readable_on_ivory():
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    for color in (palette.RED, palette.AMBER, palette.GREEN):
        assert (lum(theme.IVORY) + 0.05) / (lum(color) + 0.05) >= 4.5
