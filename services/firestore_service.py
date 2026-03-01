import firebase_admin
from firebase_admin import credentials, firestore
import config
from loader import db
import logging
from google.cloud.firestore_v1 import Increment

class FirestoreService:
    @staticmethod
    async def get_user(telegram_id):
        """Fetch user by Telegram ID from 'users' collection."""
        if not db: return None
        try:
            users_ref = db.collection('users')
            # Assuming we store documents with telegram_id as ID or field.
            # Ideally, use telegram_id as document ID for faster lookup if possible, 
            # but if linking to existing app users, we search by field.
            
            # Strategy: Search by field 'telegram_id'
            query = users_ref.where('telegram_id', '==', telegram_id).limit(1).stream()
            for doc in query:
                data = doc.to_dict()
                data['id'] = doc.id # Include doc ID
                return data
            return None
        except Exception as e:
            logging.error(f"Error getting user: {e}")
            return None

    @staticmethod
    async def get_user_by_phone(phone_number):
        """Fetch user by Phone Number."""
        if not db: return None
        try:
            users_ref = db.collection('users')
            # Phone number format should be consistent (e.g., +998...)
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
        if not db: return None
        try:
            # We can let Firestore auto-generate ID or use phone/telegram_id
            # User_data should include: phoneNumber, telegram_id, xp, level, firstName, etc.
            db.collection('users').add(user_data)
            return True
        except Exception as e:
            logging.error(f"Error creating user: {e}")
            return False

    @staticmethod
    async def link_telegram_to_phone(phone_number, telegram_id, full_name):
        """Link Telegram ID to an existing user or create new."""
        if not db: return "error", None
        try:
            users_ref = db.collection('users')
            query = users_ref.where('phoneNumber', '==', phone_number).limit(1).stream()
            
            found_doc = None
            for doc in query:
                found_doc = doc
                break
            
            if found_doc:
                # Update existing user
                found_doc.reference.update({
                    'telegram_id': telegram_id,
                    'last_updated_by': 'telegram_bot'
                })
                return "linked", found_doc.to_dict()
            else:
                # Create new user
                new_user = {
                    'phoneNumber': phone_number,
                    'telegram_id': telegram_id,
                    'firstName': full_name,
                    'xp': 0,
                    'level': 1,
                    'role': 'user',
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'last_updated_by': 'telegram_bot'
                }
                db.collection('users').add(new_user)
                return "created", new_user
        except Exception as e:
            logging.error(f"Error linking user: {e}")
            return "error", None

    @staticmethod
    async def add_xp(telegram_id, amount):
        """Atomically add XP to user."""
        if not db: return False
        try:
            users_ref = db.collection('users')
            query = users_ref.where('telegram_id', '==', telegram_id).limit(1).stream()
            
            for doc in query:
                # atomic increment
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
    async def save_message(telegram_id, role, text):
        """Save a message to the user's conversation history."""
        if not db: return False
        try:
            # We store conversations in a subcollection or a root collection. Let's use a root collection 'conversations'
            # with user's telegram_id as part of the path, or just a separate document per message.
            # Best is /users/{user_doc_id}/history/{message_id} but we have telegram_id. 
            # Alternatively: /conversations with telegram_id field.
            db.collection('conversations').add({
                'telegram_id': str(telegram_id),
                'role': role, # 'user' or 'model'
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
        if not db: return []
        try:
            # Query recent messages for this user, ordered by timestamp desc
            query = db.collection('conversations')\
                      .where('telegram_id', '==', str(telegram_id))\
                      .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                      .limit(limit)\
                      .stream()
            
            messages = []
            for doc in query:
                data = doc.to_dict()
                if 'text' in data and 'role' in data:
                    messages.append({'role': data['role'], 'text': data['text']})
            
            # Reverse to get chronological order
            messages.reverse()
            return messages
        except Exception as e:
            logging.error(f"Error getting recent messages: {e}")
            return []

    @staticmethod
    async def update_user_role(telegram_id, role):
        """Update a user's role."""
        if not db: return False
        try:
            users_ref = db.collection('users')
            query = users_ref.where('telegram_id', '==', str(telegram_id)).limit(1).stream()
            
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
