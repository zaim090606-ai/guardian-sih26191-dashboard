import palette
from ui import theme


def test_css_has_editorial_tokens_and_pinned_fonts():
    css = theme.build_css()
    for token in ("#FAF6EE", "#14213D", "#A8782A", "Cormorant Garamond", "Inter"):
        assert token in css
    assert theme.FONTS_URL.startswith("https://fonts.googleapis.com/")


def test_tier_colors_readable_on_ivory():
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    for color in (palette.RED, palette.AMBER, palette.GREEN):
        assert (lum(theme.IVORY) + 0.05) / (lum(color) + 0.05) >= 4.5
