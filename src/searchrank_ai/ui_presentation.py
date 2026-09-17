"""Presentation only: escaped cards, safe catalogue links, and a storefront theme."""

from html import escape
from urllib.parse import urlsplit


def safe_url(value: object, *, image: bool = False) -> str | None:
    """Allow only the adopted catalogue's public HTTPS hosts."""
    if not isinstance(value, str) or any(ord(char) < 33 for char in value):
        return None
    try:
        url = urlsplit(value)
        hosts = (
            {"www.91-img.com", "91-img.com"} if image else {"www.91mobiles.com", "91mobiles.com"}
        )
        if (
            url.scheme == "https"
            and url.hostname in hosts
            and not url.username
            and not url.password
            and url.port in (None, 443)
        ):
            return value
    except ValueError:
        pass
    return None


def display_value(value: object, suffix: str = "") -> str:
    if value is None or value == "":
        return "Not available"
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return f"{value:g}{suffix}"
    return str(value) + suffix


def card_html(item: dict, image_url: str | None = None) -> str:
    """Escape all catalogue data; no model prose enters this HTML template."""
    name = escape(str(item["product_name"]))
    url = safe_url(image_url, image=True)
    art = (
        f'<img src="{escape(url, quote=True)}" alt="{name}" loading="lazy" '
        'referrerpolicy="no-referrer">'
        if url
        else '<span class="sr-no-image">Catalogue image<br>not available</span>'
    )
    rating = display_value(item.get("user_rating_5"), " / 5")
    return (
        f'<article class="sr-card"><div class="sr-art">{art}</div>'
        f'<div class="sr-brand-label">{escape(str(item["brand"]))}</div><h3>{name}</h3>'
        f'<div class="sr-price">₹{item["price_inr"]:,}</div>'
        '<div class="sr-price-note">Catalogue price · not a live offer</div>'
        '<div class="sr-specs">'
        f"<span>{escape(display_value(item['ram_gb']))} GB RAM</span>"
        f"<span>{escape(display_value(item['storage_gb']))} GB storage</span></div>"
        f'<div class="sr-rating">User rating <strong>{escape(rating)}</strong></div></article>'
    )


STYLE = """
<style>
:root { color-scheme:light; }
.stApp { background:#f5f7fb; color:#162235; }
[data-testid="stHeader"] { background:#f5f7fb; }
.block-container { max-width:1240px; padding-top:4.5rem; padding-bottom:3rem; }
.stApp h1 { font-size:clamp(2rem,4vw,3.25rem); letter-spacing:-.045em;
  line-height:1.12; color:#142238; font-weight:750; padding-top:.5rem; }
.stApp h2 { font-size:1.55rem; letter-spacing:-.025em; }
.stApp h3 { font-size:1.15rem; }
.stApp p,.stApp label { font-size:1rem; }
.stApp [data-testid="stCaptionContainer"] p { color:#526179; font-size:.875rem; }
.sr-masthead { display:flex; align-items:center; justify-content:space-between; gap:1rem;
  border-bottom:1px solid #dce3ef; padding:.25rem 0 1.25rem; margin-bottom:1.4rem; }
.sr-logo { font-size:1.35rem; font-weight:800; letter-spacing:-.04em; }
.sr-logo span { color:#205ce4; }
.sr-edition { font-size:.875rem; color:#526179; }
.sr-eyebrow { color:#205ce4; font-size:.8rem; font-weight:750; letter-spacing:.12em; }
.sr-intro { color:#526179; font-size:1.05rem; max-width:44rem; margin-bottom:1rem; }
[data-testid="stTabs"] [role="tablist"] { gap:1.6rem; border-bottom:1px solid #dce3ef; }
[data-testid="stTabs"] [role="tab"] { font-weight:650; padding:.75rem .1rem; }
[data-testid="stTabs"] [aria-selected="true"] { color:#205ce4; }
[data-testid="stForm"] { background:#fff; border:1px solid #dce3ef; border-radius:16px; }
.stApp button[kind="primary"] { background:#205ce4; border-color:#205ce4;
  color:white; border-radius:10px; font-weight:650; }
.stApp button:focus-visible,.stApp a:focus-visible {
  outline:3px solid #205ce4; outline-offset:3px; }
.stApp [data-testid="stTextInput"] input,.stApp [data-testid="stTextArea"] textarea {
  color:#162235; }
.stApp [data-testid="stVerticalBlockBorderWrapper"] > div { border-radius:16px; }
.sr-card { color:#162235; overflow-wrap:anywhere; }
.sr-art { height:170px; background:#fff; border-radius:12px; display:flex;
  align-items:center; justify-content:center; margin-bottom:1rem; }
.sr-art img { max-height:150px; max-width:90%; object-fit:contain; font-size:.875rem; }
.sr-no-image { color:#69788e; font-size:.875rem; text-align:center; line-height:1.6; }
.sr-brand-label { color:#526179; text-transform:uppercase; font-size:.75rem;
  letter-spacing:.09em; font-weight:700; }
.sr-card h3 { font-size:1.08rem; line-height:1.45; font-weight:650;
  min-height:3.15rem; margin:.35rem 0 .8rem; padding:0; }
.sr-price { font-size:1.8rem; font-weight:750; letter-spacing:-.045em; }
.sr-price-note { color:#526179; font-size:.75rem; margin:.1rem 0 1rem; }
.sr-specs { display:flex; flex-wrap:wrap; gap:.4rem; }
.sr-specs span { background:#edf2fb; padding:.35rem .55rem; border-radius:6px; font-size:.875rem; }
.sr-rating { display:flex; justify-content:space-between; gap:.5rem; font-size:.875rem;
  border-top:1px solid #e3e9f2; margin-top:1rem; padding:.8rem 0 .25rem; }
.sr-empty { border:1px dashed #becbe0; border-radius:16px; padding:2rem;
  background:#fff; margin:1rem 0; }
.sr-empty h3 { margin:0 0 .5rem; font-size:1.2rem; }
.sr-empty p { margin:0; color:#526179; }
.sr-footer { border-top:1px solid #dce3ef; color:#526179; padding-top:1.2rem;
  font-size:.8rem; margin-top:2rem; }
.sr-compare-wrap { overflow-x:auto; border:1px solid #dce3ef; border-radius:12px; }
.sr-compare { border-collapse:collapse; width:100%; background:white; font-size:.95rem; }
.sr-compare caption { text-align:left; padding:1rem; font-weight:650; }
.sr-compare th,.sr-compare td { border-bottom:1px solid #e3e9f2; text-align:left;
  padding:.9rem 1rem; min-width:140px; vertical-align:top; overflow-wrap:anywhere; }
.sr-compare thead th { background:#eaf0fc; color:#162235; }
.sr-compare tbody th { color:#526179; font-weight:500; }
@media(max-width:700px) {
  .block-container { padding:4.5rem 1rem 2rem; }
  .sr-edition { max-width:9rem; text-align:right; }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.75rem; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    width:100%!important; flex:1 1 100%!important; min-width:0!important; }
  .sr-card h3 { min-height:0; } .sr-art { height:150px; }
  [data-testid="stTabs"] [role="tablist"] { gap:1rem; }
}
</style>
"""
