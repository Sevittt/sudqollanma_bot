"""
Yagona profil migratsiyasi (bir martalik).

1. Eski bot profillari (avto-ID, telegram_id maydoni) → users/tg_<telegram_id>
   va telegram_links/{telegram_id}. Eski hujjat oʻchirilmaydi, `mergedInto` bilan belgilanadi.
2. quiz_attempts.userId Telegram ID boʻlib qolgan yozuvlar → profil kaliti.
3. `level` ilova formatiga (levelBeginner…levelMaster) keltiriladi: eski raqam/matn
   qiymatlar XP va hisoblagichlardan qayta hisoblanadi.

Ilova hisobiga birlashtirish bu yerda qilinmaydi: kim kim ekanini faqat
foydalanuvchi ilovadan Telegramʼni ulaganda bilamiz (bot oʻsha paytda birlashtiradi).

Standart — sinov rejimi (hech narsa yozmaydi). Yozish uchun: --apply
    python scripts/migrate_profiles.py
    python scripts/migrate_profiles.py --apply
"""
import collections
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from firebase_admin import firestore  # noqa: E402
from services import gamification  # noqa: E402


def migrate(db, apply=False):
    """Rejani hisoblaydi va apply=True boʻlsa bajaradi. Faqat sonlar qaytaradi."""
    report = collections.Counter()
    level_changes = collections.Counter()
    users = {d.id: d.to_dict() for d in db.collection('users').stream()}
    links = {d.id: d.to_dict() for d in db.collection('telegram_links').stream()}

    # 1. Eski bot profillari → tg_<id>
    moved = {}  # eski id → yangi id
    for doc_id, u in list(users.items()):
        tg = u.get('telegram_id')
        if tg is None or doc_id.startswith('tg_') or u.get('email') or u.get('mergedInto'):
            continue
        tg = str(tg)
        if tg in links:
            report['legacy_already_linked'] += 1
            continue
        new_id = f'tg_{tg}'
        if new_id in users:
            report['legacy_target_exists'] += 1
            continue
        moved[doc_id] = new_id
        report['legacy_moved'] += 1
        data = dict(u, telegram_id=tg, migratedFrom=doc_id, level=gamification.level_id(u))
        users[new_id] = data
        if apply:
            batch = db.batch()
            batch.create(db.collection('users').document(new_id), data)
            batch.create(db.collection('telegram_links').document(tg), {
                'uid': new_id, 'linkedAt': firestore.SERVER_TIMESTAMP, 'source': 'migration'})
            batch.update(db.collection('users').document(doc_id), {
                'mergedInto': new_id, 'mergedAt': firestore.SERVER_TIMESTAMP})
            batch.commit()
        links[tg] = {'uid': new_id}

    # 2. Test urinishlari: eski profil yoki Telegram ID → profil kaliti
    tg_to_profile = {tg: link['uid'] for tg, link in links.items()}
    for a in db.collection('quiz_attempts').stream():
        user_id = str(a.to_dict().get('userId'))
        target = moved.get(user_id) or tg_to_profile.get(user_id)
        if target and target != user_id:
            report['attempts_rekeyed'] += 1
            if apply:
                a.reference.update({'userId': target, 'migratedFromUserId': user_id})

    # 3. Daraja formati
    for doc_id, u in users.items():
        if u.get('mergedInto') or doc_id in moved:
            continue
        new_level = gamification.level_id(u)
        if u.get('level') != new_level:
            level_changes[f"{type(u.get('level')).__name__}:{u.get('level')} -> {new_level}"] += 1
            report['levels_fixed'] += 1
            if apply:
                db.collection('users').document(doc_id).update({'level': new_level})

    return dict(report), dict(level_changes)


if __name__ == '__main__':
    from loader import get_db
    do_apply = '--apply' in sys.argv
    counts, levels = migrate(get_db(), apply=do_apply)
    print('REJIM:', 'YOZISH' if do_apply else 'SINOV (hech narsa yozilmadi)')
    print('Natija:', counts)
    print('Daraja oʻzgarishlari:', levels)
