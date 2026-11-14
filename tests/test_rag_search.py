"""Bot tomonidagi RAG qidiruv: chegaralash va kontekst formati."""
import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKENTESTTOKENTESTTOKENTESTTOKEN")

try:
    from services import rag_search
    from services.ai_service import AIService
except ImportError:  # aiogram / firebase-admin oʻrnatilmagan
    rag_search = None


@unittest.skipIf(rag_search is None, "bot bogʻliqliklari oʻrnatilmagan")
class RagSearchTest(unittest.TestCase):
    def test_filter_drops_far_hits(self):
        hits = [{'distance': 0.12}, {'distance': 0.39}, {'distance': 0.55}]
        self.assertEqual(rag_search.filter_hits(hits, 0.40), hits[:2])

    def test_format_context_labels_source_and_trims(self):
        text = rag_search.format_context([
            {'section': 'E-IMZO › Kesh', 'text': 'x' * 5000},
            {'doc_title': 'FAQ', 'text': 'javob'},
            {'section': 'Bo\'sh', 'text': ''},
        ], max_chars=100)
        parts = text.split('\n\n---\n\n')
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].startswith('[Manba: E-IMZO › Kesh]\n'))
        self.assertEqual(len(parts[0].split('\n', 1)[1]), 100)
        self.assertEqual(parts[1], '[Manba: FAQ]\njavob')

    def test_relevant_context_empty_on_error_without_dumping_manuals(self):
        async def boom(*_a, **_k):
            raise RuntimeError('tarmoq yoʻq')

        with mock.patch.object(rag_search, 'search', boom), \
             mock.patch.object(AIService, 'get_system_manuals') as manuals:
            result = asyncio.run(AIService.get_relevant_context('savol'))
        self.assertEqual(result, '')
        manuals.assert_not_called()

    def test_search_uses_query_task_type_and_v2_collection(self):
        seen = {}

        async def embed_content(model, contents, config):
            seen['task_type'] = config.task_type
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1] * 768)])

        class Query:
            def get(self):
                hit = SimpleNamespace(to_dict=lambda: {'text': 't', 'distance': 0.1, 'embedding': [1]})
                far = SimpleNamespace(to_dict=lambda: {'text': 'f', 'distance': 0.9})
                return [hit, far]

        class Col:
            def find_nearest(self, **kwargs):
                seen['distance_field'] = kwargs['distance_result_field']
                return Query()

        db = SimpleNamespace(collection=lambda name: seen.setdefault('collection', name) and Col())
        client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed_content)))
        with mock.patch.object(rag_search, 'get_db', return_value=db), \
             mock.patch.object(rag_search, 'init_gemini', return_value=client):
            hits = asyncio.run(rag_search.search('E-IMZO'))
        self.assertEqual(seen['collection'], 'rag_chunks_v2')
        self.assertEqual(seen['task_type'], 'RETRIEVAL_QUERY')
        self.assertEqual(hits, [{'text': 't', 'distance': 0.1}])


if __name__ == '__main__':
    unittest.main()
