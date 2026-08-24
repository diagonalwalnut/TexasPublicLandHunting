#!/usr/bin/env python3
"""Upload web/dist to HostGator over FTP.

HostGator extra FTP accounts use user@domain. AUTH TLS is used on the
control channel; file data uses PROT C after PASV because TLS data
channels often hang from restricted networks.

Required environment:
  FTP_USER       cPanel or FTP username (texashunt is expanded to user@domain)
  FTP_PASSWORD   that account's password

Optional:
  FTP_HOST       default 192.185.41.29
  FTP_PORT       default 21
  FTP_REMOTE_DIR default public_html
  FTP_TIMEOUT    default 25
"""

from __future__ import annotations

import os
import re
import socket
import ssl
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"
DEFAULT_HOST = "192.185.41.29"
DEFAULT_DOMAIN = "huntpubliclandintexas.com"


class HostGatorFTP:
    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: ssl.SSLSocket | socket.socket | None = None

    def connect(self, user: str, password: str) -> None:
        raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock = raw
        self._read_reply()
        code, _ = self.cmd("AUTH TLS")
        if code != 234:
            raise RuntimeError(f"AUTH TLS failed: {code}")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.sock = ctx.wrap_socket(raw, server_hostname=self.host)
        self.sock.settimeout(self.timeout)
        code, msg = self.cmd(f"USER {user}")
        if code != 331:
            raise RuntimeError(f"USER failed: {code} {msg}")
        code, _msg = self.cmd(f"PASS {password}")
        if code != 230:
            raise RuntimeError(f"PASS failed: {code}")
        self.cmd("PBSZ 0")
        self.cmd("PROT C")
        self.cmd("TYPE I")

    def cmd(self, line: str) -> tuple[int, str]:
        assert self.sock is not None
        shown = "PASS ****" if line.startswith("PASS ") else line
        print(f"  ftp> {shown}")
        self.sock.sendall((line + "\r\n").encode("utf-8"))
        return self._read_reply()

    def _read_reply(self) -> tuple[int, str]:
        assert self.sock is not None
        lines: list[str] = []
        while True:
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = self.sock.recv(1)
                if not chunk:
                    raise RuntimeError("FTP control connection closed")
                buf += chunk
            line = buf.decode("utf-8", "replace").rstrip("\r\n")
            lines.append(line)
            if len(line) > 3 and line[3:4] == " ":
                break
        text = "\n".join(lines)
        try:
            code = int(lines[-1][:3])
        except ValueError as exc:
            raise RuntimeError(f"Bad FTP reply: {text}") from exc
        return code, text

    def cwd(self, path: str) -> None:
        code, msg = self.cmd(f"CWD {path}")
        if code != 250:
            raise RuntimeError(f"CWD {path} failed: {msg}")

    def mkd(self, name: str) -> None:
        code, msg = self.cmd(f"MKD {name}")
        if code not in {257, 550, 521}:
            raise RuntimeError(f"MKD {name} failed: {msg}")

    def pwd(self) -> str:
        code, msg = self.cmd("PWD")
        if code != 257:
            return ""
        match = re.search(r'"([^"]+)"', msg)
        return match.group(1) if match else msg

    def _pasv_socket(self) -> socket.socket:
        code, msg = self.cmd("PASV")
        if code != 227:
            raise RuntimeError(f"PASV failed: {msg}")
        match = re.search(r"(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)", msg)
        if not match:
            raise RuntimeError(f"Could not parse PASV: {msg}")
        port = (int(match.group(5)) << 8) + int(match.group(6))
        return socket.create_connection((self.host, port), timeout=self.timeout)

    def storbinary(self, name: str, data: bytes) -> None:
        # Pure-FTPd (HostGator) often refuses PASV until PRET names the transfer.
        pret_code, _pret_msg = self.cmd(f"PRET STOR {name}")
        if pret_code not in {200, 250}:
            print(f"  ftp> PRET not accepted ({pret_code}); continuing with PASV")
        data_sock: socket.socket | None = self._pasv_socket()
        try:
            assert self.sock is not None
            print(f"  ftp> STOR {name}")
            self.sock.sendall(f"STOR {name}\r\n".encode("utf-8"))
            data_sock.sendall(data)
            try:
                data_sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            data_sock.close()
            data_sock = None
            code, msg = self._read_reply()
            if code in {125, 150}:
                code, msg = self._read_reply()
            if code not in {226, 250}:
                raise RuntimeError(f"STOR {name} incomplete: {msg}")
        finally:
            if data_sock is not None:
                try:
                    data_sock.close()
                except OSError:
                    pass

    def quit(self) -> None:
        if self.sock is None:
            return
        try:
            self.cmd("QUIT")
        except Exception:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        self.sock = None


def env_or(name: str, default: str) -> str:
    return (os.environ.get(name, "") or "").strip() or default


def require_env(name: str) -> str:
    value = (os.environ.get(name, "") or "").strip()
    if not value:
        print("Missing FTP_USER and FTP_PASSWORD.", file=sys.stderr)
        sys.exit(2)
    return value


def usernames(user: str) -> list[str]:
    names = [user]
    if "@" not in user:
        names.append(f"{user}@{DEFAULT_DOMAIN}")
    return names


def ensure_chdir(ftp: HostGatorFTP, name: str) -> None:
    try:
        ftp.cwd(name)
    except RuntimeError:
        ftp.mkd(name)
        ftp.cwd(name)


def reconnect(
    host: str, port: int, timeout: int, user: str, password: str, remote_parts: list[str]
) -> HostGatorFTP:
    ftp = HostGatorFTP(host, port, timeout)
    ftp.connect(user, password)
    for part in remote_parts:
        ensure_chdir(ftp, part)
    return ftp


def upload_tree(
    ftp: HostGatorFTP,
    local_dir: Path,
    *,
    host: str,
    port: int,
    timeout: int,
    user: str,
    password: str,
    remote_parts: list[str],
) -> tuple[HostGatorFTP, int]:
    count = 0
    for path in sorted(local_dir.iterdir(), key=lambda p: (p.is_dir(), p.name)):
        if path.is_dir():
            ensure_chdir(ftp, path.name)
            ftp, n = upload_tree(
                ftp,
                path,
                host=host,
                port=port,
                timeout=timeout,
                user=user,
                password=password,
                remote_parts=remote_parts + [path.name],
            )
            count += n
            ftp.cwd("..")
            continue
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                ftp.storbinary(path.name, path.read_bytes())
                count += 1
                print(f"  uploaded {path.relative_to(DIST)}")
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                print(f"  retry {attempt}/5 {path.relative_to(DIST)} ({exc})")
                try:
                    ftp.quit()
                except Exception:
                    pass
                time.sleep(2 * attempt)
                ftp = reconnect(host, port, timeout, user, password, remote_parts)
        if last_error is not None:
            raise last_error
    return ftp, count


def main() -> int:
    host = env_or("FTP_HOST", DEFAULT_HOST)
    user = require_env("FTP_USER")
    password = require_env("FTP_PASSWORD")
    port = int(os.environ.get("FTP_PORT") or "21")
    remote_dir = (os.environ.get("FTP_REMOTE_DIR") or "public_html").strip() or "public_html"
    timeout = int(os.environ.get("FTP_TIMEOUT") or "25")

    if not DIST.is_dir() or not (DIST / "index.html").is_file():
        print("web/dist/index.html missing. Run: cd web && npm run build", file=sys.stderr)
        return 1

    last_error: Exception | None = None
    ftp: HostGatorFTP | None = None
    used_user = user
    for candidate in usernames(user):
        trial = HostGatorFTP(host, port, timeout)
        try:
            print(f"Connecting {candidate}@{host}:{port}")
            trial.connect(candidate, password)
            ftp = trial
            used_user = candidate
            break
        except Exception as exc:
            last_error = exc
            print(f"Login as {candidate} failed ({exc})")
            trial.quit()
    if ftp is None:
        print(f"Could not log in to HostGator FTP: {last_error}", file=sys.stderr)
        return 1

    remote_parts = [p for p in remote_dir.replace("\\", "/").split("/") if p]
    try:
        print(f"Uploading {DIST} → {used_user}@{host}:{port}/{remote_dir}")
        for part in remote_parts:
            ensure_chdir(ftp, part)
        print(f"Remote directory: {ftp.pwd()}")
        ftp, n = upload_tree(
            ftp,
            DIST,
            host=host,
            port=port,
            timeout=timeout,
            user=used_user,
            password=password,
            remote_parts=remote_parts,
        )
        print(f"Uploaded {n} files to {remote_dir}")
        print("Site should be https://huntpubliclandintexas.com/")
    finally:
        ftp.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
