"""Phone normalization utilities."""
import re

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
