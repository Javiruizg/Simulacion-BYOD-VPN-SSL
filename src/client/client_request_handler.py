# src/client/client_request_handler.py
import os
import json
import socket
import ssl
from dotenv import load_dotenv

# Carga variables de entorno
load_dotenv()

HOST = os.getenv("SERVER_HOSTNAME", "127.0.0.1")
CONTROL_PORT = int(os.getenv("SERVER_PORT", "20000"))
VPN_PORT = int(os.getenv("SERVER_VPN_PORT", str(CONTROL_PORT + 1)))


def request_handler(data, host=HOST, port=CONTROL_PORT, cafile=None, timeout=10):
    """
    Envía una petición JSON (LOGIN, REGISTER, MESSAGE, LOGOUT) al servidor de control (TLS)
    y devuelve la respuesta como dict.
    """
    if cafile is None:
        # Intentamos localizar el crt relativo al proyecto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/
        possible = os.path.join(base_dir, "resources", "server.crt")
        if os.path.exists(possible):
            cafile = possible
        else:
            cafile = None

    try:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if cafile:
            context.load_verify_locations(cafile=cafile)
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                ssock.sendall(json.dumps(data).encode("utf-8"))
                raw = ssock.recv(1048576)
                try:
                    response = json.loads(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    print("[!] Received non-UTF8 response (protocol mismatch):", raw[:64])
                    return {"status": "500", "message": "Protocol mismatch"}
                return response

    except Exception as e:
        print(f"[!] Error en la request: {e}")
        return {"status": "500", "message": "Error interno en cliente"}


# ---------- Helper functions para la clase ClientSocket ----------

def log_in_data_set_up(client_instance):
    username = client_instance.entry_username.get()
    psswd = client_instance.entry_psswd.get()
    return {"ACTION": "LOGIN", "U": username, "P": psswd}


def register_data_set_up(client_instance):
    username = client_instance.entry_username.get()
    psswd = client_instance.entry_psswd.get()
    return {"ACTION": "REGISTER", "U": username, "P": psswd}


def message_data_set_up(client_instance, username, session_id):
    message = client_instance.entry_message.get()
    return {"ACTION": "MESSAGE", "U": username, "M": message, "session_id": session_id}


def log_out_data_set_up(client_instance, session_id, username):
    return {"ACTION": "LOGOUT", "U": username, "session_id": session_id}
