"""Yagona RAG yig'uvchi: bo'laklash, id barqarorligi, takrorlar va sinxronlash rejasi."""
import tempfile
import unittest
from pathlib import Path

from rag import sources as src
from rag.chunker import MAX_CHARS, chunk_markdown, split_long
from rag.sources import Chunk, doc_slug
from rag.sync import content_hash, dedupe, plan_sync

MODEL, DIM = 'gemini-embedding-2', 768


def chunk(id_, text, source='dars'):
    return Chunk(id=id_, source=source, doc_id='d', doc_title='T', section='S', text=text)


class ChunkerTest(unittest.TestCase):
    def test_sections_keep_heading_path(self):
        md = ('# Modul\n\nKirish matni ' + 'a' * 60 +
              '\n\n## Word\n\n### Ctrl+H\n\nAlmashtirish ' + 'b' * 60 +
              '\n\n## Excel\n\nAvtosumma ' + 'c' * 60)
        pieces = chunk_markdown(md, root_title='1-modul')
        self.assertEqual([p.section for p in pieces], [
            '1-modul › Modul',
            '1-modul › Modul › Word › Ctrl+H',
            '1-modul › Modul › Excel',  # ### Ctrl+H Excel bilan almashtiriladi
        ])

    def test_headers_inside_code_block_are_ignored(self):
        md = '# A\n\n```\n# bu izoh\n```\n' + 'x ' * 40
        pieces = chunk_markdown(md)
        self.assertEqual(len(pieces), 1)
        self.assertIn('# bu izoh', pieces[0].text)

    def test_long_section_split_within_limit_with_overlap(self):
        paras = [f'Paragraf {i} ' + 'soz ' * 60 for i in range(12)]
        parts = split_long('\n\n'.join(paras))
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= MAX_CHARS for p in parts))
        # qoplama: keyingi bo'lak oldingisining oxiridan bir qism bilan boshlanadi
        self.assertTrue(parts[0].endswith(parts[1].split('\n\n')[0]))

    def test_single_huge_paragraph_is_cut(self):
        parts = split_long('soz ' * 1000)
        self.assertTrue(all(len(p) <= MAX_CHARS for p in parts))
        self.assertGreater(len(parts), 2)

    def test_tiny_sections_dropped(self):
        self.assertEqual(chunk_markdown('# A\n\nqisqa'), [])


class SourcesTest(unittest.TestCase):
    def test_slug_is_stable_and_firestore_safe(self):
        self.assertEqual(doc_slug('ИЖРО ВАРАҚАЛАРИ'), doc_slug('ИЖРО ВАРАҚАЛАРИ'))
        self.assertNotIn('/', doc_slug('a/b c'))
        self.assertRegex(doc_slug('ИЖРО'), r'^[0-9a-f]{8}$')

    def test_qollanma_split_per_book_and_strips_meta(self):
        body = 'Matn ' * 30
        md = (f'# 📚 BAZA\n\n---\n## 📖 BIRINCHI QOLLANMA PDF\n*(Manba: a.pdf)*\n\n{body}\n'
              f'---\n## 📖 IKKINCHI\n*(Manba: b.pdf)*\n\n{body}\n')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'knowledge.md'
            path.write_text(md, encoding='utf-8')
            chunks = src.load_qollanma(path)
        self.assertEqual([c.doc_title for c in chunks], ['BIRINCHI QOLLANMA', 'IKKINCHI'])
        self.assertTrue(all('Manba:' not in c.text for c in chunks))
        self.assertTrue(chunks[0].id.startswith('qollanma:birinchi-qollanma-'))

    def test_dars_skips_archive_and_maps_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '2. ERI va brauzer').mkdir()
            (root / '99. Xizmat fayllari va arxiv').mkdir()
            text = '# ERI\n\n' + 'kalit ' * 30
            (root / '2. ERI va brauzer' / 'dars.md').write_text(text, encoding='utf-8')
            (root / '99. Xizmat fayllari va arxiv' / 'eski.md').write_text(text, encoding='utf-8')
            chunks = src.load_dars(root)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].category, '2-modul: ERI va Brauzer')
        self.assertTrue(chunks[0].section.startswith('2-modul: ERI va Brauzer › ERI'))


class SyncTest(unittest.TestCase):
    def test_dedupe_keeps_first_ignoring_whitespace_and_case(self):
        kept, dropped = dedupe([chunk('a', 'Bir  Xil matn'), chunk('b', 'bir xil MATN', 'qollanma'),
                                chunk('c', 'boshqa')])
        self.assertEqual([c.id for c in kept], ['a', 'c'])
        self.assertEqual([c.id for c in dropped], ['b'])

    def test_hash_depends_on_model_and_text(self):
        c = chunk('a', 'matn')
        self.assertNotEqual(content_hash(c, MODEL, DIM), content_hash(c, 'boshqa-model', DIM))
        self.assertNotEqual(content_hash(c, MODEL, DIM), content_hash(chunk('a', 'matn2'), MODEL, DIM))

    def test_plan_only_reembeds_changed_and_deletes_orphans_of_built_sources(self):
        same, changed, new = chunk('same', 'eski matn'), chunk('chg', 'yangi matn'), chunk('new', 'qo\'shildi')
        existing = {
            'same': {'hash': content_hash(same, MODEL, DIM), 'source': 'dars'},
            'chg': {'hash': 'eski-hash', 'source': 'dars'},
            'gone': {'hash': 'x', 'source': 'dars'},
            'faq:1:0': {'hash': 'x', 'source': 'faq'},  # bu safar faq yig'ilmadi — tegilmaydi
        }
        plan = plan_sync([same, changed, new], existing, {'dars'}, MODEL, DIM)
        self.assertEqual([c.id for c in plan.upsert], ['chg', 'new'])
        self.assertEqual([c.id for c in plan.unchanged], ['same'])
        self.assertEqual(plan.delete, ['gone'])

    def test_model_change_reembeds_everything(self):
        c = chunk('a', 'matn')
        existing = {'a': {'hash': content_hash(c, 'eski-model', DIM), 'source': 'dars'}}
        self.assertEqual(len(plan_sync([c], existing, {'dars'}, MODEL, DIM).upsert), 1)


if __name__ == '__main__':
    unittest.main()
