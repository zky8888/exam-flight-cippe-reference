#!/usr/bin/env python3
"""Read-only QA for source preservation, audit completeness and answer hiding."""
import importlib.util
import json
import sqlite3
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('query_kb',Path(__file__).with_name('query_kb.py'))
query=importlib.util.module_from_spec(spec)
spec.loader.exec_module(query)

class AuditInventoryTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(f'file:{ROOT}/knowledge_base/cippe_kb.sqlite3?mode=ro',uri=True)
        self.c.row_factory=sqlite3.Row

    def tearDown(self):
        self.c.close()

    def test_database_integrity(self):
        self.assertEqual(self.c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.c.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_inventory(self):
        self.assertEqual(self.c.execute('SELECT count(*) FROM source_checks').fetchone()[0],307)
        self.assertEqual(self.c.execute('SELECT count(*) FROM bok_indicators').fetchone()[0],63)
        self.assertEqual(self.c.execute('SELECT count(*) FROM indicator_routes').fetchone()[0],63)
        self.assertEqual(self.c.execute('SELECT count(*) FROM section_inventory').fetchone()[0],504)
        for row in self.c.execute('SELECT * FROM source_checks'):
            self.assertEqual(set(json.loads(row['clean_options_json'])),set('ABCD'))
            self.assertIn(row['printed_answer'],'ABCD')
            self.assertTrue(json.loads(row['pdf_pages']))
        for row in self.c.execute('SELECT * FROM indicator_routes'):
            self.assertEqual(row['status'],'candidate_only')
            for s in json.loads(row['candidate_sections']):
                self.assertIsNotNone(self.c.execute('SELECT 1 FROM sections WHERE section_no=?',(s,)).fetchone())

    def test_raw_sources_unchanged_from_git(self):
        # Deserialize the committed DB in memory; no temporary binary file needed.
        blob=subprocess.check_output(['git','show','HEAD:knowledge_base/cippe_kb.sqlite3'],cwd=ROOT)
        # A committed WAL-mode header makes deserialize look for a sidecar.
        # Switch only the in-memory copy's read/write format to rollback mode.
        blob=bytearray(blob)
        self.assertEqual(blob[:16],b'SQLite format 3\x00')
        blob[18:20]=b'\x01\x01'
        old=sqlite3.connect(':memory:')
        try:
            old.deserialize(bytes(blob))
            for sql in [
              'SELECT q_no,pdf_page,stem,source_answer,source_explanation,source_reference FROM questions ORDER BY q_no',
              'SELECT * FROM question_options ORDER BY q_no,option_key',
              'SELECT * FROM sections ORDER BY section_no']:
                self.assertEqual(old.execute(sql).fetchall(),[tuple(r) for r in self.c.execute(sql)])
        finally:
            old.close()

    def test_audit_and_display(self):
        for row in self.c.execute('SELECT q_no,audit_json FROM question_audits'):
            q=row['q_no']; a=json.loads(row['audit_json'])
            self.assertEqual(set(a['options']),set('ABCD'))
            self.assertTrue(all(a['options'].values()))
            self.assertEqual(set(a['display']['options']),set('ABCD'))
            self.assertTrue(a['source'])
            self.assertTrue(a['pages'])
            self.assertTrue(a['fact'])
            hidden=query.question_payload(self.c,q,True)
            for secret in ['audit','source_answer','verified_answer','verified_analysis','topics','source_explanation','source_reference']:
                self.assertNotIn(secret,hidden)
            shown=query.question_payload(self.c,q,False)
            self.assertIn('audit',shown)
            self.assertIsNotNone(self.c.execute("SELECT 1 FROM question_indicator_links WHERE q_no=? AND role='main'",(q,)).fetchone())

    def test_quarantine_and_corrected_key(self):
        for q in (8,11,205,273):
            row=self.c.execute('SELECT verification_status,verified_answer FROM questions WHERE q_no=?',(q,)).fetchone()
            self.assertEqual(tuple(row),('needs_review',None))
        row=self.c.execute('SELECT source_answer,verified_answer FROM questions WHERE q_no=12').fetchone()
        self.assertEqual(tuple(row),('B','A'))
        self.assertEqual(self.c.execute('SELECT count(*) FROM question_review_history WHERE q_no BETWEEN 1 AND 12').fetchone()[0],12)

    def test_variants_still_hide_answers(self):
        for row in self.c.execute('SELECT * FROM variant_questions'):
            hidden=query.variant_payload(row,False)
            self.assertEqual(set(hidden['options']),set('ABCD'))
            for secret in ['correct_answer','analysis','source_basis','misconception','card_id']:
                self.assertNotIn(secret,hidden)

if __name__=='__main__':
    unittest.main(verbosity=2)
