def calculate_dynamic_quota(agents_total: int, already_contacted: int) -> int:
    remaining = agents_total - already_contacted
    if remaining <= 0: return 0
    return max(2, min(10, remaining // 30 + 1))

def pick_slot_candidates(candidates, slot: int, total_slots: int):
    if total_slots <= 0: return []
    per_slot = len(candidates) // total_slots
    remainder = len(candidates) % total_slots
    start = slot * per_slot + min(slot, remainder)
    end = start + per_slot + (1 if slot < remainder else 0)
    return candidates[start:end]
