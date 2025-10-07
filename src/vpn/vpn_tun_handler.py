#!/usr/bin/env python3
import os
import fcntl
import struct
import select
import socket
import ssl
import sys

# Constantes para configurar la interfaz TUN
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000


def create_tun_interface(tun_name="tun0", tun_ip="10.8.0.2/24"):
    """
    Crea una interfaz TUN local con una dirección IP.
    """
    try:
        tun = os.open("/dev/net/tun", os.O_RDWR)
        ifr = struct.pack('16sH', tun_name.encode(), IFF_TUN | IFF_NO_PI)
        fcntl.ioctl(tun, TUNSETIFF, ifr)

        # Configurar IP y levantar la interfaz
        os.system(f"ip addr add {tun_ip} dev {tun_name}")
        os.system(f"ip link set dev {tun_name} up")

        print(f"[+] Interfaz {tun_name} creada con IP {tun_ip}")
        return tun

    except PermissionError:
        print("[!] Error: no tienes permisos para crear la interfaz TUN.")
        print("    Ejecuta este script con privilegios de administrador (sudo).")
        sys.exit(1)


def start_vpn_tunnel(host, port, tun_name="tun0", tun_ip="10.8.0.2/24"):
    """
    Establece un túnel SSL con el servidor y vincula el tráfico con la interfaz TUN.
    """
    tun = create_tun_interface(tun_name, tun_ip)

    # Configurar contexto SSL (verificación del servidor)
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.check_hostname = False
    context.load_verify_locations(cafile="resources/server.crt")

    print(f"[+] Conectando al servidor VPN {host}:{port} ...")

    with socket.create_connection((host, port)) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            print("[+] Conexión SSL establecida. Enrutando tráfico...")

            while True:
                # Esperar tráfico en el túnel o desde el servidor
                rlist, _, _ = select.select([tun, ssock], [], [])

                # Si hay datos en el TUN -> enviarlos al servidor
                if tun in rlist:
                    packet = os.read(tun, 4096)
                    if packet:
                        ssock.sendall(struct.pack("!I", len(packet)) + packet)

                # Si hay datos desde el servidor -> escribirlos en el TUN
                if ssock in rlist:
                    hdr = ssock.recv(4)
                    if not hdr:
                        print("[!] Desconectado del servidor.")
                        break
                    (plen,) = struct.unpack("!I", hdr)
                    packet = b''
                    while len(packet) < plen:
                        chunk = ssock.recv(plen - len(packet))
                        if not chunk:
                            break
                        packet += chunk
                    os.write(tun, packet)
