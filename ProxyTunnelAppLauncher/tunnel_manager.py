# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import os
import random
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .forwarder import SimpleForwarder
from .models import CommandEntry, PortRangeExhaustedError, ProxyProfile, resolve_text


class SentinelProcess:
    """Émule l'interface subprocess.Popen via un fichier sentinelle.
    Utilisé sur macOS/Linux pour les commandes lancées dans un émulateur de terminal,
    dont le processus parent retourne immédiatement sans attendre la fin de la session."""

    def __init__(self, sentinel_path: str):
        self._sentinel = sentinel_path
        self.returncode: Optional[int] = None
        self.stdout = None
        self.stderr = None

    def poll(self) -> Optional[int]:
        if self.returncode is not None:
            return self.returncode
        if not os.path.exists(self._sentinel):
            self.returncode = 0
            return 0
        return None

    def wait(self, timeout=None) -> int:
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            if self.poll() is not None:
                return self.returncode
            if deadline and time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(cmd='', timeout=timeout)
            time.sleep(0.5)

    def terminate(self):
        try:
            os.unlink(self._sentinel)
        except FileNotFoundError:
            pass
        self.returncode = -1

    def kill(self):
        self.terminate()


@dataclass
class TunnelSession:
    command_name: str
    local_port: int
    forwarder: SimpleForwarder
    process: Optional[subprocess.Popen] = None
    keep_alive: bool = False
    killed: bool = False
    _processes: list = field(default_factory=list)


class TunnelManager(QObject):
    session_ended = pyqtSignal(str)   # command_name

    def __init__(self, log_fn: Optional[Callable] = None,
                 port_range: tuple = (20000, 30000), parent=None):
        super().__init__(parent)
        self._port_range = port_range
        self._sessions: Dict[str, TunnelSession] = {}
        self._lock = threading.Lock()
        self.log_fn: Callable = log_fn or (lambda level, msg: None)
        self.global_vars: Dict[str, str] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def set_port_range(self, range_min: int, range_max: int):
        self._port_range = (range_min, range_max)

    def is_running(self, command_name: str) -> bool:
        return command_name in self._sessions

    def get_local_port(self, command_name: str) -> Optional[int]:
        s = self._sessions.get(command_name)
        return s.local_port if s else None

    def launch(self, cmd: CommandEntry, proxy: ProxyProfile) -> TunnelSession:
        if cmd.name in self._sessions and cmd.keep_alive:
            return self._relaunch_process(cmd)
        with self._lock:
            if cmd.name in self._sessions:
                raise RuntimeError(self.tr("Commande '{}' déjà en cours d'exécution").format(cmd.name))
            port = self._allocate_port()

        f = SimpleForwarder(
            listen_host="127.0.0.1",
            listen_port=port,
            target_host=resolve_text(cmd.target_host, self.global_vars),
            target_port=cmd.target_port,
            socks_host=resolve_text(proxy.host, self.global_vars),
            socks_port=proxy.port,
            socks_user=proxy.user,
            socks_pass=proxy.password,
            logger=lambda level, msg: self.log_fn(level, f"[Tunnel:{cmd.name}] {msg}"),
        )

        f.start()  # raises OSError if proxy unreachable or port busy

        session = TunnelSession(command_name=cmd.name, local_port=port, forwarder=f,
                                keep_alive=cmd.keep_alive)

        with self._lock:
            self._sessions[cmd.name] = session

        resolved_cmd = resolve_text(cmd.command, self.global_vars, "127.0.0.1", str(port))
        self.log_fn("INFO", f"[{cmd.name}] tunnel 127.0.0.1:{port} → "
                            f"{cmd.target_host}:{cmd.target_port}")

        try:
            args = shlex.split(resolved_cmd)
            if cmd.console:
                if sys.platform == "win32":
                    proc = subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
                elif sys.platform == "darwin":
                    proc = self._launch_console_macos(resolved_cmd)
                else:
                    proc = self._launch_console_linux(resolved_cmd)
            else:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
        except Exception as e:
            self._teardown(cmd.name)
            raise RuntimeError(self.tr("Impossible de lancer la commande : {}").format(e)) from e

        session.process = proc
        session._processes.append(proc)
        exe = os.path.splitext(os.path.basename(args[0]))[0] if args else cmd.name
        self.log_fn("INFO", f"[{cmd.name}] lancé: {resolved_cmd}")

        if not cmd.console:
            for pipe, level in ((proc.stdout, "INFO"), (proc.stderr, "WARNING")):
                threading.Thread(
                    target=self._pipe_reader,
                    args=(pipe, cmd.name, level, exe),
                    daemon=True,
                ).start()

        threading.Thread(
            target=self._process_watcher,
            args=(session, proc),
            daemon=True,
        ).start()

        return session

    def kill(self, command_name: str):
        session = self._sessions.get(command_name)
        if not session:
            return
        session.killed = True
        with self._lock:
            alive = [p for p in session._processes if p.poll() is None]
        if alive:
            for proc in alive:
                try:
                    proc.terminate()
                except Exception as e:
                    self.log_fn("ERROR", f"[{command_name}] erreur kill: {e}")
            for proc in alive:
                threading.Thread(
                    target=self._kill_after_timeout,
                    args=(proc, command_name),
                    daemon=True,
                ).start()
        else:
            self._teardown(command_name)
            self.session_ended.emit(command_name)

    def stop_all(self):
        for name in list(self._sessions.keys()):
            self.kill(name)

    # ── Internal ──────────────────────────────────────────────────────────

    def _relaunch_process(self, cmd: CommandEntry) -> TunnelSession:
        """Lance une nouvelle instance de la commande sur le tunnel keep_alive actif.
        Les instances précédentes continuent de tourner."""
        session = self._sessions[cmd.name]
        resolved_cmd = resolve_text(cmd.command, self.global_vars,
                                    "127.0.0.1", str(session.local_port))
        try:
            args = shlex.split(resolved_cmd)
            if cmd.console:
                if sys.platform == "win32":
                    proc = subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
                elif sys.platform == "darwin":
                    proc = self._launch_console_macos(resolved_cmd)
                else:
                    proc = self._launch_console_linux(resolved_cmd)
            else:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
        except Exception as e:
            raise RuntimeError(self.tr("Impossible de lancer la commande : {}").format(e)) from e
        session.process = proc
        session._processes.append(proc)
        exe = os.path.splitext(os.path.basename(args[0]))[0] if args else cmd.name
        self.log_fn("INFO", f"[{cmd.name}] relancé: {resolved_cmd}")
        if not cmd.console:
            for pipe, level in ((proc.stdout, "INFO"), (proc.stderr, "WARNING")):
                threading.Thread(
                    target=self._pipe_reader,
                    args=(pipe, cmd.name, level, exe),
                    daemon=True,
                ).start()
        threading.Thread(
            target=self._process_watcher,
            args=(session, proc),
            daemon=True,
        ).start()
        return session

    def _allocate_port(self) -> int:
        rmin, rmax = self._port_range
        used = {s.local_port for s in self._sessions.values()}
        candidates = [p for p in range(rmin, rmax + 1) if p not in used]
        random.shuffle(candidates)
        for port in candidates:
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if sys.platform == "win32":
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                probe.bind(("127.0.0.1", port))
                probe.close()
                return port
            except OSError:
                continue
        raise PortRangeExhaustedError(
            self.tr("Plage de ports épuisée ({}–{}). "
                    "Libérez des ressources ou élargissez la plage dans les paramètres."
                    ).format(rmin, rmax)
        )

    def _make_sentinel_script(self, resolved_cmd: str):
        """Crée un script shell temporaire avec fichier sentinelle pour macOS/Linux."""
        fd, sentinel = tempfile.mkstemp(prefix='proxytunnel_', suffix='.sentinel')
        os.close(fd)
        fd, script_path = tempfile.mkstemp(prefix='proxytunnel_', suffix='.sh')
        os.close(fd)
        with open(script_path, 'w') as f:
            f.write(
                f'#!/bin/bash\n'
                f'cleanup() {{ rm -f "{sentinel}" "{script_path}"; }}\n'
                f'trap cleanup EXIT\n'
                f'{resolved_cmd}\n'
            )
        os.chmod(script_path, 0o700)
        return sentinel, script_path

    def _launch_console_macos(self, resolved_cmd: str) -> SentinelProcess:
        sentinel, script_path = self._make_sentinel_script(resolved_cmd)
        applescript = (
            'tell application "Terminal"\n'
            f'  do script "bash {script_path}"\n'
            '  activate\n'
            'end tell'
        )
        subprocess.Popen(['osascript', '-e', applescript])
        return SentinelProcess(sentinel)

    def _launch_console_linux(self, resolved_cmd: str) -> SentinelProcess:
        sentinel, script_path = self._make_sentinel_script(resolved_cmd)
        terminals = [
            ['xterm', '-e', 'bash', script_path],
            ['x-terminal-emulator', '-e', 'bash', script_path],
            ['konsole', '-e', 'bash', script_path],
            ['gnome-terminal', '--', 'bash', script_path],
            ['xfce4-terminal', '-e', f'bash {script_path}'],
        ]
        for term_args in terminals:
            if shutil.which(term_args[0]):
                subprocess.Popen(term_args)
                return SentinelProcess(sentinel)
        raise RuntimeError(
            self.tr("Aucun émulateur de terminal trouvé. "
                    "Installez xterm, gnome-terminal, konsole ou xfce4-terminal.")
        )

    def _teardown(self, command_name: str):
        with self._lock:
            session = self._sessions.pop(command_name, None)
        if session:
            session.forwarder.stop()
            self.log_fn("INFO", f"[{command_name}] tunnel fermé")

    def _process_watcher(self, session: TunnelSession, proc):
        proc.wait()
        code = proc.returncode
        lvl = "INFO" if code == 0 else "WARNING"
        self.log_fn(lvl, f"[{session.command_name}] processus terminé (code {code})")
        with self._lock:
            try:
                session._processes.remove(proc)
            except ValueError:
                pass
            remaining = len(session._processes)
        if session.keep_alive and not session.killed:
            self.log_fn("INFO", f"[{session.command_name}] tunnel maintenu (keep_alive)")
            return
        if remaining > 0:
            return
        self._teardown(session.command_name)
        self.session_ended.emit(session.command_name)

    def _pipe_reader(self, pipe, command_name: str, level: str, exe: str):
        try:
            for line in pipe:
                line = line.rstrip("\n\r")
                if line:
                    self.log_fn(level, f"[{command_name}][{exe}] {line}")
        except Exception:
            pass

    def _kill_after_timeout(self, proc: subprocess.Popen, command_name: str):
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                self.log_fn("WARNING", f"[{command_name}] tué de force (SIGKILL)")
            except Exception:
                pass
