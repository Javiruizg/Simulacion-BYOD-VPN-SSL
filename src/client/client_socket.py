#!/usr/bin/env python3
import threading
import tkinter as tk
from tkinter import messagebox

from src.client.client_request_handler import *
# importar start_vpn_tunnel (puede estar en src/vpn/vpn_tun_handler.py)
try:
    from src.vpn.vpn_tun_handler import start_vpn_tunnel
except Exception:
    start_vpn_tunnel = None


class ClientSocket:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Interfaz para cliente")
        self.root.geometry("400x300")
        self.first_view()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.root.mainloop()

    def first_view(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        tk.Label(self.root, text="Nombre de usuario").pack()
        self.entry_username = tk.Entry(self.root)
        self.entry_username.pack()
        tk.Label(self.root, text="Contraseña").pack()
        self.entry_psswd = tk.Entry(self.root, show="*")
        self.entry_psswd.pack()
        tk.Button(self.root, text="Iniciar sesión", command=self.log_in).pack()
        tk.Button(self.root, text="Registrarse", command=self.register).pack()

    def log_in(self):
        username = self.entry_username.get()
        response = request_handler(log_in_data_set_up(self))
        if response.get("status") == "200":
            messagebox.showinfo("Bienvenido", "Has iniciado sesión")
            # Start VPN after login (non-blocking)
            vpn_port = int(response.get("vpn_port", VPN_PORT))
            if start_vpn_tunnel:
                threading.Thread(target=start_vpn_tunnel, args=(HOST, vpn_port), daemon=True).start()
            self.root.after(0, lambda: self.messages_view(username, response.get("message")))
        else:
            self.root.after(0, lambda: messagebox.showwarning("Error", "Usuario y contraseña incorrectos"))

    def register(self):
        username = self.entry_username.get()
        response = request_handler(register_data_set_up(self))
        if response.get("status") == "200":
            messagebox.showinfo("Bienvenido", "¡Registrado con éxito!")
            vpn_port = int(response.get("vpn_port", VPN_PORT))
            if start_vpn_tunnel:
                threading.Thread(target=start_vpn_tunnel, args=(HOST, vpn_port), daemon=True).start()
            self.root.after(0, lambda: self.messages_view(username, response.get("message")))
        else:
            self.root.after(0, lambda: messagebox.showwarning("Error", "No se pudo registrar el usuario, ya existe uno con ese nombre"))

    def messages_view(self, username, session_id):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.root.title(f"Cuenta de: {username}")
        tk.Label(self.root, text="Introduzca su mensaje").pack()
        self.entry_message = tk.Entry(self.root)
        self.entry_message.pack()
        tk.Button(self.root, text="Enviar mensaje", command=lambda: self.send_message(username, session_id)).pack()
        tk.Button(self.root, text="Cerrar sesión", command=lambda: self.log_out(session_id, username)).pack()

    def send_message(self, username, session_id):
        message = self.entry_message.get()
        if len(message) > 144:
            self.root.after(0, lambda: messagebox.showwarning("Error", "No se pueden enviar mensajes de más de 144 caracteres"))
            return
        response = request_handler(message_data_set_up(self, username, session_id))
        if response.get("status") == "200":
            self.root.after(0, lambda: messagebox.showinfo("OK", "Mensaje enviado y recibido correctamente"))
        elif response.get("status") == "403":
            self.close_app()
            messagebox.showwarning("Error", "Problema con la sesión, iniciela de nuevo")
        else:
            self.root.after(0, lambda: messagebox.showwarning("Error", "No se pudo enviar el mensaje"))

    def log_out(self, session_id, username):
        request_handler(log_out_data_set_up(self, session_id, username))
        self.close_app()

    def close_app(self):
        self.root.destroy()


if __name__ == "__main__":
    ClientSocket()
