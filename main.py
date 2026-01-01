"""
main.py: třetí projekt do Engeto Online Python Akademie

author: Lubomir Tatran
email: lubomir.tatran@gmail.com
"""

from __future__ import annotations

import csv
import sys
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SEPARATOR = "-" * 47
HEADERS = {"User-Agent": "Mozilla/5.0 (Project Elections Scraper)"}


def die(message: str, code: int = 1) -> None:
    """Print error message and exit."""
    print(message)
    sys.exit(code)


def parse_args(argv: list[str]) -> tuple[str, str]:
    """Parse and validate CLI arguments: <URL> <output.csv>."""
    if len(argv) != 3:
        die("Usage: python main.py <URL> <output.csv>")

    url = argv[1].strip()
    out_csv = argv[2].strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        die("Error: First argument must be a valid URL starting with http(s).")

    if "volby.cz" not in url:
        die("Error: URL must point to volby.cz.")

    if not out_csv.lower().endswith(".csv"):
        die("Error: Second argument must be a .csv file name.")

    return url, out_csv


def fetch_soup(url: str) -> BeautifulSoup:
    """Download a page and return BeautifulSoup parsed HTML."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        die(f"Error: Unable to download page (HTTP {resp.status_code}).")

    # volby.cz pages often use windows-1250; requests may guess, but we force it:
    resp.encoding = resp.apparent_encoding or "cp1250"
    return BeautifulSoup(resp.text, "lxml")


def clean_number(text: str) -> int:
    """Convert number-like text with spaces/nbsp to int."""
    t = text.replace("\xa0", "").replace(" ", "").strip()
    return int(t) if t.isdigit() else 0


def find_municipalities(district_soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """
    From district page soup, extract municipalities:
    code, name, and a detail URL to results page.
    """
    municipalities: list[dict[str, str]] = []

    # The district page contains tables with municipality rows.
    # We look for links that contain 'xobec=' (municipality code parameter).
    for a in district_soup.select("a[href]"):
        href = a.get("href", "")
        if "xobec=" not in href:
            continue

        code = a.get_text(strip=True)
        if not code.isdigit():
            continue

        # row has municipality name in the same <tr>
        tr = a.find_parent("tr")
        if not tr:
            continue

        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        name = tds[1].get_text(" ", strip=True)
        detail_url = urljoin(base_url, href)

        municipalities.append({"code": code, "name": name, "url": detail_url})

    # Remove duplicates by code (sometimes both "Číslo" and "X" columns exist)
    unique: dict[str, dict[str, str]] = {}
    for m in municipalities:
        unique[m["code"]] = m

    result = list(unique.values())
    if not result:
        die("Error: No municipalities found on the provided URL. Is it a district page?")
    return result


def extract_summary_numbers(muni_soup: BeautifulSoup) -> tuple[int, int, int]:
    """Extract registered, envelopes, valid votes from municipality page."""
    # Typical headers on volby.cz:
    # sa2 = registered, sa3 = envelopes, sa6 = valid
    def by_headers(h: str) -> int:
        td = muni_soup.find("td", attrs={"headers": h})
        return clean_number(td.get_text()) if td else 0

    registered = by_headers("sa2")
    envelopes = by_headers("sa3")
    valid = by_headers("sa6")

    # Fallback: sometimes headers differ; try label-based parsing
    if not (registered and envelopes and valid):
        labels = {
            "Voliči v seznamu": "registered",
            "Vydané obálky": "envelopes",
            "Platné hlasy": "valid",
        }
        found: dict[str, int] = {"registered": registered, "envelopes": envelopes, "valid": valid}
        for row in muni_soup.select("table tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            for label, key in labels.items():
                if label in cells[0] and found[key] == 0:
                    found[key] = clean_number(cells[1])

        registered, envelopes, valid = found["registered"], found["envelopes"], found["valid"]

    return registered, envelopes, valid


def extract_party_votes(muni_soup: BeautifulSoup) -> tuple[list[str], dict[str, int]]:
    """
    Extract parties and votes from municipality page.
    Returns (party_order, votes_dict).
    """
    party_order: list[str] = []
    votes: dict[str, int] = {}

    # Party rows typically contain a cell with class 'overflow_name'
    # and another numeric cell with votes.
    for row in muni_soup.select("table tr"):
        name_td = row.select_one("td.overflow_name")
        if not name_td:
            continue

        party = name_td.get_text(" ", strip=True)
        tds = row.find_all("td")
        if len(tds) < 3:
            continue

        # Usually votes are in the 3rd td in that row (index 2)
        vote_val = clean_number(tds[2].get_text())
        if party and party not in votes:
            votes[party] = vote_val
            party_order.append(party)

    if not votes:
        die("Error: Could not extract party results from municipality page.")

    return party_order, votes


def scrape_municipality(m: dict[str, str]) -> dict[str, Any]:
    """Scrape one municipality page into a flat dict."""
    soup = fetch_soup(m["url"])

    registered, envelopes, valid = extract_summary_numbers(soup)
    party_order, party_votes = extract_party_votes(soup)

    row: dict[str, Any] = {
        "code": m["code"],
        "location": m["name"],
        "registered": registered,
        "envelopes": envelopes,
        "valid": valid,
        "_party_order": party_order,   # internal helper (not written to CSV)
        "_party_votes": party_votes,   # internal helper (not written to CSV)
    }
    return row


def write_csv(rows: list[dict[str, Any]], party_cols: list[str], out_csv: str) -> None:
    """Write final output CSV."""
    fieldnames = ["code", "location", "registered", "envelopes", "valid"] + party_cols

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in rows:
            out = {k: r[k] for k in ["code", "location", "registered", "envelopes", "valid"]}
            votes: dict[str, int] = r["_party_votes"]
            for p in party_cols:
                out[p] = votes.get(p, 0)
            writer.writerow(out)


def main() -> None:
    url, out_csv = parse_args(sys.argv)

    print(SEPARATOR)
    print("Downloading district page...")
    district_soup = fetch_soup(url)

    municipalities = find_municipalities(district_soup, url)
    print(f"Found {len(municipalities)} municipalities.")
    print(SEPARATOR)

    rows: list[dict[str, Any]] = []
    party_cols: list[str] = []

    for i, m in enumerate(municipalities, start=1):
        print(f"[{i}/{len(municipalities)}] Scraping: {m['name']} ({m['code']})")
        data = scrape_municipality(m)

        # Set party columns from the first municipality (order matters)
        if not party_cols:
            party_cols = data["_party_order"]

        rows.append(data)

    write_csv(rows, party_cols, out_csv)
    print(SEPARATOR)
    print(f"Done. Saved: {out_csv}")


if __name__ == "__main__":
    main()
