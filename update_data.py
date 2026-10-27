#!/usr/bin/env python3
"""
Africa Energy Map — Quarterly Data Updater
Sources: World Bank API (EG.ELC.ACCS.ZS, EG.ELC.LOSS.ZS) + GlobalPetrolPrices electricity
Run: python update_data.py
"""
import json, re, urllib.request, urllib.error, html, sys
from datetime import datetime

HTML_FILE = "africa_energy_map.html"

AFRICA_ISO = [
    'DZA','AGO','BEN','BWA','BFA','BDI','CPV','CMR','CAF','TCD','COM','COG','COD',
    'CIV','DJI','EGY','GNQ','ERI','SWZ','ETH','GAB','GMB','GHA','GIN','GNB','KEN',
    'LSO','LBR','LBY','MDG','MWI','MLI','MRT','MUS','MAR','MOZ','NAM','NER','NGA',
    'RWA','STP','SEN','SLE','SOM','ZAF','SSD','SDN','TZA','TGO','TUN','UGA','ZMB','ZWE'
]

ISO_TO_MAP_NAME = {
    "Algeria":"Algeria","Angola":"Angola","Benin":"Benin","Botswana":"Botswana",
    "Burkina Faso":"Burkina Faso","Burundi":"Burundi","Cabo Verde":"Cabo Verde",
    "Cameroon":"Cameroon","Central African Republic":"Central African Republic",
    "Chad":"Chad","Comoros":"Comoros","Congo, Dem. Rep.":"DR Congo",
    "Congo, Rep.":"Republic of the Congo","Cote d'Ivoire":"Côte d'Ivoire",
    "Djibouti":"Djibouti","Egypt, Arab Rep.":"Egypt","Equatorial Guinea":"Equatorial Guinea",
    "Eritrea":"Eritrea","Eswatini":"Eswatini","Ethiopia":"Ethiopia","Gabon":"Gabon",
    "Gambia, The":"The Gambia","Ghana":"Ghana","Guinea":"Guinea",
    "Guinea-Bissau":"Guinea-Bissau","Kenya":"Kenya","Lesotho":"Lesotho",
    "Liberia":"Liberia","Libya":"Libya","Madagascar":"Madagascar","Malawi":"Malawi",
    "Mali":"Mali","Mauritania":"Mauritania","Mauritius":"Mauritius","Morocco":"Morocco",
    "Mozambique":"Mozambique","Namibia":"Namibia","Niger":"Niger","Nigeria":"Nigeria",
    "Rwanda":"Rwanda","Sao Tome and Principe":"Sao Tome and Principe","Senegal":"Senegal",
    "Sierra Leone":"Sierra Leone","Somalia, Fed. Rep.":"Somalia","South Africa":"South Africa",
    "South Sudan":"South Sudan","Sudan":"Sudan","Tanzania":"Tanzania","Togo":"Togo",
    "Tunisia":"Tunisia","Uganda":"Uganda","Zambia":"Zambia","Zimbabwe":"Zimbabwe",
}

AFRICA_MAP_TO_GPP = {
    "Sierra Leone":"Sierra Leone","Mali":"Mali","Kenya":"Kenya",
    "South Africa":"South Africa","Rwanda":"Rwanda","Burkina Faso":"Burkina Faso",
    "Gabon":"Gabon","Togo":"Togo","Senegal":"Senegal","Uganda":"Uganda",
    "Ghana":"Ghana","Namibia":"Namibia","Mauritius":"Mauritius",
    "Côte d'Ivoire":"Ivory Coast","Madagascar":"Madagascar","Mozambique":"Mozambique",
    "Morocco":"Morocco","Lesotho":"Lesotho","Botswana":"Botswana","Tanzania":"Tanzania",
    "Malawi":"Malawi","Cameroon":"Cameroon","Tunisia":"Tunisia","DR Congo":"DR Congo",
    "Algeria":"Algeria","Nigeria":"Nigeria","Zambia":"Zambia","Egypt":"Egypt",
    "Sudan":"Sudan","Angola":"Angola","Ethiopia":"Ethiopia",
}

def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")

def fetch_wb(indicator, iso_list, mrv=5):
    codes = ";".join(iso_list)
    url = (f"https://api.worldbank.org/v2/country/{codes}/indicator/{indicator}"
           f"?format=json&mrv={mrv}&per_page=300")
    data = json.loads(fetch_url(url))
    best = {}
    for row in data[1]:
        if row["value"] is None:
            continue
        iso = row["countryiso3code"]
        wb_name = row["country"]["value"]
        map_name = ISO_TO_MAP_NAME.get(wb_name)
        if not map_name:
            continue
        year = row["date"]
        if map_name not in best or year > best[map_name]["year"]:
            best[map_name] = {"value": round(row["value"] * 10) / 10, "year": year}
    return best

def fetch_gpp_tariffs():
    html_content = fetch_url("https://www.globalpetrolprices.com/electricity_prices/")
    # Parse table rows: country name and USD/kWh price
    pattern = r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>([\d.,]+)</td>'
    matches = re.findall(pattern, html_content, re.DOTALL)
    result = {}
    for raw_country, raw_price in matches:
        country = re.sub(r'<[^>]+>', '', raw_country).strip()
        country = html.unescape(country)
        map_name = None
        for k, v in AFRICA_MAP_TO_GPP.items():
            if v == country:
                map_name = k
                break
        if map_name:
            try:
                price_usd = float(raw_price.replace(",", "."))
                result[map_name] = round(price_usd * 100 * 10) / 10  # USD/kWh → ¢/kWh
            except ValueError:
                pass
    return result

def js_obj(d, indent=2):
    """Format dict as JS object literal (not JSON — no quotes on keys for readability)."""
    lines = []
    for k, v in sorted(d.items()):
        val = v["value"] if isinstance(v, dict) else v
        lines.append(f'  "{k}":{val}')
    return "{\n" + ",\n".join(lines) + "\n}"

def replace_const(content, const_name, new_body, new_comment):
    """Replace a JS const block in the HTML."""
    pattern = rf'(// [^\n]*\n)*const {re.escape(const_name)} = \{{[^}}]*\}};'
    replacement = f"{new_comment}\nconst {const_name} = {new_body};"
    new_content, n = re.subn(pattern, replacement, content, flags=re.DOTALL)
    if n == 0:
        print(f"  WARNING: could not find const {const_name}", file=sys.stderr)
    return new_content

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Africa Energy Map — Quarterly Update")

    print("  Fetching electricity access (WB EG.ELC.ACCS.ZS)...")
    access = fetch_wb("EG.ELC.ACCS.ZS", AFRICA_ISO)
    print(f"    → {len(access)} countries")

    print("  Fetching line losses (WB EG.ELC.LOSS.ZS)...")
    losses = fetch_wb("EG.ELC.LOSS.ZS", AFRICA_ISO)
    print(f"    → {len(losses)} countries")

    print("  Fetching electricity tariffs (GlobalPetrolPrices)...")
    try:
        tariffs = fetch_gpp_tariffs()
        print(f"    → {len(tariffs)} countries")
    except Exception as e:
        print(f"    WARNING: GPP scrape failed ({e}), skipping tariffs", file=sys.stderr)
        tariffs = {}

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    today = datetime.now().strftime("%Y-%m-%d")

    # Update ELEC_ACCESS
    if access:
        # Build new block preserving structure
        lines = []
        for name, d in sorted(access.items()):
            lines.append(f'  "{name}":{d["value"]}')
        new_body = "{\n" + ",\n".join(lines) + "\n}"
        comment = (f"// ENERGY ACCESS DATA — Source: World Bank WDI (EG.ELC.ACCS.ZS)\n"
                   f"// API récupéré {today} — année la plus récente disponible\n"
                   f"// ═══════════════════════════════════════════════════════════════")
        # Simple targeted replacement using known anchor
        old = re.search(r'// ENERGY ACCESS DATA.*?const ELEC_ACCESS = \{.*?\};',
                        content, re.DOTALL)
        if old:
            content = content[:old.start()] + comment + f"\nconst ELEC_ACCESS = {new_body};" + content[old.end():]
            print("  ✓ ELEC_ACCESS updated")

    # Update LINE_LOSSES
    if losses:
        lines = []
        for name, d in sorted(losses.items()):
            lines.append(f'  "{name}":{d["value"]}')
        new_body = "{\n" + ",\n".join(lines) + "\n}"
        old = re.search(r'// System losses.*?const LINE_LOSSES = \{.*?\};', content, re.DOTALL)
        if old:
            comment = (f"// System losses (% of electricity lost in T&D).\n"
                       f"// Source: World Bank WDI (EG.ELC.LOSS.ZS) — récupéré {today}")
            content = content[:old.start()] + comment + f"\nconst LINE_LOSSES = {new_body};" + content[old.end():]
            print("  ✓ LINE_LOSSES updated")

    # Update ELEC_TARIFF (GPP values only)
    if tariffs:
        old = re.search(r'// Average electricity tariff.*?const ELEC_TARIFF = \{.*?\};', content, re.DOTALL)
        if old:
            existing_block = old.group(0)
            # Replace GPP section header + values, keep UPBEAT fallback
            gpp_lines = "\n".join(f'  "{k}":{v},' for k, v in sorted(tariffs.items()))
            # Find UPBEAT fallback section
            upbeat_match = re.search(r'(  // UPBEAT fallback.*)', existing_block, re.DOTALL)
            upbeat_section = upbeat_match.group(1) if upbeat_match else ""
            new_block = (
                f"// Average electricity tariff (US¢/kWh).\n"
                f"// Sources: GlobalPetrolPrices.com residential — récupéré {today} + UPBEAT fallback\n"
                f"const ELEC_TARIFF = {{\n"
                f"  // GlobalPetrolPrices.com (residential USD¢/kWh)\n"
                f"{gpp_lines}\n"
                f"{upbeat_section}"
            )
            if not new_block.rstrip().endswith("};"):
                new_block = new_block.rstrip().rstrip(",") + "\n};"
            content = content[:old.start()] + new_block + content[old.end():]
            print("  ✓ ELEC_TARIFF updated (GPP section)")

    # Update subtitle date
    content = re.sub(
        r'Mis à jour \w+ \d{4}',
        f'Mis à jour {datetime.now().strftime("%b. %Y")}',
        content
    )

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  ✓ Saved {HTML_FILE}")
    print("  Done.")

if __name__ == "__main__":
    main()
