"""Shared config: firm universe and keyword mapping.

Universe: US-listed small/mid-cap consumer & TMT names whose main brand is a
distinctive, searchable word. Keyword choice follows Da, Engelberg & Gao (2011):
the term a consumer would actually type for the firm's main product.
Ambiguity notes are recorded so the mapping can be audited.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_OUT = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
for p in (DATA_RAW, DATA_OUT, OUTPUT):
    p.mkdir(parents=True, exist_ok=True)

GEO = "US"
TRENDS_START = "2016-01-01"

# ticker: (search keyword, pod, mapping note)
FIRMS = {
    "DUOL": ("duolingo", "TMT", "Brand = app = company; near 1:1 mapping."),
    "WING": ("wingstop", "Consumer", "Brand = company; QSR, ~US-centric sales."),
    "PTON": ("peloton", "Consumer", "Brand = company; also searched for news/recalls."),
    "ETSY": ("etsy", "TMT", "Marketplace; revenue = take rate x GMS, search ~ traffic."),
    "CROX": ("crocs", "Consumer", "Revenue includes HEYDUDE since 2022 (not in keyword)."),
    "CHGG": ("chegg", "TMT", "Brand = company; structural decline post-ChatGPT."),
    "SHAK": ("shake shack", "Consumer", "Two-word brand; unambiguous."),
    "PLNT": ("planet fitness", "Consumer", "Revenue mixes franchise fees + equipment sales."),
    "ELF":  ("elf cosmetics", "Consumer", "'elf' alone is ambiguous (Christmas elf) so use 'elf cosmetics'."),
    "WAYF": ("wayfair", "TMT", "Ticker is W; label WAYF used internally only."),
    "SONO": ("sonos", "TMT", "Brand = company; hardware, lumpy launches."),
    "GPRO": ("gopro", "TMT", "Brand = company; hardware."),
    "ROKU": ("roku", "TMT", "Revenue mostly platform/ads, not devices: weaker link expected."),
    "FIVE": ("five below", "Consumer", "Two-word brand; mostly store traffic, little e-com."),
    "FNKO": ("funko", "Consumer", "Brand = company; wholesale to retailers (sell-in vs sell-through)."),
    "SFIX": ("stitch fix", "Consumer", "Two-word brand; subscription apparel."),
}
SEC_TICKER = {"WAYF": "W"}  # internal label -> SEC ticker

# Generic, non-personal User-Agent for SEC EDGAR (SEC asks for a declared UA).
SEC_UA = "alt-data-student-research-script/0.1"
