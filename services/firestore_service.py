import firebase_admin
from firebase_admin import credentials, firestore
import config
from loader import get_db
import hashlib
import logging
from datetime import datetime, timezone
from google.cloud.firestore_v1 import Increment
from services import gamification

class FirestoreService:
    @staticmethod
    def _normalize_tg_id(telegram_id) -> str:
        """Ensure telegram_id is always a string for consistent queries."""
        return str(telegram_id)
    
    # ─── Yagona profil ────────────────────────────────────────────
    # Asosiy kalit — ilovadagi Firebase Auth uid. Telegram ID unga
    # telegram_links/{telegram_id} = {uid} orqali bogʻlanadi (bitta Telegram —
    # bitta profil). Faqat botdan foydalanuvchilar users/tg_<telegram_id>
    # profilini oladi; ilovadan ulansa bogʻlanish ilova uid siga koʻchadi.

    @staticmethod
    def _bot_uid(telegram_id) -> str:
        return f"tg_{FirestoreService._normalize_tg_id(telegram_id)}"

    @staticmethod
    def _user_ref(telegram_id):
        """Telegram ID boʻyicha profil hujjati havolasi (yoki None)."""
        db = get_db()
        tg_id = FirestoreService._normalize_tg_id(telegram_id)
        link = db.collection('telegram_links').document(tg_id).get()
        if link.exists and link.to_dict().get('uid'):
            return db.collection('users').document(link.to_dict()['uid'])

        # Bogʻlanishdan oldingi eski yozuvlar (avto-ID, telegram_id maydoni)
        users_ref = db.collection('users')
        for value in (tg_id, int(tg_id) if tg_id.isdigit() else None):
            if value is None:
                continue
            for doc in users_ref.where('telegram_id', '==', value).limit(1).stream():
                return doc.reference
        return None

    @staticmethod
    async def get_user(telegram_id):
        """Fetch the single profile for this Telegram ID."""
        if not get_db(): return None
        try:
            ref = FirestoreService._user_ref(telegram_id)
            if ref is None:
                return None
            snap = ref.get()
            if not snap.exists:
                return None
            data = snap.to_dict()
            data['id'] = snap.id
            return data
        except Exception as e:
            logging.error(f"Error getting user: {e}")
            return None

    @staticmethod
    async def link_with_code(code, telegram_id):
        """
        Ilovadagi "Telegramʼni ulash" kodini qabul qiladi (functions:
        createTelegramLinkCode). Holat: linked | already | expired | invalid |
        other_account | error. Eski tg_ profil birlashtirish uchun saqlanadi.
        """
        if not get_db(): return 'error'
        try:
            db = get_db()
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            code_ref = db.collection('telegram_link_codes').document(str(code).strip().upper())
            link_ref = db.collection('telegram_links').document(tg_id)

            @firestore.transactional
            def _link(tx):
                code_snap = code_ref.get(transaction=tx)
                if not code_snap.exists:
                    return 'invalid'
                uid = code_snap.to_dict().get('uid')
                expires_at = code_snap.to_dict().get('expiresAt')
                user_ref = db.collection('users').document(uid) if uid else None
                link_snap = link_ref.get(transaction=tx)
                user_snap = user_ref.get(transaction=tx) if user_ref else None

                if expires_at is None or expires_at <= datetime.now(timezone.utc):
                    tx.delete(code_ref)
                    return 'expired'
                if user_snap is None or not user_snap.exists:
                    return 'invalid'

                previous = link_snap.to_dict().get('uid') if link_snap.exists else None
                if previous == uid:
                    tx.delete(code_ref)
                    return 'already'
                if previous and not previous.startswith('tg_'):
                    return 'other_account'

                tx.set(link_ref, {
                    'uid': uid,
                    'previousUid': previous,
                    'linkedAt': firestore.SERVER_TIMESTAMP,
                })
                tx.update(user_ref, {
                    'telegram_id': tg_id,
                    'telegramLinkedAt': firestore.SERVER_TIMESTAMP,
                })
                tx.delete(code_ref)
                return 'linked'

            status = _link(db.transaction())
            if status == 'linked':
                FirestoreService._merge_previous_profile(db, tg_id)
            return status
        except Exception as e:
            logging.error(f"Error linking Telegram with code: {e}")
            return 'error'

    @staticmethod
    def _merge_previous_profile(db, tg_id):
        """Ulashdan keyin shu Telegram ning avvalgi bot profilini ilova profiliga qoʻshadi."""
        try:
            link = db.collection('telegram_links').document(tg_id).get().to_dict() or {}
            uid = link.get('uid')
            sources = [link['previousUid']] if link.get('previousUid') else []
            # Migratsiyadan oldingi avto-ID yozuvlar
            for value in (tg_id, int(tg_id) if tg_id.isdigit() else None):
                if value is None:
                    continue
                for doc in db.collection('users').where('telegram_id', '==', value).stream():
                    if doc.id != uid and doc.id not in sources:
                        sources.append(doc.id)
            for src_id in sources:
                FirestoreService.merge_profile(src_id, uid)
        except Exception as e:
            # Ulash bajarilgan; birlashtirish keyin migratsiya skripti bilan takrorlanishi mumkin
            logging.error(f"Error merging previous profile for {tg_id}: {e}")

    @staticmethod
    async def get_user_by_phone(phone_number):
        """Fetch user by Phone Number."""
        if not get_db(): return None
        try:
            users_ref = get_db().collection('users')
            query = users_ref.where('phoneNumber', '==', phone_number).limit(1).stream()
            for doc in query:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            logging.error(f"Error getting user by phone: {e}")
            return None

    @staticmethod
    async def create_user(user_data):
        """
        Faqat botdan foydalanuvchi uchun users/tg_<telegram_id> profilini va
        telegram_links bogʻlanishini yaratadi. Profil allaqachon boʻlsa False.
        """
        if not get_db(): return None
        try:
            db = get_db()
            tg_id = FirestoreService._normalize_tg_id(user_data['telegram_id'])
            uid = FirestoreService._bot_uid(tg_id)
            if FirestoreService._user_ref(tg_id) is not None:
                return False
            batch = db.batch()
            batch.create(db.collection('users').document(uid), dict(user_data, telegram_id=tg_id))
            batch.create(db.collection('telegram_links').document(tg_id), {
                'uid': uid,
                'linkedAt': firestore.SERVER_TIMESTAMP,
            })
            batch.commit()
            return True
        except Exception as e:
            logging.error(f"Error creating user: {e}")
            return False

    @staticmethod
    async def link_telegram_to_phone(phone_number, telegram_id, full_name):
        """
        Telefon raqamini Telegram profiliga yozadi. Boshqa hisoblarga telefon
        orqali bogʻlanmaydi: ilova hisobiga ulash faqat bir martalik kod bilan.
        """
        if not get_db(): return "error", None
        try:
            ref = FirestoreService._user_ref(telegram_id)
            if ref is not None:
                ref.update({'phoneNumber': phone_number, 'last_updated_by': 'telegram_bot'})
                data = ref.get().to_dict()
                return "linked", data
            new_user = {
                'phoneNumber': phone_number,
                'telegram_id': FirestoreService._normalize_tg_id(telegram_id),
                'firstName': full_name,
                'xp': 0,
                'level': 'levelBeginner',
                'role': 'user',
                'quiz_correct': 0,
                'createdAt': firestore.SERVER_TIMESTAMP,
                'last_updated_by': 'telegram_bot'
            }
            if not await FirestoreService.create_user(new_user):
                return "error", None
            return "created", new_user
        except Exception as e:
            logging.error(f"Error linking user: {e}")
            return "error", None

    @staticmethod
    async def award_quiz(telegram_id, quiz_id, score, total):
        """
        Test uchun XP ni ilova serveridagi qoidalar bilan beradi (awardXp callable):
        70% dan o'tilsa +20, 100% bo'lsa +70, bitta test uchun bir marta
        (users/{id}/xp_awards belgisi ilova bilan umumiy).
        Qaytaradi: (berilgan XP, holat) — holat: awarded | duplicate | not_eligible | no_user | error.
        """
        action = gamification.quiz_action(quiz_id, score, total)
        if not action:
            return 0, 'not_eligible'
        if not get_db():
            return 0, 'error'
        try:
            user = await FirestoreService.get_user(telegram_id)
            if not user:
                return 0, 'no_user'
            db = get_db()
            return FirestoreService._award_quiz_to(
                db, db.collection('users').document(user['id']), quiz_id, action)
        except Exception as e:
            logging.error(f"Error awarding quiz XP: {e}")
            return 0, 'error'

    @staticmethod
    def _award_quiz_to(db, user_ref, quiz_id, action):
        """Bitta test uchun mukofot tranzaksiyasi (ilova xp_awards kaliti bilan)."""
        key = gamification.quiz_dedup_key(quiz_id)
        award_ref = user_ref.collection('xp_awards').document(
            hashlib.sha256(key.encode('utf-8')).hexdigest())
        points = gamification.quiz_points(action)

        @firestore.transactional
        def _award(tx):
            snap = user_ref.get(transaction=tx)
            if award_ref.get(transaction=tx).exists:
                return 0, 'duplicate'
            after = gamification.apply_quiz_award(
                gamification.counters_of(snap.to_dict() or {}), action, points)
            tx.create(award_ref, {
                'key': key,
                'action': action,
                'points': points,
                'source': 'telegram_bot',
                'createdAt': firestore.SERVER_TIMESTAMP,
            })
            tx.update(user_ref, {
                'xp': after['xp'],
                'level': gamification.calculate_level(after),
                'quizzesPassed': after['quizzes_passed'],
                'totalQuizzesAced': after['quizzes_aced'],
                'lastActivity': firestore.SERVER_TIMESTAMP,
                'last_updated_by': 'telegram_bot',
            })
            return points, 'awarded'

        return _award(db.transaction())

    # Bot profilidan ilova profiliga, agar u yerda boʻsh boʻlsa, koʻchiriladigan maydonlar
    MERGE_FILL_FIELDS = ('phoneNumber', 'courtName', 'courtType', 'region', 'position',
                         'digital_level', 'competency_score', 'firstName', 'fullName')

    @staticmethod
    def merge_profile(src_id, dst_id):
        """
        Bot profilini (src) ilova profiliga (dst) birlashtiradi:
        test urinishlari dst ga oʻtadi, XP ilova qoidalari bilan urinishlardan
        qayta hisoblanadi (dst da bor mukofotlar takrorlanmaydi), boʻsh maydonlar
        toʻldiriladi, src `mergedInto` bilan belgilanadi (oʻchirilmaydi).
        Takror chaqirilsa hech narsa qilmaydi. Qaytaradi: berilgan XP yoki None.
        """
        db = get_db()
        src_ref = db.collection('users').document(src_id)
        dst_ref = db.collection('users').document(dst_id)
        src = src_ref.get().to_dict()
        dst = dst_ref.get().to_dict()
        if src is None or dst is None or src.get('mergedInto') or src_id == dst_id:
            return None

        attempts = list(db.collection('quiz_attempts').where('userId', '==', src_id).stream())
        for a in attempts:
            a.reference.update({'userId': dst_id, 'mergedFrom': src_id})

        awarded = 0
        actions = gamification.best_quiz_actions([a.to_dict() for a in attempts])
        for quiz_id, action in actions.items():
            points, _ = FirestoreService._award_quiz_to(db, dst_ref, quiz_id, action)
            awarded += points

        fill = {f: src[f] for f in FirestoreService.MERGE_FILL_FIELDS
                if src.get(f) not in (None, '') and dst.get(f) in (None, '')}
        if gamification.to_int(src.get('quiz_correct')):
            fill['quiz_correct'] = Increment(gamification.to_int(src.get('quiz_correct')))
        if fill:
            dst_ref.update(fill)
        src_ref.update({'mergedInto': dst_id, 'mergedAt': firestore.SERVER_TIMESTAMP})
        logging.info(f"Merged profile {src_id} -> {dst_id}: {len(attempts)} attempts, +{awarded} XP")
        return awarded

    @staticmethod
    async def increment_quiz_correct(telegram_id, count=1):
        """Atomically increment correct quiz answer count."""
        if not get_db(): return False
        try:
            ref = FirestoreService._user_ref(telegram_id)
            if ref is None:
                return False
            ref.update({
                'quiz_correct': Increment(count),
                'last_updated_by': 'telegram_bot'
            })
            return True
        except Exception as e:
            logging.error(f"Error incrementing quiz count: {e}")
            return False

    @staticmethod
    async def save_competency_level(telegram_id, level, score):
        """Save the user's digital competency level."""
        if not get_db(): return False
        try:
            ref = FirestoreService._user_ref(telegram_id)
            if ref is None:
                return False
            ref.update({
                'digital_level': level,
                'competency_score': score,
                'last_updated_by': 'telegram_bot'
            })
            return True
        except Exception as e:
            logging.error(f"Error saving competency: {e}")
            return False

    @staticmethod
    async def save_message(telegram_id, role, text):
        """Save a message to the user's conversation history."""
        if not get_db(): return False
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            get_db().collection('conversations').add({
                'telegram_id': tg_id,
                'role': role,
                'text': text,
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            return True
        except Exception as e:
            logging.error(f"Error saving message: {e}")
            return False

    @staticmethod
    async def get_recent_messages(telegram_id, limit=6):
        """Get recent chat history for a user."""
        if not get_db(): return []
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            query = get_db().collection('conversations')\
                      .where('telegram_id', '==', tg_id)\
                      .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                      .limit(limit)\
                      .stream()
            
            messages = []
            for doc in query:
                data = doc.to_dict()
                if 'text' in data and 'role' in data:
                    messages.append({'role': data['role'], 'text': data['text']})
            
            messages.reverse()
            return messages
        except Exception as e:
            logging.error(f"Error getting recent messages: {e}")
            return []

    @staticmethod
    async def update_user_role(telegram_id, role):
        """Update a user's role (faqat ilovadagi lavozimlar; admin berilmaydi)."""
        if not gamification.is_allowed_role(role):
            logging.warning(f"Rejected role update to {role!r} for {telegram_id}")
            return False
        if not get_db(): return False
        try:
            ref = FirestoreService._user_ref(telegram_id)
            if ref is None:
                return False
            ref.update({
                'role': role,
                'last_updated_by': 'telegram_bot'
            })
            return True
        except Exception as e:
            logging.error(f"Error updating user role: {e}")
            return False

    @staticmethod
    async def get_user_stats(telegram_id):
        """Get comprehensive user statistics."""
        if not get_db(): return None
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            user = await FirestoreService.get_user(telegram_id)
            if not user:
                return None
            
            # Count user messages
            msg_query = get_db().collection('conversations')\
                          .where('telegram_id', '==', tg_id)\
                          .where('role', '==', 'user')\
                          .stream()
            message_count = sum(1 for _ in msg_query)
            
            # Format join date
            created_at = user.get('createdAt')
            if created_at:
                try:
                    member_since = created_at.strftime('%Y-%m-%d')
                except Exception:
                    member_since = str(created_at)[:10]
            else:
                member_since = "Noma'lum"
            
            return {
                'xp': gamification.to_int(user.get('xp')),
                'level': gamification.level_id(user),
                'quiz_correct': user.get('quiz_correct', 0),
                'message_count': message_count,
                'member_since': member_since,
            }
        except Exception as e:
            logging.error(f"Error getting user stats: {e}")
            return None

    @staticmethod
    async def clear_history(telegram_id):
        """Clear conversation history for a user."""
        if not get_db(): return False
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            query = get_db().collection('conversations')\
                      .where('telegram_id', '==', tg_id)\
                      .stream()
            
            batch = get_db().batch()
            count = 0
            for doc in query:
                batch.delete(doc.reference)
                count += 1
                # Firestore batch limit is 500
                if count >= 500:
                    batch.commit()
                    batch = get_db().batch()
                    count = 0
            
            if count > 0:
                batch.commit()
            
            logging.info(f"Cleared history for user {tg_id}")
            return True
        except Exception as e:
            logging.error(f"Error clearing history: {e}")
            return False

    # ─── Shared Quiz Methods (synced with Flutter app) ──────────
    @staticmethod
    async def get_all_quizzes():
        """
        Get all quiz topics with question counts.
        Returns list of: {id, title, description, question_count}
        """
        if not get_db(): return []
        try:
            quizzes_ref = get_db().collection('quizzes').stream()
            quizzes = []
            
            for doc in quizzes_ref:
                data = doc.to_dict()
                # Count questions in subcollection
                q_count = 0
                q_ref = get_db().collection('quizzes').document(doc.id)\
                          .collection('questions').stream()
                for _ in q_ref:
                    q_count += 1
                
                quizzes.append({
                    'id': doc.id,
                    'title': data.get('title', 'Test'),
                    'description': data.get('description', ''),
                    'question_count': q_count,
                })
            
            logging.info(f"Found {len(quizzes)} quizzes in Firestore")
            return quizzes
        except Exception as e:
            logging.error(f"Error fetching quizzes: {e}")
            return []

    @staticmethod
    async def get_quiz_questions_by_id(quiz_id):
        """
        Get all questions from a specific quiz by its Firestore ID.
        """
        if not get_db(): return []
        try:
            quiz_doc = get_db().collection('quizzes').document(quiz_id).get()
            if not quiz_doc.exists:
                return []
            
            quiz_data = quiz_doc.to_dict()
            quiz_title = quiz_data.get('title', 'Test')
            
            questions_ref = get_db().collection('quizzes').document(quiz_id)\
                              .collection('questions').stream()
            
            questions = []
            for q_doc in questions_ref:
                q_data = q_doc.to_dict()
                if q_data.get('questionText') and q_data.get('options') and q_data.get('correctAnswer'):
                    q_data['quiz_id'] = quiz_id
                    q_data['quiz_title'] = quiz_title
                    q_data['id'] = q_doc.id
                    questions.append(q_data)
            
            logging.info(f"Quiz '{quiz_title}': {len(questions)} ta savol yuklandi")
            return questions
        except Exception as e:
            logging.error(f"Error fetching quiz questions: {e}")
            return []

    @staticmethod
    async def get_random_quiz_questions(count=5):
        """
        Fetch random quiz questions from Firestore.
        Same collection structure as Flutter app: quizzes/{quizId}/questions/{questionId}
        """
        if not get_db(): return []
        try:
            # Get all available quizzes
            quizzes_ref = get_db().collection('quizzes').stream()
            all_questions = []
            
            for quiz_doc in quizzes_ref:
                quiz_data = quiz_doc.to_dict()
                quiz_id = quiz_doc.id
                quiz_title = quiz_data.get('title', 'Test')
                
                # Get questions subcollection
                questions_ref = get_db().collection('quizzes').document(quiz_id)\
                                  .collection('questions').stream()
                
                for q_doc in questions_ref:
                    q_data = q_doc.to_dict()
                    if q_data.get('questionText') and q_data.get('options') and q_data.get('correctAnswer'):
                        q_data['quiz_id'] = quiz_id
                        q_data['quiz_title'] = quiz_title
                        q_data['id'] = q_doc.id
                        all_questions.append(q_data)
            
            if not all_questions:
                return []
            
            # Randomize and pick 'count' questions
            import random
            random.shuffle(all_questions)
            selected = all_questions[:count]
            
            logging.info(f"Firestore quiz: {len(all_questions)} ta savoldan {len(selected)} ta tanlandi")
            return selected
            
        except Exception as e:
            logging.error(f"Error fetching quiz questions: {e}")
            return []

    @staticmethod
    async def save_quiz_attempt(telegram_id, quiz_id, quiz_title, score, total_questions):
        """
        Save quiz attempt to Firestore — same format as Flutter app's quiz_attempts.
        This allows Flutter app to display bot quiz results too.
        """
        if not get_db(): return False
        try:
            from google.cloud.firestore_v1 import SERVER_TIMESTAMP
            
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            
            # Profil kaliti: ulangan boʻlsa ilova uid si — natija ilovada ham koʻrinadi
            user = await FirestoreService.get_user(telegram_id)
            user_id = user['id'] if user else tg_id
            
            attempt_data = {
                'userId': user_id,
                'quizId': quiz_id,
                'quizTitle': quiz_title,
                'score': score,
                'totalQuestions': total_questions,
                'attemptedAt': SERVER_TIMESTAMP,
                'source': 'telegram_bot',
                'telegramId': tg_id,
            }
            
            get_db().collection('quiz_attempts').add(attempt_data)
            logging.info(f"Quiz attempt saved: {score}/{total_questions} for user {tg_id}")
            return True
        except Exception as e:
            logging.error(f"Error saving quiz attempt: {e}")
            return False

    # ─── Court Selection Methods ──────────────────────────────────
    @staticmethod
    async def get_unique_regions() -> list:
        """Firestore courts kolleksiyasidan unique regionlar ro'yxatini olish."""
        if not get_db(): return []
        try:
            docs = get_db().collection('courts').stream()
            regions = set()
            for doc in docs:
                data = doc.to_dict()
                region = data.get('region', '')
                if region:
                    regions.add(region)
            # Toshkent shahri/viloyati birinchi, qolganlari alifbo tartibida
            sorted_regions = sorted(regions)
            priority = ["Toshkent shahri", "Toshkent viloyati"]
            result = [r for r in priority if r in sorted_regions]
            result += [r for r in sorted_regions if r not in priority]
            return result
        except Exception as e:
            logging.error(f"Error getting regions: {e}")
            return []

    @staticmethod
    async def get_courts_by_region_and_type(region: str, court_type: str) -> list:
        """Berilgan hudud va sud turi bo'yicha sudlar ro'yxatini olish."""
        if not get_db(): return []
        try:
            docs = get_db().collection('courts')\
                      .where('region', '==', region)\
                      .where('courtType', '==', court_type)\
                      .order_by('courtName')\
                      .stream()
            courts = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                courts.append(data)
            return courts
        except Exception as e:
            logging.error(f"Error getting courts by region/type: {e}")
            return []

    @staticmethod
    async def update_court_info(telegram_id, court_data: dict) -> bool:
        """Foydalanuvchining sud ma'lumotlarini Firestorega yozish."""
        if not get_db(): return False
        try:
            ref = FirestoreService._user_ref(telegram_id)
            if ref is None:
                return False
            ref.update({
                'courtName': court_data.get('courtName', ''),
                'courtType': court_data.get('courtType', ''),
                'region': court_data.get('region', ''),
                'position': court_data.get('position', ''),
                'last_updated_by': 'telegram_bot',
            })
            logging.info(f"Court info updated for {telegram_id}: {court_data}")
            return True
        except Exception as e:
            logging.error(f"Error updating court info: {e}")
            return False


    @staticmethod
    async def get_resources_by_type(resource_type=None):
        if not get_db(): return []
        try:
            query = get_db().collection('resources')
            if resource_type:
                query = query.where('type', '==', resource_type)
            docs = query.stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            return results
        except Exception as e:
            logging.error(f'Error getting resources: {e}')
            return []

    @staticmethod
    async def get_knowledge_base_articles(category=None, limit=10):
        if not get_db(): return []
        try:
            query = get_db().collection('knowledge_base')
            if category:
                query = query.where('category', '==', category)
            query = query.limit(limit)
            docs = query.stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            return results
        except Exception as e:
            logging.error(f'Error getting articles: {e}')
            return []

    @staticmethod
    async def get_faqs_by_category(category=None):
        if not get_db(): return []
        try:
            query = get_db().collection('faqs')
            if category:
                query = query.where('category', '==', category)
            docs = query.stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            return results
        except Exception as e:
            logging.error(f'Error getting FAQs: {e}')
            return []

    # ─── Course Methods ───────────────────────────────────────────
    @staticmethod
    async def get_courses():
        """Fetch all published courses."""
        if not get_db(): return []
        try:
            query = get_db().collection('courses')\
                      .where('isPublished', '==', True)\
                      .order_by('order')\
                      .stream()
            results = []
            for doc in query:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            return results
        except Exception as e:
            logging.error(f'Error getting courses: {e}')
            return []

    @staticmethod
    async def get_course_by_id(course_id):
        """Fetch a specific course by its Firestore ID."""
        if not get_db(): return None
        try:
            doc = get_db().collection('courses').document(course_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            logging.error(f'Error getting course by id {course_id}: {e}')
            return None
