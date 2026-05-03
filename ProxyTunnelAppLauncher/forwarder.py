# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
import socket
import sys
import threading
from typing import Callable, Optional

import socks
from PyQt6.QtCore import QCoreApplication


class SimpleForwarder:
    BUFFER_SIZE = 16384

    def __init__(self, listen_host: str, listen_port: int,
                 target_host: str, target_port: int,
                 socks_host: str, socks_port: int,
                 socks_user: Optional[str] = None,
                 socks_pass: Optional[str] = None,
                 logger: Optional[Callable] = None):
        self.listen_host = listen_host
        self.listen_port = int(listen_port)
        self.target_host = target_host
        self.target_port = int(target_port)
        self.socks_host  = socks_host
        self.socks_port  = int(socks_port)
        self.socks_user  = socks_user
        self.socks_pass  = socks_pass
        self._server_sock      = None
        self._accept_thread    = None
        self._stop_event       = threading.Event()
        self._connections      = []
        self._connections_lock = threading.Lock()
        self.logger = logger or (lambda level, msg: None)

    def log(self, level: str, *args):
        try:
            self.logger(level, f"[{self.listen_host}:{self.listen_port}] " + " ".join(map(str, args)))
        except Exception:
            pass

    def start(self):
        if self._accept_thread and self._accept_thread.is_alive():
            self.log("WARNING", "already running")
            return
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(3)
                probe.connect((self.socks_host, self.socks_port))
        except OSError:
            raise OSError(
                QCoreApplication.translate("App", "Proxy SOCKS5 inaccessible : {}:{}").format(
                    self.socks_host, self.socks_port)
            )

        self._stop_event.clear()
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform == "win32":
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server_sock.bind((self.listen_host, self.listen_port))
        except OSError as e:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
            raise OSError(
                QCoreApplication.translate("App", "Port {} indisponible sur {} : {}").format(
                    self.listen_port, self.listen_host, e.strerror)
            ) from e
        self._server_sock.listen(8)
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        self.log("INFO", "server started, listening")

    def stop(self):
        self.log("INFO", "stopping server...")
        self._stop_event.set()
        try:
            if self._server_sock:
                self._server_sock.close()
        except Exception:
            pass
        with self._connections_lock:
            connections = list(self._connections)
        for c, r in connections:
            for s in (c, r):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    s.close()
                except Exception:
                    pass
        with self._connections_lock:
            self._connections.clear()
        if self._accept_thread:
            self._accept_thread.join(timeout=0.5)
        self.log("INFO", "stopped")

    def _accept_loop(self):
        while not self._stop_event.is_set():
            try:
                self._server_sock.settimeout(1.0)
                client_sock, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.log("INFO", "incoming from", addr)
            threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
        self.log("DEBUG", "accept loop ended")

    @staticmethod
    def _enable_keepalive(sock):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if sys.platform == "win32":
                sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 60_000, 10_000))
            elif sys.platform.startswith("linux"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE,  60)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT,    6)
        except Exception:
            pass

    def _handle_client(self, client_sock):
        remote = socks.socksocket()
        if self.socks_user:
            remote.set_proxy(socks.SOCKS5, self.socks_host, self.socks_port,
                             username=self.socks_user, password=self.socks_pass)
        else:
            remote.set_proxy(socks.SOCKS5, self.socks_host, self.socks_port)
        try:
            remote.settimeout(10)
            remote.connect((self.target_host, self.target_port))
            remote.settimeout(None)  # mode bloquant pour le transfert
        except Exception as e:
            self.log("ERROR", "connect failed via socks:", e)
            try:
                client_sock.close()
            except Exception:
                pass
            return
        self._enable_keepalive(client_sock)
        self._enable_keepalive(remote)
        with self._connections_lock:
            self._connections.append((client_sock, remote))
        t1 = threading.Thread(target=self._copy_loop, args=(client_sock, remote), daemon=True)
        t2 = threading.Thread(target=self._copy_loop, args=(remote, client_sock), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        for s in (client_sock, remote):
            try:
                s.close()
            except Exception:
                pass
        with self._connections_lock:
            try:
                self._connections.remove((client_sock, remote))
            except ValueError:
                pass
        self.log("INFO", "connection closed")

    def _copy_loop(self, src, dst):
        try:
            while True:
                data = src.recv(self.BUFFER_SIZE)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
