import re

def normalize_agent_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('01'): return '60' + digits[1:]
    return digits

def dedup_agents(agent_list):
    seen = {}
    for a in agent_list:
        p = normalize_agent_phone(a.get('phone', ''))
        if p and p not in seen: seen[p] = a
    return list(seen.values())
