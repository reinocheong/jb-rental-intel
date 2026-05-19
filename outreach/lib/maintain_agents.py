#!/usr/bin/env python3
import sys, os
sys.path.insert(0, "/home/user/jb-rental-intel")

from outreach.lib.sheet_reader import get_agents_from_sheet
from outreach.lib.dedup_utils import dedup_agents
from outreach.lib.sheet_reader import get_sheets_service

INTERNAL_SHEET_ID = "1gCynpcBHYgoGiRkfVOJOCOjtiOIl0NuGgpyEexAF3W4"

def main():
    print("[outreach/lib/maintain_agents.py] 开始维护 Agent List")
    raw_agents = get_agents_from_sheet()
    unique_agents = dedup_agents(raw_agents)
    
    # Update Agent List tab
    svc = get_sheets_service()
    rows = [["Phone", "Agent", "Status"]] + [[a['phone'], a['agent'], 'active'] for a in unique_agents]
    svc.spreadsheets().values().update(spreadsheetId=INTERNAL_SHEET_ID, range="Agent List!A:C", valueInputOption="RAW", body={"values": rows}).execute()
    print(f"✅ 维护完成: {len(unique_agents)} 个唯一 Agent")

if __name__ == "__main__": main()
