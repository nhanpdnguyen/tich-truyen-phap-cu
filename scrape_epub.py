#!/usr/bin/env python3
"""Scrape Tích truyện Pháp Cú from budsas.org and produce an EPUB."""

import base64
import os
import re
import time
import requests
from bs4 import BeautifulSoup, Tag
from ebooklib import epub
from weasyprint import HTML as WeasyprintHTML

BASE_URL = "https://www.budsas.org/uni/u-kinh-phapcu-ev/ttpc{}.htm"
OUTLINE_URL = "https://www.budsas.org/uni/u-kinh-phapcu-ev/ttpc00.htm"
RAW_HTML_DIR = "raw_htmls"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

CHAPTERS = [
    ("I. Phẩm Song Yếu",               ["01a", "01b", "01c", "01d"]),
    ("II. Phẩm Không Phóng Dật",        ["02a", "02b"]),
    ("III. Phẩm Tâm",                   ["03"]),
    ("IV. Phẩm Hoa",                    ["04a", "04b"]),
    ("V. Phẩm Ngu",                     ["05a", "05b"]),
    ("VI. Phẩm Hiền Trí",               ["06"]),
    ("VII. Phẩm A La Hán",              ["07"]),
    ("VIII. Phẩm Ngàn",                 ["08"]),
    ("IX. Phẩm Ác",                     ["09"]),
    ("X. Phẩm Hình Phạt",              ["10"]),
    ("XI. Phẩm Già",                    ["11"]),
    ("XII. Phẩm Tự Ngã",               ["12"]),
    ("XIII. Phẩm Thế Gian",            ["13"]),
    ("XIV. Phẩm Phật",                  ["14"]),
    ("XV. Phẩm Hạnh Phúc",             ["15"]),
    ("XVI. Phẩm Hỷ Ái",                ["16"]),
    ("XVII. Phẩm Sân Hận",             ["17"]),
    ("XVIII. Phẩm Cấu Uế",             ["18"]),
    ("XIX. Phẩm Công Bình Pháp Trụ",   ["19"]),
    ("XX. Phẩm Đạo",                   ["20"]),
    ("XXI. Phẩm Tạp Lục",              ["21"]),
    ("XXII. Phẩm Địa Ngục",            ["22"]),
    ("XXIII. Phẩm Voi",                ["23"]),
    ("XXIV. Phẩm Tham Ái",             ["24"]),
    ("XXV. Phẩm Tỳ Kheo",              ["25"]),
    ("XXVI. Phẩm Bà La Môn",           ["26a", "26b", "26c"]),
]

PDF_CSS = """
@page {
    margin: 2cm 2.5cm;
    @bottom-center {
        content: counter(page);
        font-size: 0.8em;
        color: #666;
    }
}
body {
    font-family: serif;
    font-size: 11pt;
    line-height: 1.7;
}
.bold { font-weight: bold; }
.italic { font-style: italic; }
p { margin: 0.4em 0; text-align: justify; }
blockquote { margin: 0.8em 2em; }
h1 {
    font-size: 1.8em;
    color: #8b0000;
    text-align: center;
    margin: 2em 0 0.5em;
    page-break-before: always;
}
h2 {
    font-size: 1.4em;
    color: #8b0000;
    text-align: center;
    margin: 1.5em 0 0.5em;
    page-break-before: always;
}
.cover-page {
    text-align: center;
    page-break-after: always;
    margin-top: 30%;
}
.cover-page img {
    max-width: 100%;
    max-height: 90vh;
}
"""

CSS = """
body {
    font-family: serif;
    font-size: 1em;
    line-height: 1.6;
    margin: 1em 1.5em;
}
.bold { font-weight: bold; }
.italic { font-style: italic; }
p { margin: 0.5em 0; text-align: justify; }
blockquote { margin: 1em 2em; }
"""

# CSS properties worth preserving from inline styles
KEEP_STYLE_PROPS = {"color", "font-weight", "font-style", "text-align"}


def fetch_html(url: str) -> str:
    print(f"  Fetching {url} ...", end=" ", flush=True)
    for attempt in range(5):
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"429, retrying in {wait}s...", end=" ", flush=True)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        resp.encoding = "utf-8"
        print(f"{resp.status_code}")
        return resp.text
    resp.raise_for_status()
    return resp.text


def cache_path(page_id: str) -> str:
    """Return the local cache file path for a given page_id (e.g. '01a' or '00')."""
    return os.path.join(RAW_HTML_DIR, f"ttpc{page_id}.html")


def fetch_html_cached(page_id: str, url: str) -> str:
    """Return HTML from local cache if available, otherwise fetch and cache it."""
    path = cache_path(page_id)
    if os.path.exists(path):
        print(f"  Cache hit: {path}")
        with open(path, encoding="utf-8") as f:
            return f.read()
    html = fetch_html(url)
    os.makedirs(RAW_HTML_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return html


def clean_inline_style(style_str: str) -> str:
    """Strip MS Office / font-size noise, keep color, font-weight, font-style, text-align."""
    if not style_str:
        return ""
    props = {}
    for item in style_str.split(";"):
        item = item.strip()
        if ":" not in item:
            continue
        prop, _, val = item.partition(":")
        prop = prop.strip().lower()
        val = val.strip()
        if prop in KEEP_STYLE_PROPS and val:
            props[prop] = val
    return "; ".join(f"{k}: {v}" for k, v in props.items())


def sanitize_tag(tag: Tag) -> None:
    """In-place: remove noisy attributes, clean inline styles, drop <o:p>."""
    # Remove <o:p> MS Word tags
    for op in tag.find_all("o:p"):
        op.decompose()

    for el in tag.find_all(True):
        # Drop all attributes except a known safe set
        keep = {}
        if "style" in el.attrs:
            cleaned = clean_inline_style(el["style"])
            if cleaned:
                keep["style"] = cleaned
        if "class" in el.attrs:
            # Keep only 'bold' and 'italic' classes
            classes = [c for c in el["class"] if c in ("bold", "italic")]
            if classes:
                keep["class"] = classes
        if el.name == "a" and "href" in el.attrs:
            keep["href"] = el["href"]
        if el.name == "img":
            keep["src"] = el.get("src", "")
            keep["alt"] = el.get("alt", "")
        if el.name in ("p", "div") and "align" in el.attrs:
            keep["style"] = keep.get("style", "") + "; text-align: " + el["align"]
            keep["style"] = keep["style"].lstrip("; ")
        el.attrs = keep


def remove_nav_and_chrome(main: Tag) -> None:
    """Remove header table, <hr>s, book-title block, nav bar, footer."""
    # Header table (first <table>)
    first_table = main.find("table")
    if first_table:
        first_table.decompose()

    # All <hr> tags
    for hr in main.find_all("hr"):
        hr.decompose()

    # Book-title paragraph (contains "Tích truyện Pháp Cú" with maroon color)
    for p in main.find_all("p"):
        style = " ".join(
            s.get("style", "") for s in ([p] + p.find_all(style=True))
        )
        if "maroon" in style and "Tích truyện Pháp Cú" in p.get_text():
            p.decompose()
            break

    # Navigation paragraph (contains "Ðầu trang" / "Đầu trang")
    for p in main.find_all("p"):
        t = p.get_text()
        if ("Ðầu trang" in t or "Đầu trang" in t) and "Mục lục" in t:
            p.decompose()

    # Footer links + timestamp
    for p in main.find_all("p"):
        t = p.get_text()
        if "Trở về trang Thư Mục" in t or "updated:" in t.lower():
            p.decompose()

    # Extra footer link paragraphs (e.g. "Các bản kinh Pháp Cú khác")
    for p in main.find_all("p"):
        if p.find("a") and "Các bản kinh" in p.get_text():
            p.decompose()

    # "Chân thành cám ơn" acknowledgement line
    for p in main.find_all("p"):
        if "Chân thành cám ơn" in p.get_text():
            p.decompose()

    # Dividers like "--ooOoo--" or "-ooOoo-"
    for p in main.find_all("p"):
        t = p.get_text().strip()
        if re.fullmatch(r"[-\s]*o+O+o+[-\s]*", t):
            p.decompose()


def detect_and_anchor_stories(main: Tag, chapter_idx: int, story_offset: int = 0) -> list[tuple[str, str]]:
    """
    Find story-title <p> elements, add id anchors, return [(id, title), ...].
    Story titles: bold+navy paragraphs starting with a digit followed by '.'.
    story_offset: number of stories already found in earlier pages of this chapter,
                  so anchor IDs stay unique across multi-page chapters.
    """
    stories = []
    story_counter = story_offset
    for p in main.find_all("p"):
        text = p.get_text().strip()
        if not re.match(r"^\d+\.", text):
            continue
        # Check for bold+navy styling (either inline style or class)
        has_navy = False
        for span in p.find_all("span"):
            style = span.get("style", "")
            classes = span.get("class", [])
            if "navy" in style or "bold" in classes:
                has_navy = True
                break
        if not has_navy:
            continue
        story_counter += 1
        anchor_id = f"c{chapter_idx:02d}-s{story_counter:02d}"
        p["id"] = anchor_id
        stories.append((anchor_id, text[:80]))  # truncate very long titles
    return stories


def clean_chapter_page(html: str) -> Tag:
    """Return cleaned <main> BeautifulSoup Tag."""
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main") or soup.find("body")
    remove_nav_and_chrome(main)
    return main


def fetch_intro_sections(html: str) -> tuple[str, str]:
    """
    Extract 'Lời Nói Đầu' and 'Dẫn Nhập' from ttpc00.htm.

    The raw HTML wraps the blockquote in a <span> whose early </span> causes
    lxml to prematurely close the <blockquote>, pushing all body paragraphs
    outside it. So we scan all <p> elements in <main> that fall after the
    TOC divider (-ooOoo-) and before the nav bar, then split on "Dẫn Nhập".
    """
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main") or soup.find("body")

    all_p = main.find_all("p")

    # Find the first "-ooOoo-" divider — it marks the end of the TOC table.
    # Intro content (Lời Nói Đầu then Dẫn Nhập) follows immediately after it.
    divider_indices = [
        i for i, p in enumerate(all_p)
        if re.search(r"-+ooOoo-+", p.get_text())
    ]
    if not divider_indices:
        return "", ""
    start_idx = divider_indices[0] + 1

    loi_paras = []
    dan_paras = []
    in_dan = False

    for p in all_p[start_idx:]:
        text = p.get_text().strip()
        text_norm = " ".join(text.split())  # collapse newlines/whitespace

        # Stop at the nav bar
        if ("Ðầu trang" in text_norm or "Đầu trang" in text_norm) and "Mục lục" in text_norm:
            break
        # Stop at footer
        if "Trở về trang Thư Mục" in text or "updated:" in text.lower():
            break
        # Skip the final --ooOoo-- divider between the two sections
        if re.fullmatch(r"[\s\u00a0–-]*o+O+o+[\s–-]*", text):
            continue

        # Detect "Dẫn Nhập" heading
        if re.search(r"Dẫn\s*[Nn]hập", text) and len(text) < 30:
            in_dan = True
            continue
        # Skip "Lời Nói Đầu" heading
        if re.search(r"Lời\s*[Nn]ói\s*[Ðđ]ầu", text) and len(text) < 30:
            continue

        # Sanitize this paragraph's attributes
        keep = {}
        if "style" in p.attrs:
            c = clean_inline_style(p["style"])
            if c:
                keep["style"] = c
        if "class" in p.attrs:
            classes = [c for c in p.get("class", []) if c in ("bold", "italic", "center")]
            if classes:
                keep["class"] = classes
        p.attrs = keep
        for tag in p.find_all(True):
            tk = {}
            if "style" in tag.attrs:
                c = clean_inline_style(tag["style"])
                if c:
                    tk["style"] = c
            if "class" in tag.attrs:
                classes = [c for c in tag.get("class", []) if c in ("bold", "italic")]
                if classes:
                    tk["class"] = classes
            tag.attrs = tk

        if in_dan:
            dan_paras.append(str(p))
        else:
            loi_paras.append(str(p))

    return "".join(loi_paras), "".join(dan_paras)


def build_chapter_html(title: str, body_html: str) -> str:
    return (
        f'<html xmlns="http://www.w3.org/1999/xhtml">'
        f'<head><title>{title}</title>'
        f'<link rel="stylesheet" type="text/css" href="../style/main.css"/>'
        f'</head><body>'
        f'{body_html}'
        f'</body></html>'
    )


def make_epub_item(title: str, file_name: str, content_html: str, style_item) -> epub.EpubHtml:
    item = epub.EpubHtml(title=title, file_name=file_name, lang="vi")
    item.content = build_chapter_html(title, content_html)
    item.add_item(style_item)
    return item


def build_epub(
    intro_items: list[tuple[str, str]],           # [(title, html), ...]
    chapters: list[tuple[str, str, list]],         # [(title, html, [(anchor_id, story_title)])
    output_path: str,
    cover_path: str | None = None,
) -> None:
    book = epub.EpubBook()
    book.set_identifier("tich-truyen-phap-cu")
    book.set_title("Tích truyện Pháp Cú")
    book.add_author("Thiền viện Viên Chiếu")
    book.set_language("vi")

    if cover_path and os.path.exists(cover_path):
        with open(cover_path, "rb") as f:
            book.set_cover(os.path.basename(cover_path), f.read())

    style = epub.EpubItem(
        uid="style",
        file_name="style/main.css",
        media_type="text/css",
        content=CSS,
    )
    book.add_item(style)

    all_items = []
    toc = []

    # Intro sections (no sub-TOC needed)
    for idx, (title, html) in enumerate(intro_items, start=1):
        file_name = f"intro{idx:02d}.xhtml"
        heading = f'<h2 style="color: #8b0000; text-align: center;">{title}</h2>'
        item = make_epub_item(title, file_name, heading + html, style)
        book.add_item(item)
        all_items.append(item)
        toc.append(epub.Link(file_name, title, f"intro{idx:02d}"))

    # Chapters with nested story TOC
    for chap_idx, (chap_title, chap_html, stories) in enumerate(chapters, start=1):
        file_name = f"chap{chap_idx:02d}.xhtml"
        item = make_epub_item(chap_title, file_name, chap_html, style)
        book.add_item(item)
        all_items.append(item)

        if stories:
            story_links = [
                epub.Link(f"{file_name}#{sid}", stitle, sid)
                for sid, stitle in stories
            ]
            toc.append((epub.Section(chap_title, href=file_name), story_links))
        else:
            toc.append(epub.Link(file_name, chap_title, f"chap{chap_idx:02d}"))

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + all_items

    epub.write_epub(output_path, book)
    print(f"\nEPUB written to: {output_path}")


def build_pdf(
    intro_items: list[tuple[str, str]],
    chapters: list[tuple[str, str, list]],
    output_path: str,
    cover_path: str | None = None,
) -> None:
    parts = []

    # Cover page
    if cover_path and os.path.exists(cover_path):
        with open(cover_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        parts.append(
            f'<div class="cover-page">'
            f'<img src="data:image/png;base64,{data}" alt="Bìa sách"/>'
            f'</div>'
        )

    # Intro sections
    for title, html in intro_items:
        parts.append(f'<h2>{title}</h2>')
        parts.append(html)

    # Chapters
    for chap_title, chap_html, _ in chapters:
        parts.append(f'<h2>{chap_title}</h2>')
        parts.append(chap_html)

    full_html = (
        '<!DOCTYPE html><html lang="vi"><head>'
        '<meta charset="utf-8"/>'
        f'<style>{PDF_CSS}</style>'
        '</head><body>'
        + "".join(parts)
        + '</body></html>'
    )

    WeasyprintHTML(string=full_html).write_pdf(output_path)
    print(f"PDF written to: {output_path}")


def main():
    # --- Step 1: Download all raw HTML (skip pages already cached) ---
    print("=== Step 1: Fetching raw HTML (cached pages will be skipped) ===")
    os.makedirs(RAW_HTML_DIR, exist_ok=True)

    print("\nOutline page (ttpc00)...")
    already_cached = os.path.exists(cache_path("00"))
    fetch_html_cached("00", OUTLINE_URL)
    if not already_cached:
        time.sleep(2)

    for chap_idx, (chapter_title, page_ids) in enumerate(CHAPTERS, start=1):
        print(f"\nChapter {chap_idx}: {chapter_title}")
        for page_id in page_ids:
            already_cached = os.path.exists(cache_path(page_id))
            fetch_html_cached(page_id, BASE_URL.format(page_id))
            if not already_cached:
                time.sleep(2)

    # --- Step 2: Process cached HTML into EPUB ---
    print("\n=== Step 2: Processing cached HTML ===")

    outline_html = fetch_html_cached("00", OUTLINE_URL)
    loi_html, dan_html = fetch_intro_sections(outline_html)
    intro_items = [
        ("Lời Nói Đầu", loi_html),
        ("Dẫn Nhập", dan_html),
    ]

    chapters_data = []
    for chap_idx, (chapter_title, page_ids) in enumerate(CHAPTERS, start=1):
        print(f"\nChapter {chap_idx}: {chapter_title}")
        merged_content = []
        all_stories = []
        for page_id in page_ids:
            html = fetch_html_cached(page_id, BASE_URL.format(page_id))
            main_tag = clean_chapter_page(html)
            sanitize_tag(main_tag)

            stories = detect_and_anchor_stories(main_tag, chap_idx, story_offset=len(all_stories))
            all_stories.extend(stories)

            merged_content.append(main_tag.decode_contents())

        combined_html = "\n".join(merged_content)
        chapters_data.append((chapter_title, combined_html, all_stories))
        print(f"  → {len(all_stories)} stories found")

    # --- Step 3: Build EPUB ---
    build_epub(intro_items, chapters_data, "tich-truyen-phap-cu.epub", cover_path="cover.png")

    # --- Step 4: Build PDF ---
    build_pdf(intro_items, chapters_data, "tich-truyen-phap-cu.pdf", cover_path="cover.png")


if __name__ == "__main__":
    main()
