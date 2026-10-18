import csv
import os
import re
import sys
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE = "https://medimart.pk"
CSV_FILE = "medicines.csv"
DONE_FILE = "done_generics.txt"
USER_AGENT = "MEDSHELF-student-project/1.0 (educational use)"
COLUMNS = ["name", "price", "category", "generic", "manufacturer", "pack_size", "form", "availability", "product_url"]
LABELS = ["Formula", "Pack size", "Form", "Used for", "Categories"]
DELAY = 1.0

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})
robots = RobotFileParser()


def start_robots():
    global DELAY
    robots.parse([])
    try:
        response = session.get(BASE + "/robots.txt", timeout=20)
        if response.status_code == 200:
            robots.parse(response.text.splitlines())
            wait = robots.crawl_delay(USER_AGENT)
            if wait:
                DELAY = max(DELAY, float(wait))
    except requests.RequestException as error:
        print("Could not read robots.txt:", error)
    print("Delay between requests:", DELAY, "seconds")


def fetch(url):
    if not robots.can_fetch(USER_AGENT, url):
        print("  robots.txt does not allow:", url)
        return None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=30)
        except requests.RequestException as error:
            print("  network error:", error)
            time.sleep(5)
            continue
        if response.status_code == 200:
            time.sleep(DELAY)
            return response.text
        if response.status_code in (404, 410):
            return None
        print("  status", response.status_code, "for", url)
        if response.status_code in (403, 429, 503):
            time.sleep(20 * (attempt + 1))
            continue
        return None
    return None


def get_generic_links():
    html = fetch(BASE + "/generics/")
    if html is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        path = urlparse(a["href"]).path.strip("/").split("/")
        if len(path) == 2 and path[0] == "generics":
            link = BASE + "/generics/" + path[1] + "/"
            if link not in links:
                links.append(link)
    return links


def find_card(link):
    node = link.parent
    for _ in range(6):
        if node is None:
            break
        titles = {a["href"] for a in node.select('h2 a[href*="/product/"], h3 a[href*="/product/"]')}
        if len(titles) == 1 and (node.select_one(".price") or "₨" in node.get_text()):
            return node
        node = node.parent
    return link.parent


def read_price(card):
    box = card.select_one(".price ins") or card.select_one(".price") or card
    match = re.search(r"₨\s*([\d,]+(?:\.\d+)?)", box.get_text(" ", strip=True))
    if match:
        return match.group(1).replace(",", "")
    return ""


def parse_cards(html):
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one("#main-content") or soup.select_one("main") or soup
    cards = []
    seen = set()
    for link in area.select('h2 a[href*="/product/"], h3 a[href*="/product/"]'):
        url = link["href"].split("?")[0]
        if url in seen:
            continue
        seen.add(url)
        card = find_card(link)
        category = card.select_one('a[href*="/product-category/"]')
        cards.append({
            "name": link.get_text(" ", strip=True),
            "price": read_price(card),
            "category": category.get_text(strip=True) if category else "",
            "product_url": url,
        })
    return cards


def read_rows():
    if not os.path.exists(CSV_FILE):
        return []
    with open(CSV_FILE, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for column in COLUMNS:
            row.setdefault(column, "")
    return rows


def write_rows(rows):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def append_rows(rows):
    new_file = not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def read_done():
    if not os.path.exists(DONE_FILE):
        return set()
    with open(DONE_FILE, encoding="utf-8") as file:
        return set(line.strip() for line in file if line.strip())


def collect_listing():
    start_robots()
    print("Reading the generics list...")
    generics = get_generic_links()
    if not generics:
        print("No generics found. Stopping.")
        return
    print(len(generics), "generics found")
    existing = set(row["product_url"] for row in read_rows())
    done = read_done()
    debug_saved = False
    for number, generic_url in enumerate(generics, 1):
        if generic_url in done:
            continue
        generic = generic_url.rstrip("/").split("/")[-1].replace("-", " ").title()
        seen_here = set()
        new_rows = []
        page = 1
        finished = False
        while True:
            url = generic_url if page == 1 else generic_url + "?product-page=" + str(page)
            html = fetch(url)
            if html is None:
                break
            fresh = [c for c in parse_cards(html) if c["product_url"] not in seen_here]
            if not fresh:
                if page == 1 and not debug_saved:
                    print("  No medicines found on", url)
                    with open("debug_page.html", "w", encoding="utf-8") as file:
                        file.write(html)
                    debug_saved = True
                finished = page > 1
                break
            for card in fresh:
                seen_here.add(card["product_url"])
                if card["product_url"] in existing:
                    continue
                existing.add(card["product_url"])
                card["generic"] = generic
                new_rows.append(card)
            page += 1
        if new_rows:
            append_rows(new_rows)
        if finished:
            with open(DONE_FILE, "a", encoding="utf-8") as file:
                file.write(generic_url + "\n")
        print(f"[{number}/{len(generics)}] {generic}: {len(new_rows)} new, total {len(existing)}")
    print("Finished. Unique medicines collected:", len(existing))


def value_after(lines, label):
    for index, line in enumerate(lines):
        if line == label and index + 1 < len(lines):
            value = lines[index + 1]
            if value not in LABELS:
                return value
    return ""


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    result = {"manufacturer": "", "pack_size": "", "form": "", "availability": ""}
    meta = soup.find("meta", attrs={"property": re.compile("availability$")})
    if meta:
        if meta.get("content") == "instock":
            result["availability"] = "In stock"
        elif meta.get("content") == "outofstock":
            result["availability"] = "Out of stock"
    brand = soup.select_one('a[href*="/brand/"]')
    if brand:
        image = brand.find("img")
        name = brand.get("title") or brand.get_text(strip=True)
        if not name and image:
            name = image.get("title") or image.get("alt") or ""
        result["manufacturer"] = name
    lines = [line.strip() for line in soup.get_text("\n").split("\n") if line.strip()]
    result["pack_size"] = value_after(lines, "Pack size")
    result["form"] = value_after(lines, "Form")
    if not result["availability"]:
        for line in lines[:400]:
            if line in ("In stock", "Out of stock"):
                result["availability"] = line
                break
    return result


def collect_details():
    rows = read_rows()
    if not rows:
        print(CSV_FILE, "is missing or empty. Run 'py scraper.py list' first.")
        return
    start_robots()
    todo = [row for row in rows if row["availability"] == ""]
    print(len(todo), "medicines still need details")
    failures = 0
    for count, row in enumerate(todo, 1):
        html = fetch(row["product_url"])
        if html is None:
            failures += 1
            if failures >= 10:
                print("Too many failed requests in a row. Stopping.")
                break
            continue
        failures = 0
        for key, value in parse_detail(html).items():
            if value:
                row[key] = value
        if row["availability"] == "":
            row["availability"] = "Unknown"
        if count % 50 == 0:
            write_rows(rows)
            print(count, "of", len(todo), "done")
    write_rows(rows)
    print("Details saved.")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "list"
    if step == "list":
        collect_listing()
    elif step == "details":
        collect_details()
    else:
        print("Use: py scraper.py list   or   py scraper.py details")