from src.database.setup_database import User, UserMessage
from datetime import datetime
from src.utils.utils import save_salt_in_salt_server

async def save_user(Session, lock, username, password, salt):
    async with lock:
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user:
                print("El usuario ya existe")
                raise Exception("El usuario ya existe")
            else:
                new_user = User(username=username, password=password)
                session.add(new_user)
                session.commit()                    
                print("Usuario guardado")
                stored_user = session.query(User).filter_by(username=username).first()
                id = stored_user.id
                save_salt_in_salt_server(id, salt)
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()




async def get_user(Session, lock, username):
    async with lock:
        session = Session()
        try:
            user = session.query(User).filter_by(username=username).first()
            return user
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
async def save_message_count(Session, lock, user_id):
    async with lock:
        session = Session()
        try:
            with session.begin():
                date = datetime.now().date()
                user_message = session.query(UserMessage).filter_by(user_id=user_id, date=date).first()
                if user_message:
                    user_message.cont += 1
                else:
                    new_user_message = UserMessage(user_id=user_id, date=date, cont=1)
                    session.add(new_user_message)
                session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()