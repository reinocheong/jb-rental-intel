#!/usr/bin/env python3
"""
Facebook JB Rental Parser → Google Sheets
Reads raw JSON, extracts structured fields, appends to Google Sheets.
"""
import json, re, os, sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")  # UTC+8 Malaysia

RAW_JSON = "/home/user/fb_data/fb_posts_raw.json"
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"
SHEET_NAME = "JB Rentals"
SA_KEY_FILE = "/home/user/.hermes/google_sa_key.json"


# ============================================================
# Phone normalization
# ============================================================

def normalize_phone(raw: str) -> str:
    """Normalize phone to +60xxxxxxxxx. Returns empty string if invalid."""
    if not raw or not raw.strip():
        return ""
    
    # Split multi-number, extract first valid
    parts = re.split(r'[,;，；/\s]+', raw.strip())
    seen = set()
    
    for p in parts:
        p = p.strip()
        if not p:
            continue
        
        # Masked number (contains *)
        if '*' in p:
            continue
        
        digits = re.sub(r'\D', '', p)
        
        # Too short or too long
        if len(digits) < 8 or len(digits) > 15:
            continue
        
        # Already international: +60 / +65
        if p.startswith('+'):
            if digits.startswith('60') and 10 <= len(digits) <= 13:
                norm = '+' + digits
            elif digits.startswith('65') and 10 <= len(digits) <= 12:
                norm = '+' + digits
            else:
                continue
        # Local Malaysian: 01x → +60
        elif re.match(r'^01\d', p) and 10 <= len(digits) <= 11:
            norm = '+60' + digits[1:]
        # No prefix: 60xxxx → +60
        elif digits.startswith('60') and 10 <= len(digits) <= 13:
            norm = '+' + digits
        # Singapore local: 8xxx / 9xxx
        elif re.match(r'^[89]\d{7}$', digits):
            norm = '+65' + digits
        else:
            continue
        
        # Dedup: return first unique
        if norm not in seen:
            seen.add(norm)
            return norm
    
    return ""


# ============================================================
#  TEXT CLEANING — strip Facebook UI noise, keep post body
# ============================================================

def clean_post_text(text):
    """Remove Facebook UI noise from raw textContent."""
    if not text:
        return ""

    # ── 1. Cut at reaction summary ──
    m = re.search(r'所有心情[：:]\s*\d+', text)
    if m and m.start() > 40:
        text = text[:m.start()]
    if len(text) > 150:
        m = re.search(r'\d+条评论', text)
        if m and m.start() > 40:
            text = text[:m.start()]

    # ── 2. Strip header noise (agent name + FB metadata prefix) ──
    text = re.sub(r'火速回复\s*', '', text)
    text = re.sub(r'·\s*关注\s*', '', text)
    text = re.sub(r'·\s*\d+\s*分钟\s*', '', text)
    text = re.sub(r'·\s*\d+\s*小时\s*', '', text)
    text = re.sub(r'·\s*\d+\s*天\s*', '', text)
    text = re.sub(r'·\s*分享对象[：:]\s*公开小组\s*', '', text)
    text = re.sub(r'·\s*分享对象[：:]\s*所有朋友\s*', '', text)
    # Strip time attached to agent name (no leading ·): "Fion Foo34分钟" → "Fion Foo"
    text = re.sub(r'([\u4e00-\u9fffA-Za-z])\d+\s*(?:分钟|小时|天|周|月)\s*', r'\1 ', text)
    # Clean standalone time/datestamp after agent name
    text = re.sub(r'^\s*\d+[月天周]\d+[日号]?\s*', '', text)
    text = re.sub(r'^\s*\d+\s*分钟\s*', '', text)
    text = re.sub(r'^\s*\d+\s*小时\s*', '', text)

    # ── 3. Strip footer noise (trailing UI fragments) ──
    # Identity: "以 Reino Cheong 的身份评论" — support names with spaces
    text = re.sub(r'\s*以\s+[\s\S]+?\s+的身份\s*(?:评论|回答)\s*$', '', text)
    # Interaction bar: "发消息531赞评论分享" / "发消息赞评论分享"
    text = re.sub(r'\s*发消息\s*\d*\s*赞\s*(?:评论|回复)\s*分享\s*\d*\s*$', '', text)
    text = re.sub(r'\s*赞\s*(?:评论|回复)\s*分享\s*\d*\s*$', '', text)
    text = re.sub(r'\s*赞回复分享\s*\d*\s*$', '', text)
    # "全部N条回复"
    text = re.sub(r'\s*全部\s*\d+\s*条回复\s*$', '', text)
    # "展开+NMYR 815,000 · Location" / "收起+NMYR ..." (mid-text, not just end)
    text = re.sub(r'\s*…?\s*展开\s*\+?\d*\s*(?:MYR|RM|US\$)\s*[\d,]+\s*·\s*[^·]+', '', text)
    text = re.sub(r'\s*…?\s*收起\s*\+?\d*\s*(?:MYR|RM|US\$)\s*[\d,]+\s*·\s*[^·]+', '', text)
    # Also catch bare "展开+N" / "收起+N" without location
    text = re.sub(r'\s*…?\s*展开\s*\+?\d*\s*(?:MYR|RM|US\$)?\s*[\d,]+', '', text)
    text = re.sub(r'\s*…?\s*收起\s*\+?\d*\s*(?:MYR|RM|US\$)?\s*[\d,]+', '', text)
    # Lone "展开" / "收起" at end
    text = re.sub(r'\s*展开\s*$', '', text)
    text = re.sub(r'\s*收起\s*$', '', text)
    # Time suffixes: "25周" / "12周赞回复分享已编辑"
    text = re.sub(r'\s*\d+\s*[周天月年]\s*(?:赞回复分享已编辑)?\s*$', '', text)
    text = re.sub(r'\s*\d+\s*(?:分钟|小时|秒)\s*$', '', text)

    # ── 4. Mid-text noise ──
    # "· 分享对象： 公开小组" appearing mid-text (after header already stripped)
    text = re.sub(r'·\s*分享对象[：:]\s*公开小组\s*', '', text)
    text = re.sub(r'·\s*分享对象[：:]\s*所有朋友\s*', '', text)

    # Collapse multiple spaces
    text = re.sub(r'\s{2,}', ' ', text)

    return text.strip()


def is_comment_thread(text):
    """Detect '评论区缝合怪' — posts that are comment threads, not original listings.
    
    Indicators:
    - Multiple "某人Pm" / "某人赞回复分享" patterns (other people replying)
    - "全部N条回复" or "查看 N 条回复" (nested replies)
    - "展开+N" in comment context
    - "查看更多评论/回答"
    """
    commenter_replies = len(re.findall(r'[^\s·]{2,20}(?:Pm|赞回复分享|·\s*关注)', text))
    nested_replies = len(re.findall(r'(?:全部|查看)\s*\d+\s*条回复', text))
    expand_comments = len(re.findall(r'展开\+\d+', text))
    more_links = len(re.findall(r'查看更多(?:评论|回答)', text))
    identity_end = 1 if re.search(r'以\s+[\s\S]+?\s+的身份(?:评论|回答)', text) else 0
    
    score = commenter_replies * 3 + nested_replies * 5 + expand_comments * 2 + more_links * 3 + identity_end * 3
    return score >= 6


def is_rental_post(text):
    """Reject non-rental/property posts (phones, cars, etc.)."""
    first100 = text[:100]
    phone_brands = r'IPHONE|iphone|SAMSUNG|HUAWEI|XIAOMI|honor|vivo|OPPO|手机\s*(?:出售|卖|转)'
    car_brands = r'[Mm][Yy][Vv][Ii]|[Pp][Ee][Rr][Oo][Dd][Uu][Aa]|[Pp][Rr][Oo][Tt][Oo][Nn]|HONDA|TOYOTA|NISSAN'
    
    if re.search(phone_brands, first100):
        return False
    if re.search(car_brands, text):
        return False
    return True


def is_looking_for_rental(text):
    """Detect 求租 (looking for rental) posts — NOT what we want.
    
    We ONLY want 出租 (offering for rent). These are tenants/house-hunters:
    - 找/寻找/要找 + 房/屋/房间/屋子
    - budget RMxxx (without explicit FOR RENT)
    - 想找/要找/寻找 at start or early in post
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Strong indicators of "looking for" (求租)
    looking_patterns = [
        r'(?:我|我们|本人)?(?:想|要|正在|在)(?:找|寻找|找着)(?:房|屋|房间|屋子|整间)',
        r'(?:找|寻找)(?:靠近|近|附近)',
        r'^.{0,20}找.{0,10}(?:房|屋|studio|room|condo|apartment)',
        r'budget\s*(?:RM|rm)?\s*\d+',  # budget without FOR RENT
        r'(?:什么|谁有|有没有).{0,10}(?:介绍|出租|房子)',
        r'谢绝agent',  # tenants often say this
        r'不要中介', 
        r'直接对屋主',  # tenants want direct landlord
    ]
    
    for pat in looking_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    
    return False

# --- Field definitions ---
HEADERS = [
    "Agent Name",      # A
    "Property Name",   # B
    "Listing Type",    # C  出租/出售
    "Property Type",   # D
    "Rooms",           # E  几房几厕
    "Furnishing",      # F  全家私/半家私/无家私
    "Rent (RM)",       # G  (sale posts: left blank)
    "Phone",           # H
    "Link",            # I
    "Remark",          # J
    "Scraped At",      # K
    "Post Text",       # L  原始帖文
]

# ----- Property names (common JB developments) -----
# 格式：[匹配关键字, ...]
# 匹配时大小写不敏感，输出用 canonical 形式
KNOWN_PROPERTIES = [
    # ── 高层/公寓 ──
    "R&F Princess Cove", "R&F", "RNF", "R and F", "Princess Cove",
    "Tri Tower", "Tritower",
    "Trellis Residence", "Trellis",
    "Paragon Residences", "Paragon Suites", "Paragon",
    "SKS Pavilion", "SKS Pavillion",
    "Country Garden", "碧桂园",
    "KSL Residence", "KSL Resident", "KSL D'Inspire", "D'Inspire",
    "Danga Bay",
    "Twin Tower", "Twin Galaxy",
    "Palazio Apartment", "Palazio",
    "Surimas Suites", "Surimas",
    "One49 Residence",
    "Tropez Residence", "Tropez",
    "Sky 88", "Sky88",
    "The Platino", "Platino",
    "Meridin Medini", "Meridin",
    "Bayu Marina", "Bayu Puteri",
    "V Summer",
    "Suasana Suites", "Suasana",
    "Forest City",
    "Summit Residence", "Summit",
    "Wateredge Residence", "Wateredge",
    "Pan Vista Apartment", "Pan Vista",
    "Tebrau City Residence", "Tebrau City",
    "Season Larkin Apartment", "Season Larkin", "Season Apartment",
    "Botanika",
    "Epic Residence",
    "Sunway Grid Residence", "Sunway Grid",
    "Aloha Tower",
    "The Aliff Residence", "Aliff Residence",
    "Akasa Condo", "Akasa",
    "Ambience Residence",
    "Dwi Mahkota Condo",
    "G Residence",
    "The Garden Residence", "Garden Residence",
    "Havona",
    "Marina Residence", "Marina Apartment",
    "Molek Regency",
    "Park Avenue Apartment",
    "Permas Ville Apartment",
    "The Raffles Suites",
    "Rich Apartment",
    "Senibong Villa",
    "Seri Mutiara Apartment",
    "The Straits View Condo", "Straits View Condo",
    "Veranda Residence",
    "Bora Residence",
    "Skudai Villa",
    "Bukit Impian Residence",
    "Centra Residence",
    "1 Tebrau Residence",
    "The Aliff",
    # ── Taman 系列 ──
    "Taman Universiti", "大学城",
    "Taman Pelangi", "Pelangi", "彩虹",
    "Taman Molek",
    "Taman Daya",
    "Taman Perling", "Perling",
    "Taman Sentosa",
    "Taman Johor Jaya",
    "Taman Setia Indah",
    "Taman Puteri Wangsa",
    "Taman Iskandar",
    "Taman Century",
    "Taman Gaya",
    "Taman Desa Jaya",
    "Taman Megah Ria",
    "Taman Kempas Indah",
    "Taman Bukit Kempas",
    "Taman Laguna",
    "Taman Scientex",
    "Taman Sierra Perdana",
    "Taman Suria",
    "Taman Tasek",
    "Taman Melodies",
    "Taman Abad",
    "Taman Adda Height",
    "Taman Gembira",
    "Taman Ungku Tun Aminah",
    "Taman JP Perdana",
    "Taman Perumahan Rakyat Lima Kedai",
    # ── 区域/城镇 ──
    "Johor Jaya",
    "Mount Austin",
    "Austin Heights",
    "Setia Tropika",
    "Bukit Indah",
    "Gelang Patah",
    "Iskandar Puteri",
    "Eco Botanic",
    "Eco Summer",
    "Eco Business Park 1",
    "Desa Tebrau",
    "Desa Harmoni",
    "Kangkar Tebrau",
    "Mutiara Rini",
    "Nusa Sentral",
    "Nusa Bestari",
    "Impian Emas",
    "Permas Jaya", "百万镇",
    "Johor Bahru",
    "Bandar Dato Onn",
    "Skudai",
    "Kulai",
    "Senai",
    "Larkin",
    "Tampoi",
    "Kempas",
    "Masai",
    "Pasir Gudang",
    "Tebrau",
    "Tuas",
    "Medini",
    "Sutera Utama",
    "Jalan Hang Tuat",
    "Jalan Raja Udang",
    "Jalan Abdul Samad",
    "Mid Valley Southkey",
    "South Key Mosaic",
    "CIQ",
    "Kota Masai",
    "Tiram",
]

# ── 标准化映射：任意变体 → canonical 名称 ──
PROPERTY_NORMALIZE = {
    # R&F
    "r&f": "R&F Princess Cove", "rnf": "R&F Princess Cove",
    "r and f": "R&F Princess Cove", "princess cove": "R&F Princess Cove",
    # Tri Tower
    "tritower": "Tri Tower", "tri tower": "Tri Tower",
    # Trellis
    "trellis residence": "Trellis Residence", "trellis": "Trellis Residence",
    "trellis residensi": "Trellis Residence",
    # Paragon
    "paragon suites": "Paragon Residences", "paragon residence": "Paragon Residences",
    "paragon": "Paragon Residences",
    # SKS
    "sks pavillion": "SKS Pavilion", "sks pavillion residence": "SKS Pavilion",
    "sks pavilion": "SKS Pavilion",
    # KSL
    "ksl residence": "KSL Residence", "ksl resident": "KSL Residence",
    "ksl d'inspire": "KSL D'Inspire", "d'inspire": "KSL D'Inspire",
    # Country Garden
    "country garden": "Country Garden", "碧桂园": "Country Garden",
    # Twin
    "twin tower": "Twin Tower", "twin galaxy": "Twin Galaxy",
    # Others
    "palazio": "Palazio Apartment", "palazio apartment": "Palazio Apartment",
    "surimas": "Surimas Suites", "surimas suites": "Surimas Suites",
    "one49": "One49 Residence", "one49 residence": "One49 Residence",
    "tropez": "Tropez Residence", "tropez residence": "Tropez Residence",
    "sky 88": "Sky 88", "sky88": "Sky 88",
    "platino": "The Platino", "the platino": "The Platino",
    "meridin": "Meridin Medini", "meridin medini": "Meridin Medini",
    "bayu marina": "Bayu Marina", "bayu puteri": "Bayu Puteri",
    "v summer": "V Summer", "suasana": "Suasana Suites",
    "forest city": "Forest City",
    "summit": "Summit Residence", "summit residence": "Summit Residence",
    "wateredge": "Wateredge Residence",
    "pan vista": "Pan Vista Apartment",
    # Areas
    "pelangi": "Taman Pelangi", "彩虹": "Taman Pelangi",
    "大学城": "Taman Universiti", "taman universiti": "Taman Universiti",
    "bukit indah": "Bukit Indah", "johor jaya": "Johor Jaya",
    "mount austin": "Mount Austin", "setia tropika": "Setia Tropika",
    "gelang patah": "Gelang Patah", "iskandar puteri": "Iskandar Puteri",
    "desa tebrau": "Desa Tebrau", "mutiara rini": "Mutiara Rini",
    "nusa sentral": "Nusa Sentral", "permas jaya": "Permas Jaya",
    "百万镇": "Permas Jaya", "skudai": "Skudai", "kulai": "Kulai",
    "senai": "Senai", "larkin": "Larkin", "tampoi": "Tampoi",
    "tebrau": "Tebrau", "medini": "Medini", "perling": "Taman Perling",
    "tuas": "Tuas", "pasir gudang": "Pasir Gudang",
    "kota masai": "Kota Masai",
}

# ── 垃圾关键词黑名单：匹配到则拒绝整个提取结果 ──
PROPERTY_NAME_BLACKLIST = {
    # 人名常见后缀
    'chong', 'lee', 'goh', 'loh', 'tan', 'wong', 'lim', 'chen', 'pong',
    'koh', 'lye', 'loo', 'liew', 'teo', 'ng', 'foo', 'chan', 'yap',
    'chin', 'sia', 'tee', 'ooi', 'seng',
    # 属性
    'for rent', 'for sale', '出租', '出售', '房间出租',
    'fully furnished', 'partial furnished', 'unfurnished', 'full furnish',
    'master room', 'master bedroom', 'common room', 'middle room',
    'small room', 'balcony room', 'single storey', 'double storey',
    'wifi', 'unifi', 'deposit', 'freehold', 'leasehold', 'bumi lot',
    'guarded', 'gated', 'food court', 'living hall', 'toilet',
    'bathroom', 'bedroom', 'high floor', 'nice view', 'smart lock',
    'internet included', 'utilities included', 'ce floor',
    # FB 噪音
    'real estate', 'whatsapp', 'please contact', 'call or',
    'no agent', '不要中介', 'teamgather', 'roof realty',
    'properties sdn bhd', 'stabilisation', 'submaster',
    'untuk dijual', 'brand new', 'new launch', 'new unit',
    'end lot', 'intermediate lot', 'land size',
    'xiao hong shu', 'xiaohongshu',
    # 杂项
    'residences', 'service apartment', 'jbcondo', 'ciq room for rent',
    'need room', 'looking for', 'walk to ksl', 'rts',
}

def normalize_property_name(raw_name):
    """标准化楼盘名。返回 canonical 名称，若无法识别则返回原值。"""
    if not raw_name or not raw_name.strip():
        return ""
    
    name = raw_name.strip()
    key = name.lower().strip().rstrip('.').replace('  ', ' ')
    
    # ── 查标准化映射 ──
    if key in PROPERTY_NORMALIZE:
        return PROPERTY_NORMALIZE[key]
    
    # ── 去掉价格后缀再查 ──
    clean = re.sub(r'\s*(?:RM|rm)\s*\d[\d,.]*', '', key).strip()
    if clean and clean != key and clean in PROPERTY_NORMALIZE:
        return PROPERTY_NORMALIZE[clean]
    
    # ── 简单 title case（保留中文） ──
    if re.search(r'[\u4e00-\u9fff]', name):
        return name
    
    # Smart title
    fixed = name.title()
    # 修复常见缩写
    for abbr in ['JB', 'CIQ', 'KSL', 'SKS', 'R&F', 'RNF', 'MYR', 'Wi-Fi', "D'Inspire"]:
        fixed = re.sub(r'\b' + re.escape(abbr.lower()) + r'\b', abbr, fixed, flags=re.IGNORECASE)
    
    return fixed


def _is_valid_property_name(name):
    """拒绝明显的垃圾：人名、价格、属性描述。"""
    if not name or len(name) < 2:
        return False
    
    key = name.lower().strip()
    
    # 精确命中黑名单
    if key in PROPERTY_NAME_BLACKLIST:
        return False
    
    # 部分命中黑名单（至少 4 字符才判断，避免误杀短名）
    for bw in PROPERTY_NAME_BLACKLIST:
        if len(bw) >= 4 and bw in key:
            return False
    
    # 纯价格模式
    if re.match(r'^(?:RM|rm)\s*\d[\d,.]*$', name):
        return False
    
    # 纯数字
    if re.match(r'^\d+$', name):
        return False
    
    # 人名模式：首字母大写 + 常见姓
    if re.match(r'^[A-Z][a-z]+\s+(?:Chong|Lee|Goh|Loh|Tan|Wong|Lim|Chen)$', name):
        return False
    
    # 全大写缩写 ≥ 3 字母（CC、REN、D75、HGM、TRR...）
    if re.match(r'^[A-Z0-9]{3,}$', name):
        return False
    
    # 全大写字母+空格模式: "CC CHUNG", "DK PROPERTY"
    if re.match(r'^[A-Z]{2,4}\s+[A-Z]{3,}$', name):
        return False
    
    # 全大写字母+数字模式: "REN69697"
    if re.match(r'^[A-Z]{2,4}\d{3,}', name):
        return False
    
    # 以 "FOR RENT" / "For Sale" 开头
    if re.match(r'^(?:FOR|For)\s+(?:RENT|SALE)', name):
        return False
    
    return True


def extract_listing_type(text):
    """Detect if post is FOR RENT or FOR SALE."""
    text_lower = text.lower()
    
    # ── Strong sale signals ──
    sale_strong = [
        r'\bfor\s*sale\b', r'出售', r'售卖', r'selling price',
        r'\bRM\s*[\d,]+\s*k\b',  # RM 500k, RM688k → sale
        r'\bRM\s*[\d,]{6,}\b',   # RM 500,000+ → sale
        r'卖\s*(?:RM|rm)', r'sale price',
        r'brand new', r'new launch',
    ]
    for pat in sale_strong:
        if re.search(pat, text, re.IGNORECASE):
            return '出售'
    
    # ── Weak sale: price >= 50k without rent context ──
    m = re.search(r'(?:RM|rm)\s*([\d,]{3,6})\b', text)
    if m:
        try:
            val = int(m.group(1).replace(',', ''))
            if val >= 50000:
                # Check for rent keywords nearby
                window = text[max(0,m.start()-60):m.end()+60]
                if not any(kw in window.lower() for kw in ['rent', '出租', '租金', 'per month']):
                    return '出售'
        except ValueError:
            pass
    
    # ── Rent signals ──
    rent_patterns = [
        r'\bfor\s*rent\b', r'出租', r'房间出租', r'屋子出租', r'招租',
        r'rental', r'tenants?',
        r'包水电', r'per month', r'/month',
    ]
    for pat in rent_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return '出租'
    
    # Default: rent (most groups are rental-focused)
    return '出租'

def extract_property_name(text):
    """Extract property location/name from post text.
    所有返回结果都经过 normalize_property_name() 标准化。"""
    text_lower = text.lower()
    
    # ── Agent name blacklist for Pattern 2 ──
    # 如果匹配到的词是常见人名，跳过
    _agent_first_names = {
        'angela', 'crystal', 'jacelyn', 'sally', 'sandra', 'jac', 'kedy',
        'jeddy', 'eugene', 'janet', 'jessrene', 'jess', 'esther', 'nicole',
        'diane', 'puyol', 'yuxiu', 'jeny', 'ebby', 'jia hui', 'jia xin',
        'qian han', 'yu ern', 'yoklen', 'keith', 'kent', 'fionna', 'vincy',
        'kenny', 'benjamin', 'tommy', 'brandon', 'darren', 'chew', 'yii',
        'yeow', 'mei', 'ling', 'royce', 'soh', 'hui jing', 'elaine', 'alice',
        'ivan', 'song', 'well', 'cheksiang', 'molly', 'ervin', 'adeline',
        'yi yi', 'bibi', 'cindle', 'jie', 'wan', 'sukky', 'joe', 'peace',
        'ke', 'bright', 'may', 'bee', 'beng', 'jane', 'jason', 'joyce',
        'john', 'ck', 'day', 'jocelyn', 'yong', 'long', 'mystical',
        'sabrina', 'dawn', 'four', 'anne', 'ost', 'matthew', 'lim',
        'sim', 'yvonne', 'kc',
    }
    
    def is_valid_name(name):
        if not name or len(name) < 2:
            return False
        key = name.lower().strip()
        # 检查是否为人名
        if key in _agent_first_names:
            return False
        return True

    # Pattern 1: Explicit "地点：XXX" / "Location: XXX"
    m = re.search(r'(?:地点|location)\s*[：:]\s*([^（(\n，,]{2,40})', text, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        if is_valid_name(name):
            return normalize_property_name(name)

    # Pattern 2: Capitalized name before parentheses: "V Summer(走路"
    # Fixed: skip if match is an agent first name
    m = re.search(r'([A-Z][a-zA-Z0-9\s\-]{2,30}?)(?:[（(])', text)
    if m:
        name = m.group(1).strip()
        if re.search(r'[A-Z]', name) and len(name) >= 3 and is_valid_name(name):
            return normalize_property_name(name)

    # Pattern 3: "XXX Residence/Apartment/Condo/Residensi/Tower/Villa/Court/Suites"
    # Fixed: require the word before suffix to start with capital letter (not "Fully Furnished")
    m = re.search(r'([A-Z][A-Za-z0-9\s\-]{2,30}?)\s*(?:Residence|Residensi|Apartment|Condo|Resort|Tower|Villa|Court|Suites)', text, re.IGNORECASE)
    if m:
        name = m.group(0).strip()
        if len(name) >= 3 and is_valid_name(name) and not name.lower().startswith(('fully', 'partial', 'semi', 'un')):
            return normalize_property_name(name)

    # Pattern 4: Check known properties (use new expanded list)
    for prop in KNOWN_PROPERTIES:
        if prop.lower() in text_lower:
            return normalize_property_name(prop)

    # Pattern 5: Generic address patterns
    addr_patterns = [
        r'(?:Taman|Tmn\.?)\s+([A-Za-z\s]+)',
        r'Jalan\s+([A-Za-z\s]+\d*)',
    ]
    for pat in addr_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(0).strip()
            return normalize_property_name(raw)

    return ""


def extract_property_type(text):
    """Extract property type."""
    types = {
        "双层排屋": "双层排屋", "Double Storey": "双层排屋", "double storey": "双层排屋",
        "单层排屋": "单层排屋", "Single Storey": "单层排屋", "single storey": "单层排屋",
        "排屋": "排屋", "Terrace": "排屋",
        "Studio": "Studio", "studio": "Studio",
        "公寓": "公寓", "Apartment": "公寓", "apartment": "公寓",
        "Condo": "公寓", "condo": "公寓", "Condominium": "公寓",
        "Flat": "Flat", "flat": "Flat",
        "半独立": "半独立", "Semi-D": "半独立", "semi d": "半独立",
        "独立式": "独立式", "Bungalow": "独立式", "bungalow": "独立式",
        "Townhouse": "Townhouse",
        "中房": "中房", "Middle Room": "中房", "common room": "中房",
        "小房": "小房", "Small Room": "小房",
        "大房": "大房", "Master Room": "大房", "master room": "大房",
        "房间": "房间", "Room": "房间", "whole unit": "整间",
    }
    text_lower = text.lower()
    # Sort by length (longest first) to match more specific types
    for key in sorted(types.keys(), key=len, reverse=True):
        if key.lower() in text_lower:
            return types[key]
    return ""


def extract_rooms(text):
    """Extract room count: 几房几厕 / X房Y厕 / X bed Y bath"""
    # Chinese patterns: 4房3厕, 3房2浴
    m = re.search(r'(?:^|\s)(\d+)\s*房\s*(\d+)\s*[厕浴]', text)
    if m:
        return f"{m.group(1)}房{m.group(2)}厕"

    # English patterns: 3 bed 2 bath, 3 bedroom 2 bathroom
    m = re.search(r'(?:^|\s)(\d+)\s*bed(?:room)?s?\s*(\d+)\s*bath(?:room)?s?', text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}房{m.group(2)}厕"

    # Single count: 4房, 3 rooms (with word boundary)
    m = re.search(r'\b(\d+)\s*房\b', text)
    if m:
        return f"{m.group(1)}房"

    m = re.search(r'\b(\d+)\s*bed(?:room)?\b', text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}房"

    return ""


def extract_rent(text):
    """Extract rent amount in RM from post text.
    
    Handles: RM 1600, RM1,600, RM 1.2k, Rental: RM 900, 租金 RM 1200
    Returns integer RM amount, or empty string.
    Ignores sale prices (>= 50k typically) unless context says rent.
    """
    if not text:
        return ""

    # ── Normalize: expand RM 1.2k → RM 1200, RM1.8k → RM 1800 ──
    # Also normalize MYR → RM (FB uses both)
    def expand_k(m):
        num = m.group(1).replace(',', '')
        try:
            return f'RM {int(float(num) * 1000)}'
        except ValueError:
            return m.group(0)
    text_expanded = re.sub(r'(?:RM|rm|MYR|myr)\s*([\d.]+)\s*k\b', expand_k, text, flags=re.IGNORECASE)
    # Normalize MYR → RM (FB uses +NMYR or MYR)
    text_expanded = re.sub(r'\+?\d*\s*(?:MYR|myr)', ' RM', text_expanded)

    # ── Pattern 1: RM before number (most common) ──
    # RM 1600, RM1,600, RM 1,200, rm900, RM1400
    m = re.search(r'(?:RM|rm)\s*([\d,]{3,8})\b', text_expanded)
    if m:
        try:
            val = int(m.group(1).replace(',', ''))
            # Skip sale-like prices (>50k typically sale, unless rental keyword nearby)
            if val < 50000 or _has_rental_context(text, m.start()):
                return val
        except ValueError:
            pass

    # ── Pattern 2: "Rental RM xxxx" / "Rental: RM xxxx" / "租金 RM xxxx" ──
    m = re.search(r'(?:Rental|RENTAL|rental|租金|Rent\b)\s*:?\s*(?:RM|rm)?\s*([\d,]{3,6})\b', text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(',', ''))
        except ValueError:
            pass

    # ── Pattern 3: Number before RM ──
    m = re.search(r'([\d,]{3,5})\s*(?:RM|rm)\b', text_expanded)
    if m:
        try:
            val = int(m.group(1).replace(',', ''))
            if val < 50000:
                return val
        except ValueError:
            pass

    # ── Pattern 4: number at end of post with rent context ──
    m = re.search(r'(?:budget|租金|rent)\D*([\d,]{3,5})\b', text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(',', ''))
        except ValueError:
            pass

    # ── Pattern 5: standalone 3-4 digit number at very end ──
    m = re.search(r'\b([\d,]{3,4})\s*$', text.strip())
    if m:
        try:
            val = int(m.group(1).replace(',', ''))
            if 100 <= val < 50000:
                return val
        except ValueError:
            pass

    return ""


def _has_rental_context(text, pos):
    """Check if text near position has rental keywords (not sale)."""
    window = text[max(0, pos-60):pos+60]
    rental_kw = ['rent', 'rental', '出租', '租金', '月租', 'per month', '/month', '包水电']
    sale_kw = ['sale', '出售', 'selling', '售价', 'for sale']
    
    has_rental = any(kw in window.lower() for kw in rental_kw)
    has_sale = any(kw in window.lower() for kw in sale_kw)
    
    return has_rental and not has_sale


def extract_furnishing(text):
    """Extract furnishing status: 全家私 / 半家私 / 无家私"""
    text_lower = text.lower()
    if re.search(r'[全齐]家[私俱]|fully furnished|full[-\s]?furnish', text_lower):
        return '全家私'
    if re.search(r'半家[私俱]|partial[-\s]?furnish|semi[-\s]?furnish', text_lower):
        return '半家私'
    if re.search(r'\bunfurnished\b|无家[私俱]|没有家[私俱]|kosong', text_lower):
        return '无家私'
    return ''


def extract_remark(text, property_name="", property_type="", rooms=""):
    """Extract remarks: facilities, features, owner-info (EXCLUDING furnishing)."""
    keywords = []

    checks = [
        (r'包水电', '包水电'),
        (r'包[热水冷气网]', '包设施'),
        (r'屋主[自租]', '屋主自租'),
        (r'我是屋主', '屋主直租'),
        (r'no agent', '无中介'),
        (r'不要中介', '无中介'),
        (r'新[装修翻]', '新装修'),
        (r'近\s*CIQ', '近CIQ'),
        (r'CIQ', '近CIQ'),
        (r'[走靠]?[路近].*[CIQ关]', '近CIQ'),
        (r'新马[通勤往来]', '新马通勤'),
        (r'停[车位]', '有停车位'),
        (r'parking', '有停车位'),
        (r'car.?park', '有停车位'),
        (r'冷气', '有冷气'),
        (r'air.?cond', '有冷气'),
        (r'双人床', '双人床'),
        (r'私人[厕浴]', '私人厕所'),
        (r'洗衣机', '有洗衣机'),
        (r'冰[箱厨]', '有冰箱'),
        (r'可[以能煮]', '可煮'),
        (r'[女男]孩[子生]', '限女生' if '女' in text else '限男生'),
        (r'female only', '限女生'),
        (r'male only', '限男生'),
    ]

    for pattern, label in checks:
        if re.search(pattern, text, re.IGNORECASE):
            if label not in keywords:
                keywords.append(label)

    # Remove duplicates from property type / rooms
    if property_type and property_type not in keywords:
        pass  # keep type separate

    return "; ".join(keywords) if keywords else ""


def format_scraped_at(iso_str):
    """Convert ISO UTC string to Malaysia time: '2026-05-09 17:45:30'"""
    if not iso_str:
        return ""
    try:
        # Parse ISO format (with or without timezone)
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        # Convert to Malaysia time
        dt_my = dt.astimezone(MY_TZ)
        return dt_my.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str[:19] if iso_str else ""


def parse_post(post):
    """Parse one raw post into structured fields."""
    raw_text = post.get("text", "")
    text = clean_post_text(raw_text)  # strip FB UI noise
    agent = post.get("agent_name", "")
    phone = normalize_phone(post.get("phone", ""))
    link = post.get("link", "")
    scraped_at = post.get("scraped_at", "")
    group_name = post.get("group_name", "")

    # If agent name empty or is FB generated username, try harder from text
    _fb_name = re.compile(r'^[A-Z][a-z]{3,}[A-Z][a-z]{3,}\d*$')
    if not agent or _fb_name.match(agent):
        m = re.match(r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)', text)
        if m and not _fb_name.match(m.group(1)):
            agent = m.group(1)
        else:
            m = re.match(r'^([\u4e00-\u9fff]{2,4})', text)
            if m:
                agent = m.group(1)
        # If still FB generated, clear it
        if agent and _fb_name.match(agent):
            agent = ''

    prop_name = extract_property_name(text)
    # Final validation: reject if normalize still produces garbage
    if prop_name and not _is_valid_property_name(prop_name):
        prop_name = ""
    listing_type = extract_listing_type(text)
    prop_type = extract_property_type(text)
    rooms = extract_rooms(text)
    furnishing = extract_furnishing(text)
    
    # Rent: extract from RAW text (prices often in FB tags that get cleaned out)
    # Then fall back to cleaned text
    rent = ""
    price_remark = ""
    if listing_type == "出租":
        rent = extract_rent(raw_text) or extract_rent(text)
    else:
        m = re.search(r'(?:RM|rm)\s*(\d[\d,.]{2,6})', raw_text)
        if m:
            try:
                price_remark = f"售价: RM{int(m.group(1).replace(',','')):,}"
            except:
                price_remark = f"售价: RM{m.group(1)}"
    
    remark = extract_remark(text, prop_name, prop_type, rooms)
    if price_remark:
        remark = f"{price_remark}; {remark}" if remark else price_remark
    if group_name and group_name not in remark:
        remark = f"[{group_name}] {remark}".strip()

    return {
        "agent": agent,
        "property": prop_name,
        "listing_type": listing_type,
        "type": prop_type,
        "rooms": rooms,
        "furnishing": furnishing,
        "rent": rent,
        "phone": phone,
        "link": link,
        "remark": remark,
        "scraped_at": format_scraped_at(scraped_at),  # 2026-05-09 17:45:30 (Malaysia time)
        "post_text": text,
    }


def get_sheets_service():
    """Authenticate and return Google Sheets service (Service Account)."""
    creds = Credentials.from_service_account_file(SA_KEY_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds)
def build_sheets():
    """Read raw JSON, parse, append to Google Sheets."""
    service = get_sheets_service()
    sheet = service.spreadsheets()

    # Load raw data
    raw_posts = []
    if os.path.exists(RAW_JSON):
        with open(RAW_JSON, "r") as f:
            raw_posts = json.load(f)

    # Parse all posts — clean first, then filter (order: 求租 > comment_thread > non_rental)
    parsed = []
    seen = set()
    skipped = {"comment_thread": 0, "non_rental": 0, "looking": 0}
    for post in raw_posts:
        raw_text = post.get("text", "")
        cleaned = clean_post_text(raw_text)
        
        # Filter 1: Reject 求租 (looking for rental) — check BEFORE comment_thread
        #            because 求租 posts attract many replies, inflating comment score
        if is_looking_for_rental(cleaned) or is_looking_for_rental(raw_text):
            skipped["looking"] += 1
            continue
        
        # Filter 2: Reject non-rental (phones, cars)
        if not is_rental_post(raw_text):
            skipped["non_rental"] += 1
            continue
        
        # Filter 3: Reject comment threads without real post body
        if is_comment_thread(raw_text):
            skipped["comment_thread"] += 1
            continue
        
        row = parse_post(post)
        # Deduplicate by link
        key = row["link"]
        if key in seen:
            continue
        seen.add(key)
        parsed.append(row)

    # Read existing data from Google Sheets for dedup
    existing_links = set()
    existing_phones = set()
    existing_texts = set()
    
    try:
        result = sheet.values().get(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A:L"
        ).execute()
        values = result.get("values", [])
        if values:
            for row in values[1:]:  # Skip header
                if len(row) > 8 and row[8]:
                    existing_links.add(row[8])  # Link column (I, index 8)
                if len(row) > 7 and row[7]:
                    for p in str(row[7]).split(','):
                        p = p.strip()
                        if p:
                            existing_phones.add(p)
                # Text-based dedup: property + type + rooms combo
                prop = row[1] if len(row) > 1 else ""
                ptype = row[3] if len(row) > 3 else ""
                prooms = row[4] if len(row) > 4 else ""
                prent = row[6] if len(row) > 6 else ""
                key = f"{prop}|{ptype}|{prooms}|{prent}"
                if key.strip('|'):
                    existing_texts.add(key)
        total_rows = len(values)
    except Exception:
        total_rows = 0

    # Filter out duplicates
    unique_parsed = []
    for row_data in parsed:
        # Dedup by link
        if row_data["link"] and row_data["link"] in existing_links:
            continue
        # Dedup by phone
        if row_data["phone"]:
            phones = [p.strip() for p in row_data["phone"].split(',') if p.strip()]
            if any(p in existing_phones for p in phones):
                continue
        # Dedup by property+type+rooms+rent combo
        key = f"{row_data['property']}|{row_data['type']}|{row_data['rooms']}|{row_data['rent']}"
        if key.strip('|') and key in existing_texts:
            continue
        
        unique_parsed.append(row_data)
        # Track for future dedup
        if row_data["link"]:
            existing_links.add(row_data["link"])
        if row_data["phone"]:
            for p in row_data["phone"].split(','):
                p = p.strip()
                if p:
                    existing_phones.add(p)
        if key.strip('|'):
            existing_texts.add(key)

    # If no existing data, write headers first
    if total_rows == 0:
        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A1:L1",
            body={"values": [HEADERS]},
            valueInputOption="RAW"
        ).execute()
        total_rows = 1

    # Append new rows
    new_rows = 0
    if unique_parsed:
        next_row = total_rows + 1
        values = []
        for row_data in unique_parsed:
            values.append([
                row_data["agent"],
                row_data["property"],
                row_data["listing_type"],
                row_data["type"],
                row_data["rooms"],
                row_data["furnishing"],
                row_data["rent"],
                row_data["phone"],
                row_data["link"],
                row_data["remark"],
                row_data["scraped_at"],
                row_data["post_text"],
            ])
        
        end_col = chr(64 + len(HEADERS))
        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A{next_row}:{end_col}{next_row + len(values) - 1}",
            body={"values": values},
            valueInputOption="RAW"
        ).execute()
        new_rows = len(values)

    return {
        "total_rows": total_rows + new_rows - (1 if total_rows == 0 else 0),
        "new_rows": new_rows,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
        "parsed": unique_parsed,
        "skipped": skipped,
    }


if __name__ == "__main__":
    result = build_sheets()
    print(json.dumps({
        "total": result["total_rows"],
        "new": result["new_rows"],
        "skipped": result["skipped"],
        "sheet_url": result["sheet_url"],
        "preview": [
            {k: v for k, v in p.items() if k not in ("photos",)}
            for p in result["parsed"][:5]
        ]
    }, ensure_ascii=False, indent=2))
