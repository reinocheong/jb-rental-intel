"""Known property names and normalization data."""
import re

# ----- Property names (common JB developments) -----
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

PROPERTY_NORMALIZE = {
    "r&f": "R&F Princess Cove", "rnf": "R&F Princess Cove",
    "r and f": "R&F Princess Cove", "princess cove": "R&F Princess Cove",
    "tritower": "Tri Tower", "tri tower": "Tri Tower",
    "trellis residence": "Trellis Residence", "trellis": "Trellis Residence",
    "trellis residensi": "Trellis Residence",
    "paragon suites": "Paragon Residences", "paragon residence": "Paragon Residences",
    "paragon": "Paragon Residences",
    "sks pavillion": "SKS Pavilion", "sks pavillion residence": "SKS Pavilion",
    "sks pavilion": "SKS Pavilion",
    "ksl residence": "KSL Residence", "ksl resident": "KSL Residence",
    "ksl d'inspire": "KSL D'Inspire", "d'inspire": "KSL D'Inspire",
    "country garden": "Country Garden", "碧桂园": "Country Garden",
    "twin tower": "Twin Tower", "twin galaxy": "Twin Galaxy",
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

PROPERTY_NAME_BLACKLIST = {
    'chong', 'lee', 'goh', 'loh', 'tan', 'wong', 'lim', 'chen', 'pong',
    'koh', 'lye', 'loo', 'liew', 'teo', 'ng', 'foo', 'chan', 'yap',
    'chin', 'sia', 'tee', 'ooi', 'seng',
    'for rent', 'for sale', '出租', '出售', '房间出租',
    'fully furnished', 'partial furnished', 'unfurnished', 'full furnish',
    'master room', 'master bedroom', 'common room', 'middle room',
    'small room', 'balcony room', 'single storey', 'double storey',
    'wifi', 'unifi', 'deposit', 'freehold', 'leasehold', 'bumi lot',
    'guarded', 'gated', 'food court', 'living hall', 'toilet',
    'bathroom', 'bedroom', 'high floor', 'nice view', 'smart lock',
    'internet included', 'utilities included', 'ce floor',
    'real estate', 'whatsapp', 'please contact', 'call or',
    'no agent', '不要中介', 'teamgather', 'roof realty',
    'properties sdn bhd', 'stabilisation', 'submaster',
    'untuk dijual', 'brand new', 'new launch', 'new unit',
    'end lot', 'intermediate lot', 'land size',
    'xiao hong shu', 'xiaohongshu',
    'residences', 'service apartment', 'jbcondo', 'ciq room for rent',
    'need room', 'looking for', 'walk to ksl', 'rts',
}

def normalize_property_name(raw_name):
    """Normalize property name. Returns canonical name or original."""
    if not raw_name or not raw_name.strip():
        return ""
    name = raw_name.strip()
    key = name.lower().strip().rstrip('.').replace('  ', ' ')
    if key in PROPERTY_NORMALIZE:
        return PROPERTY_NORMALIZE[key]
    clean = re.sub(r'\s*(?:RM|rm)\s*\d[\d,.]*', '', key).strip()
    if clean and clean != key and clean in PROPERTY_NORMALIZE:
        return PROPERTY_NORMALIZE[clean]
    if re.search(r'[\u4e00-\u9fff]', name):
        return name
    fixed = name.title()
    for abbr in ['JB', 'CIQ', 'KSL', 'SKS', 'R&F', 'RNF', 'MYR', 'Wi-Fi', "D'Inspire"]:
        fixed = re.sub(r'\b' + re.escape(abbr.lower()) + r'\b', abbr, fixed, flags=re.IGNORECASE)
    return fixed

def is_valid_property_name(name):
    """Reject garbage: names, prices, property descriptions."""
    if not name or len(name) < 2:
        return False
    key = name.lower().strip()
    if key in PROPERTY_NAME_BLACKLIST:
        return False
    for bw in PROPERTY_NAME_BLACKLIST:
        if len(bw) >= 4 and bw in key:
            return False
    if re.match(r'^(?:RM|rm)\s*\d[\d,.]*$', name):
        return False
    if re.match(r'^\d+$', name):
        return False
    if re.match(r'^[A-Z][a-z]+\s+(?:Chong|Lee|Goh|Loh|Tan|Wong|Lim|Chen)$', name):
        return False
    if re.match(r'^[A-Z0-9]{3,}$', name):
        return False
    if re.match(r'^[A-Z]{2,4}\s+[A-Z]{3,}$', name):
        return False
    if re.match(r'^[A-Z]{2,4}\d{3,}', name):
        return False
    if re.match(r'^(?:FOR|For)\s+(?:RENT|SALE)', name):
        return False
    return True
