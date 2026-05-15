#!/usr/bin/env python3
"""
清洗 JB Rentals Sheet 的 Property Name 列 — 标准化 + 去垃圾。
只改 Property Name (B列)，不删行、不改其他列。
"""
import json, re, sys, os
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

SA_KEY = "/home/user/.hermes/google_sa_key.json"
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"
SHEET_NAME = "JB Rentals"
PROP_COL_INDEX = 1  # B列 = index 1

# ═══════════════════════════════════════════
#  标准化映射表
# ═══════════════════════════════════════════
NORMALIZE_MAP = {
    # R&F
    "r&f": "R&F Princess Cove",
    "rnf": "R&F Princess Cove",
    "r and f": "R&F Princess Cove",
    "r&f princess cove": "R&F Princess Cove",
    "r&f phase 2": "R&F Princess Cove",
    "rf princess cove phase 2": "R&F Princess Cove",
    "f princess cove": "R&F Princess Cove",
    "r&f mall": "R&F Princess Cove",
    # Tri Tower
    "tritower": "Tri Tower",
    "tri tower": "Tri Tower",
    "tritower residence": "Tri Tower",
    # Trellis
    "trellis residence": "Trellis Residence",
    "trellis residensi": "Trellis Residence",
    "trellis": "Trellis Residence",
    # Paragon
    "paragon suites": "Paragon Residences",
    "paragon residence": "Paragon Residences",
    "paragon": "Paragon Residences",
    # SKS
    "sks pavillion": "SKS Pavilion",
    "sks pavillion residence": "SKS Pavilion",
    "sks pavilion": "SKS Pavilion",
    # Country Garden
    "country garden": "Country Garden",
    "country garden central park": "Country Garden",
    # KSL
    "ksl": "KSL Residence",
    "ksl residence": "KSL Residence",
    "ksl resident": "KSL Residence",
    "ksl resident 2": "KSL Residence",
    "ksl d'inspire": "KSL D'Inspire",
    "d inspire": "KSL D'Inspire",
    "d'inspire": "KSL D'Inspire",
    "d'inspire residence": "KSL D'Inspire",
    # Danga
    "danga bay": "Danga Bay",
    "danga kings bay": "Danga Bay",
    # Twin
    "twin tower": "Twin Tower",
    "twin galaxy": "Twin Galaxy",
    # Others
    "palazio": "Palazio Apartment",
    "palazio apartment": "Palazio Apartment",
    "surimas": "Surimas Suites",
    "surimas suites": "Surimas Suites",
    "surimas condo": "Surimas Suites",
    "one49": "One49 Residence",
    "one49 residence": "One49 Residence",
    "tropez residence": "Tropez Residence",
    "tropez": "Tropez Residence",
    "sky 88": "Sky 88",
    "sky88": "Sky 88",
    "platino": "The Platino",
    "the platino": "The Platino",
    "meridin": "Meridin Medini",
    "meridin medini": "Meridin Medini",
    "bayu marina": "Bayu Marina",
    "bayu marina residence": "Bayu Marina",
    "bayu puteri": "Bayu Puteri",
    "v summer": "V Summer",
    "suasana": "Suasana Suites",
    "suasana suites": "Suasana Suites",
    "forest city": "Forest City",
    "summit residence": "Summit Residence",
    "summit": "Summit Residence",
    "wateredge": "Wateredge Residence",
    "wateredge residence": "Wateredge Residence",
    "pan vista": "Pan Vista Apartment",
    "pan vista apartment": "Pan Vista Apartment",
    "tebrau city residence": "Tebrau City Residence",
    "tebrau city": "Tebrau City Residence",
    "season larkin": "Season Larkin Apartment",
    "season larkin apartment": "Season Larkin Apartment",
    "season apartment": "Season Larkin Apartment",
    # Taman 系列
    "taman universiti": "Taman Universiti",
    "taman ungku tun aminah": "Taman Ungku Tun Aminah",
    "taman molek": "Taman Molek",
    "taman daya": "Taman Daya",
    "taman perling": "Taman Perling",
    "taman sentosa": "Taman Sentosa",
    "taman pelangi": "Taman Pelangi",
    "taman johor jaya": "Taman Johor Jaya",
    "taman setia indah": "Taman Setia Indah",
    "taman puteri wangsa": "Taman Puteri Wangsa",
    "taman iskandar": "Taman Iskandar",
    "taman century": "Taman Century",
    "taman century abad": "Taman Century",
    "taman gaya": "Taman Gaya",
    "taman desa jaya": "Taman Desa Jaya",
    "taman megah ria": "Taman Megah Ria",
    "taman kempas indah": "Taman Kempas Indah",
    "taman bukit kempas": "Taman Bukit Kempas",
    "taman laguna": "Taman Laguna",
    "taman scientex": "Taman Scientex",
    "taman sierra perdana": "Taman Sierra Perdana",
    "taman suria": "Taman Suria",
    "taman tasek": "Taman Tasek",
    "tmn setia indah": "Taman Setia Indah",
    "tmn sentosa": "Taman Sentosa",
    "tmn jp perdana": "Taman JP Perdana",
    # 中文
    "大学城": "Taman Universiti",
    "彩虹": "Taman Pelangi",
    "新山大学城": "Taman Universiti",
    "碧桂园": "Country Garden",
    # 区域
    "johor jaya": "Johor Jaya",
    "mount austin": "Mount Austin",
    "austin heights": "Austin Heights",
    "setia tropika": "Setia Tropika",
    "bukit indah": "Bukit Indah",
    "gelang patah": "Gelang Patah",
    "iskandar puteri": "Iskandar Puteri",
    "eco botanic": "Eco Botanic",
    "eco summer": "Eco Summer",
    "eco business park 1": "Eco Business Park 1",
    "desa tebrau": "Desa Tebrau",
    "desa harmoni": "Desa Harmoni",
    "kangkar tebrau": "Kangkar Tebrau",
    "mutiara rini": "Mutiara Rini",
    "nusa sentral": "Nusa Sentral",
    "nusa bestari": "Nusa Bestari",
    "impian emas": "Impian Emas",
    "permas jaya": "Permas Jaya",
    "johor bahru": "Johor Bahru",
    "bandar dato onn": "Bandar Dato Onn",
    "skudai": "Skudai",
    "kulai": "Kulai",
    "senai": "Senai",
    "larkin": "Larkin",
    "tampoi": "Tampoi",
    "pelangi": "Taman Pelangi",
    "kempas": "Kempas",
    "masai": "Masai",
    "pasir gudang": "Pasir Gudang",
    "tebrau": "Tebrau",
    "medini": "Medini",
    "perling": "Taman Perling",
    "tuas": "Tuas",
    # 楼盘
    "aloha tower": "Aloha Tower",
    "aliff residence": "The Aliff Residence",
    "the aliff residence": "The Aliff Residence",
    "akasa condo": "Akasa Condo",
    "ambience residence": "Ambience Residence",
    "botanika": "Botanika",
    "botanika apartment": "Botanika",
    "botanika @ tebrau bay": "Botanika",
    "bukit impian residence": "Bukit Impian Residence",
    "centraresidence": "Centra Residence",
    "dwi mahkota condo": "Dwi Mahkota Condo",
    "epic residence": "Epic Residence",
    "g residence": "G Residence",
    "garden residence": "The Garden Residence",
    "the garden residence": "The Garden Residence",
    "havona": "Havona",
    "marina residence": "Marina Residence",
    "marina apartment": "Marina Residence",
    "molek regency": "Molek Regency",
    "molek regency service apartment": "Molek Regency",
    "park avenue apartment": "Park Avenue Apartment",
    "permas ville apartment": "Permas Ville Apartment",
    "raffles suites": "The Raffles Suites",
    "the raffles suites": "The Raffles Suites",
    "rich apartment": "Rich Apartment",
    "senibong villa": "Senibong Villa",
    "seri mutiara apartment": "Seri Mutiara Apartment",
    "straits view condo": "The Straits View Condo",
    "the straits view condo": "The Straits View Condo",
    "sunway grid residence": "Sunway Grid Residence",
    "1 tebrau residence": "1 Tebrau Residence",
    "skudai villa": "Skudai Villa",
    "veranda residence": "Veranda Residence",
    "bora residence": "Bora Residence",
    # 商业
    "kota puteri": "Kota Puteri Industrial",
    "johor premium outlet": "Johor Premium Outlet",
    "kota masai": "Kota Masai",
    "mid valley southkey": "Mid Valley Southkey",
    "south key mosaic": "South Key Mosaic",
    # 补充
    "jalan sutera kuning": "Sutera Utama",
    "jalan sutera kuning jb": "Sutera Utama",
    "jalan hang tuat": "Jalan Hang Tuat",
    "jalan raja udang": "Jalan Raja Udang",
    "jalan abdul samad": "Jalan Abdul Samad",
    "taman melodies": "Taman Melodies",
    "taman abad": "Taman Abad",
    "taman adda height": "Taman Adda Height",
    "taman gembira": "Taman Gembira",
    "taman perumahan rakyat lima kedai flat": "Taman Perumahan Rakyat Lima Kedai",
    "tiram": "Tiram",
    "wangsa": "Taman Puteri Wangsa",
    "百万镇": "Permas Jaya",
    "柔佛 / 巴西古当": "Pasir Gudang",
    "ciqcondo": "CIQ",
    "jb ciq checkpoint": "CIQ",
    "jb ciq jb sentral r&f mall 新加坡关卡 热门地区房间": "R&F Princess Cove",
}


# ═══════════════════════════════════════════
#  垃圾检测
# ═══════════════════════════════════════════
GARBAGE_PATTERNS = [
    # 纯人名
    r'^[A-Z][a-z]+\s+(?:Chong|Lee|Goh|Loh|Tan|Wong|Lim|Chen|Pong|Koh|Lye|Loo|Liew|Teo|Ng|Foo|Chan|Yap|Chin|Sia|Tee|Ooi|Seng)\s*$',
    r'^(?:Angela|Crystal|Jacelyn|Sally|Sandra|Jac|Kedy|Loh\b|Jeddy|Eugene|Janet|Jess(?:rene)?|Esther|Nicole|Diane|Puyol|YuXiu|Jeny|Ebby|Jia\s*Hui|Jia\s*Xin|Qian\s*Han|Yu\s*Ern|Yoklen|Keith|Kent|Fionna|Vincy|Kenny|Benjamin|Tommy|Brandon|Darren|Chew\b|Yii|Yeow|Mei\b|Ling\b|Royce|Soh|Hui\s*Jing|Elaine|Alice|Ivan|Song|Well\b|Cheksiang|Molly|Erven|Adeline|Yi\s*Yi)\s',
    # 价格
    r'^(?:RM|Rm|rm)\s*\d[\d,.]*',
    r'^RENTAL\s*\d',
    # 属性
    r'^(?:Fully|Partial(?:ly)?|Semi)\s*(?:Furnish(?:ed|es)?|furnish(?:ed)?)',
    r'^(?:Unfurnished|Kosong)',
    r'^(?:Master|Common|Middle|Small|Balcony)\s*(?:Room|Bedroom)',
    r'^(?:Bedroom|Bathroom|Bed|Bath|Rooms|Toilet|Deposit)',
    r'^(?:Living\s*Hall|Nice\s*View|High\s*Floor|Smart\s*Lock|High-Speed\s*WiFi)',
    r'^(?:Freehold|Leasehold|Bumi\s*(?:Lot|Release)|Non[-\s]Bumi)',
    r'^(?:WiFi|Wi-Fi|Unifi|UNIFI|Internet\s*Included|Utilities\s*included)',
    r'^(?:Guarded|Gated|Visitors?\s*allowed)',
    r'^(?:Food\s*Court|Single\s*Storey|Double\s*Storey|Storey)',
    r'^(?:Service\s*Apartment|Service\s*residence|Residences?)',
    # 联系方式
    r'^(?:WhatsApp?\s|Whattsapp|Call\s*Or|Please\s*Contact|No\s*agent)',
    r'^(?:Real\s*Estate|Properties|TeamGather|Royce\s*Properties)',
    # 垃圾前缀
    r'^(?:Submaster|Stabilisation|CCC\s*|HGM\s*|TRR|WTL|GF|CE\s*|D75|RTS\s*$)',
    r'^(?:Nego|For\s*(?:Rent|Sale)\b)',
    r'^(?:REN\s*\d|DK\s*Property|FOR\s*SALE|UNTUK\s*DIJUAL)',
    r'^(?:Custom|Stainless|Unblocked|Empathetic|Emphathetic)',
    r'^(?:X\s*Jalan)',
    r'^(?:Land\s*(?:size|Pagoh)|Intermediate\s*lot|End\s*lot|Lot\w*)',
    r'^(?:Price\s*Dropped|New\s*Unit)',
    r'^\d{2,3}x\d{2,3}',
    r'^Only\s*a\s*5',
    r'^International\s*School',
    r'^[A-Z]{2,4}\s+[A-Z]{3,8}$',  # CC CHUNG, DK PROPERTY
    r'^Facing\s+South',              # Facing South Gng
    r'^\d{5,}',
    r'^m\s+Rm\d',
    r'^johorproperty',
    r'^YUINN',
    r'^rry\d+\s+FOR\s+RENT',
    r'^GFshoprent',
]


def smart_title(s):
    """Title case 但保留已知缩写大寫 (JB, CIQ, R&F, KSL 等)"""
    # 先转 title
    s = s.title()
    # 修复常见缩写
    fixes = {
        ' Jb ': ' JB ',
        ' Jb,': ' JB,',
        'Jb ': 'JB ',
        ' Ciq ': ' CIQ ',
        'Ciq ': 'CIQ ',
        ' Ksl ': ' KSL ',
        'Ksl ': 'KSL ',
        ' R&Amp;F ': ' R&F ',
        'R&Amp;F ': 'R&F ',
        " D'Inspire": " D'Inspire",
        " D'inspire": " D'Inspire",
        'Sks ': 'SKS ',
        'Rm ': 'RM ',
        ' Myr ': ' MYR ',
        ' Wi-Fi ': ' Wi-Fi ',
        'Air Cond': 'Air Cond',
        'R N F ': 'RNF ',
    }
    for old, new in fixes.items():
        s = s.replace(old, new)
    return s


# 已知的关键字列表（用于在垃圾文本中搜回真正的楼盘名）
_PROPERTY_KEYWORDS = sorted([
    "R&F", "RNF", "Trellis", "Paragon", "Tritower", "Tri Tower",
    "SKS Pavillion", "SKS Pavilion", "Palazio", "Surimas",
    "Country Garden", "Danga Bay", "Twin Tower", "Twin Galaxy",
    "KSL", "Tropez", "Sky 88", "Platino", "Medini", "Meridin",
    "Forest City", "Suasana", "V Summer", "Summit", "Wateredge",
    "Pan Vista", "Bayu Marina", "Bayu Puteri", "One49",
    "Tebrau City", "Season Larkin", "Botanika", "Epic",
    "Sunway Grid", "Aloha Tower", "Aliff", "Akasa", "Ambience",
    "Dwi Mahkota", "G Residence", "Havona", "Marina",
    "Molek Regency", "Park Avenue", "Permas Ville",
    "Raffles Suites", "Senibong Villa", "Seri Mutiara",
    "Straits View", "Veranda", "Bora", "Skudai Villa",
    "Centra", "Bukit Impian", "Rich Apartment",
    "Taman Universiti", "Taman Pelangi", "Taman Molek",
    "Taman Daya", "Taman Perling", "Taman Sentosa",
    "Taman Johor Jaya", "Taman Setia Indah", "Taman Puteri Wangsa",
    "Taman Iskandar", "Taman Century", "Taman Gaya",
    "Taman Desa Jaya", "Taman Megah Ria", "Taman Kempas Indah",
    "Taman Bukit Kempas", "Taman Laguna", "Taman Scientex",
    "Taman Sierra Perdana", "Taman Suria", "Taman Tasek",
    "Taman Melodies", "Taman Abad", "Taman Adda Height",
    "Taman Gembira", "Taman Ungku Tun Aminah",
    "Johor Jaya", "Mount Austin", "Austin Heights",
    "Setia Tropika", "Bukit Indah", "Gelang Patah",
    "Iskandar Puteri", "Eco Botanic", "Eco Summer",
    "Eco Business Park", "Desa Tebrau", "Desa Harmoni",
    "Kangkar Tebrau", "Mutiara Rini", "Nusa Sentral",
    "Nusa Bestari", "Impian Emas", "Permas Jaya",
    "Johor Bahru", "Bandar Dato Onn", "Skudai", "Kulai",
    "Senai", "Larkin", "Tampoi", "Kempas", "Masai",
    "Pasir Gudang", "Tebrau", "Perling", "Tuas",
    "Kota Puteri", "Kota Masai", "Mid Valley Southkey",
    "South Key Mosaic", "Sutera Utama", "Jalan Hang Tuat",
    "Jalan Raja Udang", "Jalan Abdul Samad", "CIQ",
    "大学城", "彩虹", "碧桂园", "柔佛", "百万镇",
], key=len, reverse=True)  # 长优先


def try_extract_property(raw):
    """从混有 agent 名、FOR RENT 等垃圾的文本中提取真正的楼盘名。
    用已知关键字搜索代替简单截前缀。"""
    # 先试直接搜已知关键字
    for kw in _PROPERTY_KEYWORDS:
        if kw.lower() in raw.lower():
            return kw
    # 回退：去掉 "FOR RENT" 和常见前缀
    text = re.sub(r'^(?:FOR\s*RENT|For Rent)\s*', '', raw, flags=re.IGNORECASE).strip()
    text = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s*I+)?\s*', '', text).strip()
    if text.lower().startswith('for rent'):
        text = text[8:].strip()
    return text.strip()


def normalize(name):
    """标准化一个 property name。返回 (clean_name, was_dirty)"""
    if not name or not name.strip():
        return ("", False)

    original = name.strip()
    key = original.lower().strip().rstrip('.').replace('  ', ' ')

    # ── 1. 直接查映射表 ──
    if key in NORMALIZE_MAP:
        return (NORMALIZE_MAP[key], True)

    # ── 2. 尝试提取真正的楼盘名后再查 ──
    extracted = try_extract_property(original)
    if extracted and extracted.lower() != key:
        ek = extracted.lower().strip().replace('  ', ' ')
        if ek in NORMALIZE_MAP:
            return (NORMALIZE_MAP[ek], True)
        # 用提取后的再试
        if ek and ek != key:
            key = ek
            original = extracted

    # ── 3. 去价格后缀再查 ──
    clean_key = re.sub(r'\s*(?:RM|rm)\s*\d[\d,.]*', '', key).strip()
    if clean_key and clean_key != key and clean_key in NORMALIZE_MAP:
        return (NORMALIZE_MAP[clean_key], True)

    # ── 4. 判定是否为垃圾 ──
    for pat in GARBAGE_PATTERNS:
        if re.search(pat, original, re.IGNORECASE):
            return ("", True)

    # ── 5. 如果有中文，保留不改 ──
    if re.search(r'[\u4e00-\u9fff]', original):
        return (original, False)

    # ── 6. Smart title case ──
    fixed = smart_title(original)
    if fixed != original:
        return (fixed, True)

    return (original, False)


def clean_sheet(dry_run=True):
    creds = Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    svc = build("sheets", "v4", credentials=creds)

    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{SHEET_NAME}'!A:L"
    ).execute()
    rows = result.get("values", [])

    if len(rows) < 2:
        print("Sheet 为空或只有表头")
        return

    print(f"总行数: {len(rows) - 1} (不含表头)\n")

    changes = []
    cleaned_count = 0

    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= PROP_COL_INDEX:
            continue
        original = row[PROP_COL_INDEX].strip()
        clean, dirty = normalize(original)
        if dirty:
            agent = row[0][:20] if len(row) > 0 else "?"
            changes.append({
                "row": i, "agent": agent,
                "old": original[:45],
                "new": clean[:45] if clean else "(清空)",
            })
            cleaned_count += 1

    print(f"需要修改: {cleaned_count} 行\n")

    if cleaned_count == 0:
        print("✅ 没有需要修改的")
        return

    for c in changes[:40]:
        print(f"  行{c['row']:4d} | {c['agent'][:14]:14s} | {c['old'][:38]:38s} → {c['new']}")

    if len(changes) > 40:
        print(f"  ... 还有 {len(changes) - 40} 条")

    if dry_run:
        print(f"\n🧪 干跑模式。加 --apply 执行写入。")
        return

    # ── 写入 ──
    print(f"\n📝 正在写入 {cleaned_count} 行...")
    batch = []
    for c in changes:
        new_val = normalize(rows[c['row'] - 1][PROP_COL_INDEX])[0]
        batch.append({
            "range": f"'{SHEET_NAME}'!B{c['row']}",
            "values": [[new_val]],
        })

    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={"valueInputOption": "RAW", "data": batch},
    ).execute()
    print(f"✅ 完成！修改 {cleaned_count} 个 Property Name。")


if __name__ == "__main__":
    clean_sheet(dry_run="--apply" not in sys.argv)
