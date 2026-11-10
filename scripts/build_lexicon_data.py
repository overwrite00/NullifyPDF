"""Generate ``lexicon_data_it.py`` from ISTAT open data (development only).

Not part of the runtime and not imported by the application. It reads the
ISTAT "Elenco comuni italiani" workbook (CC BY 4.0, https://www.istat.it/note-legali/),
normalises the place names, marks the ones that are also ordinary words as
ambiguous, and writes a plain Python module that PyInstaller collects like any
other import. Only the standard library is needed to read the workbook.

    python scripts/build_lexicon_data.py [--istat-file FILE] [--out FILE]

The generated module only *confirms* PERSON/LOCATION hits; a name missing
from it never rejects one.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Set

WIKIDATA_URL = "https://query.wikidata.org/sparql"
# Names that have an article on the Italian Wikipedia: a bounded, relevant set
# (counting people per name would time out on the public endpoint).
NAME_QUERY = (
    'SELECT DISTINCT ?l WHERE {{ ?n wdt:P31 wd:{cls}. '
    '?a schema:about ?n; schema:isPartOf <https://it.wikipedia.org/>. '
    '?n rdfs:label ?l. FILTER(LANG(?l)="it") }} LIMIT {page} OFFSET {off}'
)
NAME_CLASSES = {"given": "Q202444", "surnames": "Q101352"}
NAME_PAGE = 2000
NAME_OK = re.compile(r"^[a-zà-ÿ'’-]{3,24}$")
ISTAT_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
COLUMNS = {
    "Denominazione in italiano": "it",
    "Denominazione altra lingua": "alt",
    "Sigla automobilistica": "sigla",
    "Denominazione Regione": "region",
}
ROOT = pathlib.Path(__file__).resolve().parent.parent


def _col(ref: str) -> str:
    return re.match(r"[A-Z]+", ref).group()  # type: ignore[union-attr]


def read_rows(path: pathlib.Path) -> "tuple[List[str], List[Dict[str, str]]]":
    """First worksheet of an .xlsx as a list of header->value dicts."""
    z = zipfile.ZipFile(path)
    sst = [
        "".join(t.text or "" for t in si.iter("{%s}t" % NS["m"]))
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)
    ] if "xl/sharedStrings.xml" in z.namelist() else []
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = sheet.findall(".//m:row", NS)
    headers: Dict[str, str] = {}
    out: List[Dict[str, str]] = []
    for i, row in enumerate(rows):
        cells: Dict[str, str] = {}
        for c in row.findall("m:c", NS):
            v = c.find("m:v", NS)
            if v is None or v.text is None:
                continue
            cells[_col(c.get("r", ""))] = sst[int(v.text)] if c.get("t") == "s" else v.text
        if i == 0:
            headers = {col: " ".join(val.split()) for col, val in cells.items()}
            continue
        out.append({headers[col]: val for col, val in cells.items() if col in headers})
    return list(headers.values()), out


def fetch_names(kind: str, retries: int = 6) -> Set[str]:
    """Names of one kind (Wikidata, CC0), paged to stay under the query timeout."""
    import json
    import time
    import urllib.parse

    out: Set[str] = set()
    off = 0
    while True:
        q = NAME_QUERY.format(cls=NAME_CLASSES[kind], page=NAME_PAGE, off=off)
        url = WIKIDATA_URL + "?format=json&query=" + urllib.parse.quote(q)
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "NullifyPDF-build/1.0 (github.com/overwrite00/NullifyPDF)"}
                )
                rows = json.load(urllib.request.urlopen(req, timeout=120))["results"]["bindings"]
                break
            except Exception as e:
                if attempt == retries - 1:
                    raise RuntimeError(f"Wikidata {kind} page {off}: {e}") from e
                time.sleep(10 * (attempt + 1))
        for r in rows:
            n = normalise(r["l"]["value"])
            if NAME_OK.match(n):
                out.add(n)
        if len(rows) < NAME_PAGE:
            return out
        off += NAME_PAGE


def normalise(name: str) -> str:
    return " ".join(name.replace("’", "'").lower().split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--istat-file", type=pathlib.Path)
    ap.add_argument("--wikidata", action="store_true",
                    help="also fetch given names / surnames (CC0) from Wikidata")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "lexicon_data_it.py")
    args = ap.parse_args()
    src = args.istat_file
    if src is None:
        src = pathlib.Path("Elenco-comuni-italiani.xlsx")
        req = urllib.request.Request(ISTAT_URL, headers={"User-Agent": "NullifyPDF-build/1.0"})
        src.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    headers, rows = read_rows(src)
    missing = set(COLUMNS) - set(headers)
    if missing:
        print(f"Workbook layout changed, missing columns: {sorted(missing)}", file=sys.stderr)
        return 1

    comuni: Set[str] = set()
    sigle: Set[str] = set()
    regions: Set[str] = set()
    for r in rows:
        for key in ("Denominazione in italiano", "Denominazione altra lingua"):
            for part in re.split(r"\s*/\s*", r.get(key, "")):
                n = normalise(part)
                if len(n) >= 2:
                    comuni.add(n)
        if r.get("Sigla automobilistica"):
            sigle.add(r["Sigla automobilistica"].strip().upper())
        for part in re.split(r"\s*/\s*", r.get("Denominazione Regione", "")):
            if part.strip():
                regions.add(normalise(part))

    sys.path.insert(0, str(ROOT))
    import lexicon_it

    common = set(lexicon_it.COMMON_WORDS | lexicon_it.FUNCTION_WORDS | lexicon_it.GIVEN_NAMES
                 | lexicon_it.CONFLICT_NAMES)
    vocab_words: Set[str] = set()
    nlp = None
    try:
        import spacy

        nlp = spacy.load("it_core_news_md")
        vocab_words = {w for w in comuni if " " not in w and nlp.vocab.has_vector(w)}
    except Exception as e:  # model optional for the generator
        print(f"spaCy vocabulary not used: {e}", file=sys.stderr)
    ambiguous = {w for w in comuni if len(w) <= 3 or w in common or w in vocab_words}

    def lit(items: Set[str]) -> str:
        body = "|".join(sorted(items))
        assert '"""' not in body and "\\" not in body
        return 'frozenset("""' + body + '""".split("|"))'

    names_text = ""
    if args.wikidata:
        given = fetch_names("given")
        surn = fetch_names("surnames")
        both = given | surn
        name_ambiguous = {w for w in both if w in common or len(w) <= 3}
        if nlp is not None:
            try:
                name_ambiguous |= {w for w in both if " " not in w and nlp.vocab.has_vector(w)
                                   and w not in lexicon_it.GIVEN_NAMES and w not in lexicon_it.SURNAMES}
            except Exception:
                pass
        names_text = (
            "# Given names and surnames: Wikidata (CC0,\n"
            "# https://www.wikidata.org/wiki/Wikidata:Licensing), entries that\n"
            "# have an article on the Italian Wikipedia.\n"
            f"NAMES_GIVEN = {lit(given)}\n"
            f"NAMES_SURNAMES = {lit(surn)}\n"
            f"NAMES_AMBIGUOUS = {lit(name_ambiguous)}\n"
        )
        print(f"{len(given)} given names, {len(surn)} surnames ({len(name_ambiguous)} ambiguous)")

    text = (
        "# Generated by scripts/build_lexicon_data.py - do not edit.\n"
        "# Contains ISTAT data (Elenco comuni italiani, " + src.name + "), licensed\n"
        "# CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); modified: names\n"
        "# normalised, lower-cased, bilingual names split.\n"
        f"SOURCE_SHA256 = {{'istat_comuni': '{sha}'}}\n"
        f"COMUNI = {lit(comuni)}\n"
        f"COMUNI_AMBIGUOUS = {lit(ambiguous)}\n"
        f"PROVINCE_SIGLE = {lit(sigle)}\n"
        f"REGIONS = {lit(regions)}\n"
        + names_text
    )
    args.out.write_text(text, encoding="utf-8")
    print(f"{len(comuni)} comuni ({len(ambiguous)} ambiguous), {len(sigle)} province codes, "
          f"{len(regions)} regions -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
