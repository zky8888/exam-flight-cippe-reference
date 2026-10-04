#!/usr/bin/env python3
"""Validate the existing coverage document and persist its candidate routes.

Candidate routes are not semantic/full-content review or evidence of mastery.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def main():
    text = (ROOT/'07-IAPP-BOK覆盖矩阵.md').read_text()
    table = text.split('<!-- BOK-ROUTES-START -->')[1].split('<!-- BOK-ROUTES-END -->')[0]
    rows=[]
    for line in table.splitlines():
        if not line.startswith('| ') or line.startswith('| 项目'):
            continue
        ident,page,branches,sections,schedule=[x.strip() for x in line.strip('|').split('|')]
        rows.append((ident,int(page),branches,sections.split(','),schedule))
    c=sqlite3.connect(ROOT/'knowledge_base/cippe_kb.sqlite3')
    c.execute('PRAGMA foreign_keys=ON')
    expected=dict(c.execute('SELECT indicator_id,pdf_page FROM bok_indicators'))
    assert len(rows)==63 and {r[0] for r in rows}==set(expected)
    c.executescript('''CREATE TABLE IF NOT EXISTS indicator_routes (
      indicator_id TEXT PRIMARY KEY REFERENCES bok_indicators(indicator_id),
      branches_zh TEXT NOT NULL, candidate_sections TEXT NOT NULL,
      planned_session TEXT NOT NULL, status TEXT NOT NULL, updated_on TEXT NOT NULL);
    ''')
    with c:
        for ident,page,branches,sections,schedule in rows:
            assert page==expected[ident]
            for s in sections:
                assert c.execute('SELECT 1 FROM sections WHERE section_no=?',(s,)).fetchone(),s
            c.execute('INSERT OR REPLACE INTO indicator_routes VALUES(?,?,?,?,?,?)',
                      (ident,branches,json.dumps(sections),schedule,'candidate_only','2026-09-05'))
    print('63 official rows matched; 63 candidate routes saved; no teaching/mastery changes.')
    c.close()

if __name__=='__main__':
    main()
