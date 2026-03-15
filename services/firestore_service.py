import firebase_admin
from firebase_admin import credentials, firestore
import config
from loader import get_db
import logging
from google.cloud.firestore_v1 import Increment

class FirestoreService:
    @staticmethod
    def _normalize_tg_id(telegram_id) -> str:
        """Ensure telegram_id is always a string for consistent queries."""
        return str(telegram_id)
    
    @staticmethod
    async def get_user(telegram_id):
        """Fetch user by Telegram ID from 'users' collection."""
        if not get_db(): return None
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            users_ref = get_db().collection('users')
            query = users_ref.where('telegram_id', '==', tg_id).limit(1).stream()
            for doc in query:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            
            # Fallback: try as int (legacy data may have int telegram_id)
            query2 = users_ref.where('telegram_id', '==', int(telegram_id)).limit(1).stream()
            for doc in query2:
                data = doc.to_dict()
                data['id'] = doc.id
                # Fix the data type while we're at it
                doc.reference.update({'telegram_id': tg_id})
                return data
            
            return None
        except Exception as e:
            logging.error(f"Error getting user: {e}")
            return None

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
        """Create a new user document."""
        if not get_db(): return None
        try:
            get_db().collection('users').add(user_data)
            return True
        except Exception as e:
            logging.error(f"Error creating user: {e}")
            return False

    @staticmethod
    async def link_telegram_to_phone(phone_number, telegram_id, full_name):
        """Link Telegram ID to an existing user or create new."""
        if not get_db(): return "error", None
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            users_ref = get_db().collection('users')
            query = users_ref.where('phoneNumber', '==', phone_number).limit(1).stream()
            
            found_doc = None
            for doc in query:
                found_doc = doc
                break
            
            if found_doc:
                found_doc.reference.update({
                    'telegram_id': tg_id,
                    'last_updated_by': 'telegram_bot'
                })
                return "linked", found_doc.to_dict()
            else:
                new_user = {
                    'phoneNumber': phone_number,
                    'telegram_id': tg_id,
                    'firstName': full_name,
                    'xp': 0,
                    'level': 1,
                    'role': 'user',
                    'quiz_correct': 0,
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'last_updated_by': 'telegram_bot'
                }
                get_db().collection('users').add(new_user)
                return "created", new_user
        except Exception as e:
            logging.error(f"Error linking user: {e}")
            return "error", None

    @staticmethod
    async def add_xp(telegram_id, amount):
        """Atomically add XP to user."""
        if not get_db(): return False
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            users_ref = get_db().collection('users')
            query = users_ref.where('telegram_id', '==', tg_id).limit(1).stream()
            
            for doc in query:
                doc.reference.update({
                    'xp': Increment(amount),
                    'last_updated_by': 'telegram_bot'
                })
                return True
            return False
        except Exception as e:
            logging.error(f"Error adding XP: {e}")
            return False

    @staticmethod
    async def increment_quiz_correct(telegram_id, count=1):
        """Atomically increment correct quiz answer count."""
        if not get_db(): return False
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            users_ref = get_db().collection('users')
            query = users_ref.where('telegram_id', '==', tg_id).limit(1).stream()
            for doc in query:
                doc.reference.update({
                    'quiz_correct': Increment(count),
                    'last_updated_by': 'telegram_bot'
                })
                return True
            return False
        except Exception as e:
            logging.error(f"Error incrementing quiz count: {e}")
            return False

    @staticmethod
    async def save_competency_level(telegram_id, level, score):
        """Save the user's digital competency level."""
        if not get_db(): return False
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            users_ref = get_db().collection('users')
            query = users_ref.where('telegram_id', '==', tg_id).limit(1).stream()
            for doc in query:
                doc.reference.update({
                    'digital_level': level,
                    'competency_score': score,
                    'last_updated_by': 'telegram_bot'
                })
                return True
            return False
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
        """Update a user's role."""
        if not get_db(): return False
        try:
            tg_id = FirestoreService._normalize_tg_id(telegram_id)
            users_ref = get_db().collection('users')
            query = users_ref.where('telegram_id', '==', tg_id).limit(1).stream()
            
            for doc in query:
                doc.reference.update({
                    'role': role,
                    'last_updated_by': 'telegram_bot'
                })
                return True
            return False
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
                'xp': user.get('xp', 0),
                'level': user.get('level', 1),
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
            
            # Find the user's Firebase UID from their telegram_id
            user = await FirestoreService.get_user(telegram_id)
            user_id = user.get('uid', tg_id) if user else tg_id
            
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

