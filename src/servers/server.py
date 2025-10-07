#!/usr/bin/env python3
import os
import sys
import tempfile
import socket
import ssl
import threading
import json
import asyncio
import select
import struct
import itertools

# Ajusta sys.path si hace falta según cómo ejecutes tus scripts
# sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
from src.database.setup_database import database_setup
from src.servers.server_request_handler import *       # login/register/message/logout
from src.vpn.vpn_tun_handler import create_tun_interface
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, BestAvailableEncryption
from cryptography.hazmat.backends import default_backend

load_dotenv()

lock = asyncio.Lock()
Session = None

# contador para asignar IDs/IPS únicas a clientes VPN
client_id_counter = itertools.count(2)   # IPs 10.8.0.2, 10.8.0.3, ...

# mapa de sesiones (session_id -> username)
sessions_log = {}

def recv_all(sock, n):
    """ Leer exactamente n bytes del socket, o None si se cierra. """
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data

# -----------------------
# CONTROL SERVER (JSON)
# -----------------------
def handle_control_connection(conn, addr):
    """
    Atiende peticiones JSON (LOGIN, REGISTER, MESSAGE, LOGOUT).
    Cliente envía JSON y espera JSON de respuesta.
    """
    try:
        raw = conn.recv(1048576)
        if not raw:
            return
        try:
            message = json.loads(raw.decode('utf-8'))
        except Exception:
            conn.sendall(json.dumps({"status": "400", "message": "Bad JSON"}).encode('utf-8'))
            return

        action = message.get("ACTION")
        response = {"status": "400", "message": "Acción no válida"}

        try:
            if action == "LOGIN":
                response = asyncio.run(log_in_server_logic(Session, lock, message))
                # si ok, registrar sesión en sessions_log
                if response.get("status") == "200":
                    session_id = response.get("message")
                    sessions_log[str(session_id)] = message.get("U")

            elif action == "REGISTER":
                response = asyncio.run(register_server_logic(Session, lock, message))
                if response.get("status") == "200":
                    session_id = response.get("message")
                    sessions_log[str(session_id)] = message.get("U")

            elif action == "MESSAGE":
                # message_server_logic espera sessions_log según tu implementación
                response = asyncio.run(message_server_logic(Session, lock, message, sessions_log))

            elif action == "LOGOUT":
                response = log_out_server_logic(message)
                # opcional: eliminar sesión si existe
                sid = message.get("session_id")
                if sid and str(sid) in sessions_log:
                    del sessions_log[str(sid)]

        except Exception as e:
            response = {"status": "500", "message": f"Server handler error: {e}"}

        # Añadir vpn_port para que el cliente sepa dónde conectarse para VPN
        try:
            control_port = int(os.getenv("SERVER_PORT", "20000"))
            vpn_port = int(os.getenv("SERVER_VPN_PORT", str(control_port + 1)))
            if response.get("status") == "200":
                response["vpn_port"] = vpn_port
        except Exception:
            pass

        conn.sendall(json.dumps(response).encode('utf-8'))

    except Exception as e:
        try:
            conn.sendall(json.dumps({"status": "500", "message": "Server internal error"}).encode('utf-8'))
        except Exception:
            pass
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        conn.close()


def start_control_server(host, control_port, ssl_context):
    """ Listener TLS para control (JSON). """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, control_port))
    sock.listen(8)
    print(f"[CONTROL] escuchando en {host}:{control_port}")

    with ssl_context.wrap_socket(sock, server_side=True) as ssock:
        while True:
            conn, addr = ssock.accept()
            t = threading.Thread(target=handle_control_connection, args=(conn, addr), daemon=True)
            t.start()


# -----------------------
# VPN SERVER (TUN + framing)
# -----------------------
def handle_vpn_client(conn, addr, client_id):
    """
    Handler para la conexión VPN: crea TUN local para este cliente y hace framing
    (4 bytes big-endian length + packet) por la conexión TLS.
    """
    print(f"[VPN] Cliente conectado: {addr}, id={client_id}")
    tun_name = f"tun{client_id}"
    tun_ip = f"10.8.0.{client_id}/24"

    # crear interfaz TUN (requiere permisos)
    tun = create_tun_interface(tun_name, tun_ip)

    try:
        while True:
            rlist, _, _ = select.select([conn, tun], [], [])
            # Packet desde TUN -> al cliente
            if tun in rlist:
                packet = os.read(tun, 65536)
                if packet:
                    length = struct.pack("!I", len(packet))
                    conn.sendall(length + packet)

            # Packet desde cliente -> escribir en TUN
            if conn in rlist:
                hdr = recv_all(conn, 4)
                if not hdr:
                    print("[VPN] cliente desconectado")
                    break
                (packet_len,) = struct.unpack("!I", hdr)
                packet = recv_all(conn, packet_len)
                if packet is None:
                    print("[VPN] cliente desconectado mientras enviaba paquete")
                    break
                os.write(tun, packet)

    except Exception as e:
        print(f"[VPN] error en handler de cliente {addr}: {e}")
    finally:
        # limpiar
        try:
            os.system(f"ip link set dev {tun_name} down")
            os.system(f"ip addr del {tun_ip} dev {tun_name}")
        except Exception:
            pass
        try:
            os.close(tun)
        except Exception:
            pass
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        conn.close()
        print(f"[VPN] Conexión con {addr} cerrada y {tun_name} eliminada.")


def start_vpn_server(host, vpn_port, ssl_context):
    """ Listener TLS para VPN (framing + TUN). """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, vpn_port))
    sock.listen(8)
    print(f"[VPN] escuchando en {host}:{vpn_port}")

    with ssl_context.wrap_socket(sock, server_side=True) as ssock:
        while True:
            conn, addr = ssock.accept()
            client_id = next(client_id_counter)
            t = threading.Thread(target=handle_vpn_client, args=(conn, addr, client_id), daemon=True)
            t.start()


# -----------------------
# START SERVER (ambos listeners)
# -----------------------
def start_ssl_server():
    global Session
    host = str(os.getenv("SERVER_HOSTNAME", "0.0.0.0"))
    control_port = int(os.getenv("SERVER_PORT", "20000"))
    vpn_port = int(os.getenv("SERVER_VPN_PORT", str(control_port + 1)))

    # DB session
    Session = database_setup()

    # Preparar certificado (keystore.p12 -> PEM temporal)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    KEYSTORE_PATH = os.path.join(BASE_DIR, "..", "..", "resources", "keystore.p12")
    with open(KEYSTORE_PATH, "rb") as p12_file:
        p12_data = p12_file.read()

    private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
        p12_data,
        os.getenv("KEYSTORE_PASSWORD").encode("utf-8"),
        default_backend()
    )

    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as temp_key_cert_file:
        pem_private_key = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=BestAvailableEncryption(os.getenv("KEYSTORE_PASSWORD").encode("utf-8"))
        )
        pem_cert = certificate.public_bytes(Encoding.PEM)
        temp_key_cert_file.write(pem_cert)
        temp_key_cert_file.write(pem_private_key)
        temp_key_cert_path = temp_key_cert_file.name

    # SSL Context (reutilizable para ambos servicios)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=temp_key_cert_path, keyfile=temp_key_cert_path, password=os.getenv("KEYSTORE_PASSWORD"))
    try:
        ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
    except Exception:
        pass
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3

    # Lanzar listeners en hilos separados
    t_control = threading.Thread(target=start_control_server, args=(host, control_port, ssl_context), daemon=True)
    t_vpn = threading.Thread(target=start_vpn_server, args=(host, vpn_port, ssl_context), daemon=True)
    t_control.start()
    t_vpn.start()

    print(f"[MAIN] Servidor en {host}, CONTROL={control_port}, VPN={vpn_port}")
    # Mantener el hilo principal vivo
    try:
        while True:
            threading.Event().wait(60)
    except KeyboardInterrupt:
        print("Saliendo...")


if __name__ == "__main__":
    start_ssl_server()
