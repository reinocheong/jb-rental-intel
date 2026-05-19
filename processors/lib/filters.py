"""Post filtering utilities."""
import re

def is_comment_thread(text):
    """Detect '评论区缝合怪' — posts that are comment threads, not original listings."""
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
    """Detect 求租 (looking for rental) posts — NOT what we want."""
    if not text:
        return False
    
    looking_patterns = [
        r'(?:我|我们|本人)?(?:想|要|正在|在)(?:找|寻找|找着)(?:房|屋|房间|屋子|整间)',
        r'(?:找|寻找)(?:靠近|近|附近)',
        r'^.{0,20}找.{0,10}(?:房|屋|studio|room|condo|apartment)',
        r'budget\s*(?:RM|rm)?\s*\d+',
        r'(?:什么|谁有|有没有).{0,10}(?:介绍|出租|房子)',
        r'谢绝agent',
        r'不要中介', 
        r'直接对屋主',
    ]
    
    for pat in looking_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    
    return False
