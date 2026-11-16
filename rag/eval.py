"""RAG sifat o'lchovi (eval CLI): 30 ta haqiqiy savolda hit@1, hit@3 (chegara bilan) va hit@5.

Ishga tushirish:
  python -m rag.eval
  python -m rag.eval --max-distance 0.33 --min-hit5 0.80
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from rag.build import DEFAULT_COLLECTION, _model, connect_firestore, gemini_client


@dataclass(frozen=True)
class EvalCase:
    query: str
    expected_doc_ids: tuple[str, ...]
    label: str = ''


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        query="Nima uchun sud hujjatlarini Ish stolida (Desktop) saqlash xavfli?",
        expected_doc_ids=('1-windows-office-va-ofis-texnikasi-1-mod-25015941',),
        label='dars:m1_desktop',
    ),
    EvalCase(
        query="Sud hujjatlarini to'g'ri nomlash standarti qanday?",
        expected_doc_ids=('1-windows-office-va-ofis-texnikasi-1-mod-25015941',),
        label='dars:m1_naming',
    ),
    EvalCase(
        query="Word dasturida qidirish va almashtirish uchun qaysi tugmalar bosiladi (Ctrl+H)?",
        expected_doc_ids=('1-windows-office-va-ofis-texnikasi-1-mod-25015941', 'art_it_4'),
        label='dars:m1_word_ctrl_h',
    ),
    EvalCase(
        query="Adobe Acrobat orqali skanerlashda necha DPI standarti tavsiya etiladi?",
        expected_doc_ids=(
            '1-windows-office-va-ofis-texnikasi-1-mod-25015941',
            'esud_e-sud_da_hujjat_skanerlash_va_yuklash_qoidalari_qanday',
        ),
        label='dars:m1_scan_dpi',
    ),
    EvalCase(
        query="ERI kalitlari kompyuterning qaysi papkasida saqlanishi shart (DSKEYS)?",
        expected_doc_ids=('2-eri-va-brauzer-sozlamalari-2-modul-bo-8d537155', 'art_security_3'),
        label='dars:m2_dskeys',
    ),
    EvalCase(
        query="E-IMZO bilan aloqa yo'q yoki WebSocket error chiqsa nima qilish kerak?",
        expected_doc_ids=(
            '2-eri-va-brauzer-sozlamalari-2-modul-bo-8d537155',
            'e-imzo-modulidan-foydalanish-bo-yicha-qo-4f48741b',
        ),
        label='dars:m2_eimzo_error',
    ),
    EvalCase(
        query="Ish joyidan turib ketayotganda ekranni qulflash uchun qaysi tugmalar bosiladi (Win+L)?",
        expected_doc_ids=('3-axborot-xavfsizligi-va-maxfiylik-3-mod-27b6e778',),
        label='dars:m3_win_l',
    ),
    EvalCase(
        query="Begona USB-fleshkalarni ishchi kompyuterga ulash nega xavfli?",
        expected_doc_ids=('3-axborot-xavfsizligi-va-maxfiylik-3-mod-27b6e778',),
        label='dars:m3_usb',
    ),
    EvalCase(
        query="Sud qarorlarini public.sud.uz tarmog'ida e'lon qilish (Publikatsiya) tartibi qanday?",
        expected_doc_ids=(
            '3-axborot-xavfsizligi-va-maxfiylik-3-mod-27b6e778',
            '5-85e2d720',
            'sud-hujjatlarini-internet-tarmog-ida-e-l-ac8e9104',
        ),
        label='dars:m3_public_sud',
    ),
    EvalCase(
        query="EDO.SUD.UZ tizimida sud raisi rezolyutsiya (ustxat) va fishkani qanday qo'yadi?",
        expected_doc_ids=(
            '4-oliy-sud-axborot-tizimlari-va-edo-4-mo-2de6a8ad',
            '5-ustxat-bilan-kelib-tushgan-hujjatlarni-a9015508',
        ),
        label='dars:m4_edo_fishka',
    ),
    EvalCase(
        query="billing.sud.uz tizimida 12 xonali kvitansiya haqiqiyligini qanday tekshiriladi?",
        expected_doc_ids=(
            '4-oliy-sud-axborot-tizimlari-va-edo-4-mo-2de6a8ad',
            '4-oliy-sud-axborot-tizimlari-va-edo-4-mo-4f924b6e',
        ),
        label='dars:m4_billing',
    ),
    EvalCase(
        query="my.sud.uz portalida davlat boji kalkulyatoridan qanday foydalaniladi?",
        expected_doc_ids=(
            '4-oliy-sud-axborot-tizimlari-va-edo-my-s-2973f91c',
            '4-oliy-sud-axborot-tizimlari-va-edo-4-mo-4f924b6e',
            '4-oliy-sud-axborot-tizimlari-va-edo-tadq-d965a99d',
        ),
        label='dars:m4_mysud_calc',
    ),
    EvalCase(
        query="Sud majlislarini audio va video qayd etish (AVF) tizimida kotibning vazifalari nima?",
        expected_doc_ids=('5-modul-bo-yicha-to-liq-amaliy-qo-llanma-0293d7b4', '64fa3721'),
        label='dars:m5_avf',
    ),
    EvalCase(
        query="Mobil VKA tizimi orqali masofaviy sud majlisini o'tkazish tartibi qanday?",
        expected_doc_ids=('5-modul-bo-yicha-to-liq-amaliy-qo-llanma-0293d7b4', 'b5112f4a'),
        label='dars:m5_mobil_vka',
    ),
    EvalCase(
        query="Lex.uz bazasida qonunning eski tahririni qanday topish mumkin?",
        expected_doc_ids=('5-modul-bo-yicha-to-liq-amaliy-qo-llanma-0293d7b4',),
        label='dars:m5_lexuz',
    ),
    EvalCase(
        query="EDO da hujjatga viza (kelishuv) qanday qo'yiladi?",
        expected_doc_ids=(
            'edo_edo_da_hujjatga_viza_kelishuv_qanday_qoyiladi',
            '8-kelishish-va-imzolashga-yuborish-yo-ri-0e066c56',
            'art_edo_2',
        ),
        label='faq:edo_viza',
    ),
    EvalCase(
        query="EDO da arxivlangan hujjatlarni qanday ko'raman?",
        expected_doc_ids=('edo_edo_da_arxivlangan_hujjatlarni_qanday_koraman',),
        label='faq:edo_arxiv',
    ),
    EvalCase(
        query="EDO va E-SUD o'rtasidagi farq nima?",
        expected_doc_ids=('edo_edo_va_e-sud_ortasidagi_farq_nima',),
        label='faq:edo_vs_esud',
    ),
    EvalCase(
        query="E-SUD da 'Sessiya muddati tugadi' xatoligi chiqsa nima qilaman?",
        expected_doc_ids=('esud_e-sud_da_xatolik_sessiya_muddati_tugadi_xabari_chiqmoqda_nima_qilaman',),
        label='faq:esud_session',
    ),
    EvalCase(
        query="E-SUD da parolimni unutdim, qanday tiklayman?",
        expected_doc_ids=('esud_e-sud_da_parolimni_unutdim_qanday_tiklayman',),
        label='faq:esud_password',
    ),
    EvalCase(
        query="E-XAT da attestatsiya sertifikati qanday chiqariladi?",
        expected_doc_ids=('exat_e-xat_da_attestatsiya_sertifikati_qanday_chiqariladi', 'art_exat_1'),
        label='faq:exat_cert',
    ),
    EvalCase(
        query="E-XAT da DTS (Davlat Tili Sertifikati) natijalarini qanday ko'raman?",
        expected_doc_ids=('exat_e-xat_da_dts_davlat_tili_sertifikati_natijalarini_qanday_koraman',),
        label='faq:exat_dts',
    ),
    EvalCase(
        query="Majburiy ijro byurosi (MIB) tomonidan qaytarilgan ijro hujjatlarini qayta yuborish tartibi",
        expected_doc_ids=(
            '22-6ef85a9e',
            '102a2d6b',
            '4-oliy-sud-axborot-tizimlari-va-edo-4-mo-2de6a8ad',
        ),
        label='qollanma:mib',
    ),
    EvalCase(
        query="E-XSUD axborot tizimi orqali apellyatsiya va kassatsiya shikoyatlarini ro'yxatga olish",
        expected_doc_ids=('13-e-xsud-a3663bfc', '12-e-xsud-2a871d91'),
        label='qollanma:exsud_shikoyat',
    ),
    EvalCase(
        query="Devonxona tomonidan kiruvchi hujjatlarni ro'yxatga olish va taqsimlash tartibi",
        expected_doc_ids=(
            '3-devonxona-tomonidan-kiruvchi-hujjatlar-61161c4a',
            '4-devonxona-tomonidan-kirim-qilingan-huj-2d94b35e',
            '4-oliy-sud-axborot-tizimlari-va-edo-4-mo-2de6a8ad',
        ),
        label='qollanma:devonxona',
    ),
    EvalCase(
        query="Topshiriq muddatini uzaytirish so'rovini tasdiqlash yo'riqnomasi",
        expected_doc_ids=(
            '13-topshiriq-muddatini-uzaytirish-so-rov-c1a2498a',
            '4-oliy-sud-axborot-tizimlari-va-edo-4-mo-2de6a8ad',
        ),
        label='qollanma:muddat',
    ),
    EvalCase(
        query="Sud hujjatlaridan nusxa berganlik uchun davlat bojini undirish tartibi",
        expected_doc_ids=('b88ef159',),
        label='qollanma:nusxa_boj',
    ),
    EvalCase(
        query="Ishlarni sudyalar o'rtasida avtomatik tarzda taqsimlash va qayta taqsimlash",
        expected_doc_ids=('e241a408',),
        label='qollanma:taqsimlash',
    ),
    EvalCase(
        query="HP va Canon printerlarini kompyuterga o'rnatish va bosib chiqarmasa muammolar yechimi",
        expected_doc_ids=(
            'art_it_printer_8',
            'general_printer_bilan_muammo_bolsa_bosib_chiqarmasa_nima_qilaman',
            'canon-install-guide-printer-c4595967',
            'hp-install-guide-printer-ae48c2cc',
        ),
        label='kb:printer',
    ),
    EvalCase(
        query="Mol-mulkka taqiq solish va ekspertiza tayinlash bo'yicha yo'riqnoma",
        expected_doc_ids=('e5a8e44e', 'f0095277'),
        label='qollanma:taqiq_ekspertiza',
    ),
)


def evaluate_case(case: EvalCase, hits: list[dict], max_distance: float = 0.33) -> dict:
    """Bitta savol bo'yicha hit@1, hit@3 (masofa chegarasi bilan) va hit@5 ni hisoblaydi."""
    expected = set(case.expected_doc_ids)
    top5 = hits[:5]
    top_doc_ids = [str(h.get('doc_id') or '') for h in top5]

    matched_rank = next((idx + 1 for idx, doc_id in enumerate(top_doc_ids) if doc_id in expected), None)
    hit_at_1 = bool(top_doc_ids and top_doc_ids[0] in expected)
    hit_at_5 = matched_rank is not None
    filtered_top3 = [h for h in hits[:3] if h.get('distance', 0.0) <= max_distance]
    hit_at_3_threshold = any(str(h.get('doc_id') or '') in expected for h in filtered_top3)

    return {
        'label': case.label,
        'query': case.query,
        'expected_doc_ids': case.expected_doc_ids,
        'hit_at_1': hit_at_1,
        'hit_at_3_threshold': hit_at_3_threshold,
        'hit_at_5': hit_at_5,
        'matched_rank': matched_rank,
        'top_doc_ids': top_doc_ids,
        'top_distance': hits[0].get('distance') if hits else None,
        'distances': [h.get('distance') for h in top5],
    }


def summarize_eval(results: list[dict], min_hit5: float = 0.80) -> dict:
    """Barcha eval natijalaridan umumiy ko'rsatkichlarni jamlaydi."""
    total = len(results)
    if total == 0:
        return {
            'total': 0,
            'hit_1': 0,
            'hit_3_threshold': 0,
            'hit_5': 0,
            'hit_1_rate': 0.0,
            'hit_3_threshold_rate': 0.0,
            'hit_5_rate': 0.0,
            'passed': False,
        }

    hit_1 = sum(1 for r in results if r['hit_at_1'])
    hit_3_threshold = sum(1 for r in results if r['hit_at_3_threshold'])
    hit_5 = sum(1 for r in results if r['hit_at_5'])
    hit_5_rate = hit_5 / total

    return {
        'total': total,
        'hit_1': hit_1,
        'hit_3_threshold': hit_3_threshold,
        'hit_5': hit_5,
        'hit_1_rate': hit_1 / total,
        'hit_3_threshold_rate': hit_3_threshold / total,
        'hit_5_rate': hit_5_rate,
        'passed': hit_5_rate >= min_hit5,
    }


def query_rag(db, client, query: str, collection: str, model: str, dim: int, limit: int = 5) -> list[dict]:
    """Jonli Firestore kolleksiyasidan bitta savol uchun top-k hujjatlarni qaytaradi."""
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
    from google.cloud.firestore_v1.vector import Vector
    from google.genai import types

    result = client.models.embed_content(
        model=model,
        contents=query,
        config=types.EmbedContentConfig(
            task_type='RETRIEVAL_QUERY',
            output_dimensionality=dim,
        ),
    )
    vector = result.embeddings[0].values
    docs = (
        db.collection(collection)
        .find_nearest(
            vector_field='embedding',
            query_vector=Vector(vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit,
            distance_result_field='distance',
        )
        .get()
    )
    hits: list[dict] = []
    for doc in docs:
        data = doc.to_dict() or {}
        data.pop('embedding', None)
        hits.append(data)
    return hits


def run(collection: str, limit: int, max_distance: float, min_hit5: float) -> int:
    model, dim = _model()
    db = connect_firestore()
    client = gemini_client()

    results: list[dict] = []
    print(f'RAG Eval — kolleksiya: {collection}, model: {model} ({dim}), chegara: <= {max_distance}')
    print('-' * 88)
    for idx, case in enumerate(EVAL_CASES, start=1):
        hits = query_rag(db, client, case.query, collection, model, dim, limit=limit)
        res = evaluate_case(case, hits, max_distance=max_distance)
        results.append(res)
        mark = 'PASS' if res['hit_at_5'] else 'MISS'
        t_mark = 'OK' if res['hit_at_3_threshold'] else 'NO'
        dist_str = f"{res['top_distance']:.4f}" if res['top_distance'] is not None else 'n/a'
        top_id = res['top_doc_ids'][0] if res['top_doc_ids'] else 'none'
        print(
            f"{idx:>2}. [{mark} | h3<={max_distance}:{t_mark} | rank={res['matched_rank'] or '-'}] "
            f"d={dist_str} | {case.label:<24} -> {top_id}"
        )

    summary = summarize_eval(results, min_hit5=min_hit5)
    print('-' * 88)
    print(
        f"Jami: {summary['total']} | "
        f"hit@1: {summary['hit_1']}/{summary['total']} ({summary['hit_1_rate']:.1%}) | "
        f"hit@3 (<={max_distance}): {summary['hit_3_threshold']}/{summary['total']} ({summary['hit_3_threshold_rate']:.1%}) | "
        f"hit@5: {summary['hit_5']}/{summary['total']} ({summary['hit_5_rate']:.1%})"
    )
    if not summary['passed']:
        print(f"MEZON BAJARILMADI: hit@5 {summary['hit_5_rate']:.1%} < {min_hit5:.0%}")
        return 1
    print(f"MEZON BAJARILDI: hit@5 {summary['hit_5_rate']:.1%} >= {min_hit5:.0%}")
    return 0


def main(argv: list[str] | None = None) -> int:
    default_max_dist = float(os.getenv('RAG_MAX_DISTANCE', '0.33'))
    parser = argparse.ArgumentParser(description='RAG qidiruv sifatini baholash (eval)')
    parser.add_argument('--collection', default=DEFAULT_COLLECTION)
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--max-distance', type=float, default=default_max_dist)
    parser.add_argument('--min-hit5', type=float, default=0.80)
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    return run(args.collection, args.limit, args.max_distance, args.min_hit5)


if __name__ == '__main__':
    sys.exit(main())
