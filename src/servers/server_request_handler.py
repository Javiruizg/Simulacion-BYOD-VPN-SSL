import base64
import socket
import ssl
import json
import os
import secrets
from dotenv import load_dotenv
from src.database.database_functions import save_user, get_user, save_message_count
from src.utils.utils import hash_password
from src.utils.utils import verify_password, get_salt_from_salt_server


'''
Este request handler se encarga principalmente del procesamiento de peticiones
de los servidores. Está compuesto únicamente por funciones que serán llamadas dentro
de los servidores
'''

# VARIABLES DE ENTORNO DEL SERVIDOR 
load_dotenv()
HOST = str(os.getenv("SALT_HOSTNAME"))
PORT = os.getenv("SALT_PORT")

async def log_in_server_logic(Session, lock, message):
    try:
        username = message.get("U")
        password = message.get("P")

        user = await get_user(Session, lock, username)
        salt = get_salt_from_salt_server(user.id)
        
        comprobar = verify_password(password, salt, user.password)
        
        if comprobar:
            print("Funciona login para el usuario: " + username)
            session_id = secrets.randbits(1024) #session_id generada
            response = {"status": "200", "message": session_id}
        else:
            response = {"status": "401", "message": "Credenciales incorrectas"}
        return response
    except Exception as e:
        return {"status": "401", "message": "Credenciales incorrectas"}


async def register_server_logic(Session, lock, message):
    try:
        username = message.get("U")
        psswd, salt = hash_password(message.get("P"))
        await save_user(Session, lock, username, psswd, salt)
        print("Funciona register para el nuevo usuario: " + username)
        session_id = secrets.randbits(1024) #session_id generada
        return {"status": "200", "message": session_id}
    except Exception as e:
        return {"status": "401", "message": "No se pudo registrar el usuario"}

async def message_server_logic(Session, lock, message, sessions_log):
    try:
        if message:
            if(sessions_log[message.get("session_id")] == message.get("U")): # Además de comprobar si hay mensaje, comprueba si la sesión es correcta
                user = await get_user(Session, lock, message.get("U"))
                user_id = user.id
                await save_message_count(Session, lock, user_id)
                response = {"status": "200", "message": "Mensaje enviado correctamente"}
            else:
                response = {"status": "403", "message": "Sesión incorrecta"}
        
        else:
            response = {"status": "400", "message": "No se recibió ningún mensaje"}
        return response
    except Exception as e:
        return {"status": "400", "message": "No se recibió ningún mensaje"}

def log_out_server_logic(message):
    response = {"status": "200", "message": "Desconexión exitosa"}
    return response

