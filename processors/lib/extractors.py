"""Field extraction logic."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .property_data import normalize_property_name, is_valid_property_name, KNOWN_PROPERTIES
from .phone_utils import normalize_phone

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")

def extract_listing_type(text):
    """Detect if post is FOR RENT or FOR SALE."""
    text_lower = text.lower()
    sale_strong = [
        r'\bfor\s*sale\b', r'出售', r'售卖', r'selling price',
        r'\bRM\s*[\d,]+\s*k\b', r'\bRM\s*[\d,]{6,}\b',
        r'卖\s*(?:RM|rm)', r'sale price', r'brand new', r'new launch',
    ]
    for pat in sale_strong:
        if re.search(pat, text, re.IGNORECASE):
            return '出售'
    m = re.search(r'(?:RM|rm)\s*([\d,]{3,6})\b', text)
    if m:
        try:
            val = int(m.group(1).replace(',', ''))
            if val >= 50000:
                window = text[max(0,m.start()-60):m.end()+60]
                if not any(kw in window.lower() for kw in ['rent', '出租', '租金', 'per month']):
                    return '出售'
        except ValueError:
            pass
    rent_patterns = [
        r'\bfor\s*rent\b', r'出租', r'房间出租', r'屋子出租', r'招租',
        r'rental', r'tenants?', r'包水电', r'per month', r'/month',
    ]
    for pat in rent_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return '出租'
    return '出租'

def extract_property_name(text):
    """Extract property location/name from post text."""
    text_lower = text.lower()
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
        if not name or len(name) < 2: return False
        if name.lower().strip() in _agent_first_names: return False
        return True

    m = re.search(r'(?:地点|location)\s*[：:]\s*([^（(\n，,]{2,40})', text, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        if is_valid_name(name): return normalize_property_name(name)

    m = re.search(r'([A-Z][a-zA-Z0-9\s\-]{2,30}?)(?:[（(])', text)
    if m:
        name = m.group(1).strip()
        if re.search(r'[A-Z]', name) and len(name) >= 3 and is_valid_name(name): return normalize_property_name(name)

    m = re.search(r'([A-Z][A-Za-z0-9\s\-]{2,30}?)\s*(?:Residence|Residensi|Apartment|Condo|Resort|Tower|Villa|Court|Suites)', text, re.IGNORECASE)
    if m:
        name = m.group(0).strip()
        if len(name) >= 3 and is_valid_name(name) and not name.lower().startswith(('fully', 'partial', 'semi', 'un')):
            return normalize_property_name(name)

    for prop in KNOWN_PROPERTIES:
        if prop.lower() in text_lower: return normalize_property_name(prop)

    addr_patterns = [r'(?:Taman|Tmn\.?)\s+([A-Za-z\s]+)', r'Jalan\s+([A-Za-z\s]+\d*)']
    for pat in addr_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m: return normalize_property_name(m.group(0).strip())
    return ""

def extract_property_type(text):
    """Extract property type."""
    types = {
        "双层排屋": "双层排屋", "Double Storey": "双层排屋", "double storey": "双层排屋",
        "单层排屋": "单层排屋", "Single Storey": "单层排屋", "single storey": "单层排屋",
        "排屋": "排屋", "Terrace": "排屋", "Studio": "Studio", "studio": "Studio",
        "公寓": "公寓", "Apartment": "公寓", "apartment": "公寓", "Condo": "公寓", "condo": "公寓",
        "Condominium": "公寓", "Flat": "Flat", "flat": "Flat", "半独立": "半独立", "Semi-D": "半独立",
        "semi d": "半独立", "独立式": "独立式", "Bungalow": "独立式", "bungalow": "独立式",
        "Townhouse": "Townhouse", "中房": "中房", "Middle Room": "中房", "common room": "中房",
        "小房": "小房", "Small Room": "小房", "大房": "大房", "Master Room": "大房", "master room": "大房",
        "房间": "房间", "Room": "房间", "whole unit": "整间",
    }
    text_lower = text.lower()
    for key in sorted(types.keys(), key=len, reverse=True):
        if key.lower() in text_lower: return types[key]
    return ""

def extract_rooms(text):
    """Extract room count."""
    m = re.search(r'(?:^|\s)(\d+)\s*房\s*(\d+)\s*[厕浴]', text)
    if m: return f"{m.group(1)}房{m.group(2)}厕"
    m = re.search(r'(?:^|\s)(\d+)\s*bed(?:room)?s?\s*(\d+)\s*bath(?:room)?s?', text, re.IGNORECASE)
    if m: return f"{m.group(1)}房{m.group(2)}厕"
    m = re.search(r'\b(\d+)\s*房\b', text)
    if m: return f"{m.group(1)}房"
    m = re.search(r'\b(\d+)\s*bed(?:room)?\b', text, re.IGNORECASE)
    if m: return f"{m.group(1)}房"
    return ""

def extract_rent(text):
    """Extract rent amount in RM."""
    if not text: return ""
    def expand_k(m):
        num = m.group(1).replace(',', '')
        try: return f'RM {int(float(num) * 1000)}'
        except: return m.group(0)
    text_expanded = re.sub(r'(?:RM|rm|MYR|myr)\s*([\d.]+)\s*k\b', expand_k, text, flags=re.IGNORECASE)
    text_expanded = re.sub(r'\+?\d*\s*(?:MYR|myr)', ' RM', text_expanded)

    m = re.search(r'(?:RM|rm)\s*([\d,]{3,8})\b', text_expanded)
    if m:
        try:
            val = int(m.group(1).replace(',', ''))
            if val < 50000 or _has_rental_context(text, m.start()): return val
        except: pass
    m = re.search(r'(?:Rental|RENTAL|rental|租金|Rent\b)\s*:?\s*(?:RM|rm)?\s*([\d,]{3,6})\b', text, re.IGNORECASE)
    if m:
        try: return int(m.group(1).replace(',', ''))
        except: pass
    m = re.search(r'([\d,]{3,5})\s*(?:RM|rm)\b', text_expanded)
    if m:
        try:
            val = int(m.group(1).replace(',', ''))
            if val < 50000: return val
        except: pass
    m = re.search(r'(?:budget|租金|rent)\D*([\d,]{3,5})\b', text, re.IGNORECASE)
    if m:
        try: return int(m.group(1).replace(',', ''))
        except: pass
    m = re.search(r'\b([\d,]{3,4})\s*$', text.strip())
    if m:
        try:
            val = int(m.group(1).replace(',', ''))
            if 100 <= val < 50000: return val
        except: pass
    return ""

def _has_rental_context(text, pos):
    window = text[max(0, pos-60):pos+60]
    rental_kw = ['rent', 'rental', '出租', '租金', '月租', 'per month', '/month', '包水电']
    sale_kw = ['sale', '出售', 'selling', '售价', 'for sale']
    return any(kw in window.lower() for kw in rental_kw) and not any(kw in window.lower() for kw in sale_kw)

def extract_furnishing(text):
    text_lower = text.lower()
    if re.search(r'[全齐]家[私俱]|fully furnished|full[-\s]?furnish', text_lower): return '全家私'
    if re.search(r'半家[私俱]|partial[-\s]?furnish|semi[-\s]?furnish', text_lower): return '半家私'
    if re.search(r'\bunfurnished\b|无家[私俱]|没有家[私俱]|kosong', text_lower): return '无家私'
    return ''

def extract_remark(text, property_name="", property_type="", rooms=""):
    keywords = []
    checks = [
        (r'包水电', '包水电'), (r'包[热水冷气网]', '包设施'), (r'屋主[自租]', '屋主自租'),
        (r'我是屋主', '屋主直租'), (r'no agent', '无中介'), (r'不要中介', '无中介'),
        (r'新[装修翻]', '新装修'), (r'近\s*CIQ', '近CIQ'), (r'CIQ', '近CIQ'),
        (r'[走靠]?[路近].*[CIQ关]', '近CIQ'), (r'新马[通勤往来]', '新马通勤'),
        (r'停[车位]', '有停车位'), (r'parking', '有停车位'), (r'car.?park', '有停车位'),
        (r'冷气', '有冷气'), (r'air.?cond', '有冷气'), (r'双人床', '双人床'),
        (r'私人[厕浴]', '私人厕所'), (r'洗衣机', '有洗衣机'), (r'冰[箱厨]', '有冰箱'),
        (r'可[以能煮]', '可煮'), (r'[女男]孩[子生]', '限女生' if '女' in text else '限男生'),
        (r'female only', '限女生'), (r'male only', '限男生'),
    ]
    for pattern, label in checks:
        if re.search(pattern, text, re.IGNORECASE):
            if label not in keywords: keywords.append(label)
    return "; ".join(keywords) if keywords else ""

def format_scraped_at(iso_str):
    if not iso_str: return ""
    try:
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.astimezone(MY_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except: return iso_str[:19] if iso_str else ""
