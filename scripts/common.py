"""모든 수집 스크립트가 함께 쓰는 도구.

- 데이터 저장 위치: 환경변수 BIO_DATA_ROOT, 없으면 저장소 안의 data/
- HTTP 받기: 일시 오류와 HTTP 429(요청 과다)는 기다렸다가 다시 시도하고, 계속되면 멈춘다
- 파일 받기: .part 임시 파일로 받은 뒤 이름을 바꾼다. 이미 받은 파일은 건너뛴다
- MD5 확인: 16진수와 base64 표기를 모두 받는다
- 수집 기록: data/logs/ 에 JSON을 남기고, RUNS.md 에 붙일 한 줄을 출력한다

외부 패키지 없이 Python 3.9 이상 표준 라이브러리만 쓴다.
"""
from __future__ import annotations

import base64
import datetime as dt
import getpass
import hashlib
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
_contact = os.environ.get("BIO_CONTACT_EMAIL", "").strip()
USER_AGENT = "bio-rag-data/0.1 (research corpus download" + (f"; {_contact}" if _contact else "") + ")"


class NotFound(Exception):
    """HTTP 404. 다시 시도해도 결과가 같으므로 바로 알린다."""


class ChecksumError(Exception):
    """받은 파일의 MD5가 기관이 밝힌 값과 다르다."""


def say(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"[주의] {msg}", file=sys.stderr, flush=True)


def data_root_path() -> pathlib.Path:
    """BIO_DATA_ROOT(없으면 저장소 안 data/)의 절대 경로. 폴더는 만들지 않는다."""
    root = os.environ.get("BIO_DATA_ROOT", "").strip() or str(REPO / "data")
    return pathlib.Path(root).expanduser().resolve()


def data_root() -> pathlib.Path:
    path = data_root_path()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise SystemExit(f"저장 위치를 만들 권한이 없다: {path}\n"
                         "python3 scripts/check_env.py 를 실행하면 원인과 해결 명령을 보여 준다.")
    return path


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:,.1f} {unit}" if unit != "B" else f"{int(n):,} B"
        n /= 1024
    return f"{n:,.1f} TB"


def _retry_after(err: urllib.error.HTTPError) -> float | None:
    value = err.headers.get("Retry-After") if err.headers else None
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _open(url: str, timeout: float, headers: dict | None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def http_get(url: str, *, timeout: float = 60, retries: int = 5, headers: dict | None = None) -> bytes:
    """URL 내용을 받아 bytes로 돌려준다. 429·5xx·연결 오류는 간격을 늘리며 다시 시도한다."""
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            with _open(url, timeout, headers) as resp:
                return resp.read()
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise NotFound(url) from err
            if err.code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = _retry_after(err) or delay
                warn(f"HTTP {err.code}: {wait:.0f}초 기다린 뒤 다시 시도한다({attempt}/{retries}) {url}")
                time.sleep(wait)
                delay = min(delay * 2, 300)
                continue
            if err.code == 429:
                raise SystemExit(f"HTTP 429(요청 과다)가 계속된다. 몇 시간 뒤 다시 실행하라. 우회하지 않는다: {url}")
            raise
        except (urllib.error.URLError, socket.timeout, ConnectionError) as err:
            if attempt < retries:
                warn(f"연결 오류({err}): {delay:.0f}초 뒤 다시 시도한다({attempt}/{retries})")
                time.sleep(delay)
                delay = min(delay * 2, 300)
                continue
            raise
    raise RuntimeError("unreachable")


def file_md5(path: pathlib.Path) -> hashlib._Hash:  # type: ignore[name-defined]
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h


def md5_matches(path: pathlib.Path, expected: str) -> bool:
    h = file_md5(path)
    exp = expected.strip()
    return exp.lower() == h.hexdigest() or exp == base64.b64encode(h.digest()).decode()


def download(url: str, dest: pathlib.Path, *, md5: str | None = None,
             timeout: float = 120, retries: int = 5) -> int:
    """url을 dest로 받는다. 이미 있으면(MD5가 주어지면 일치할 때만) 건너뛰고 0을 돌려준다.

    돌려주는 값은 새로 받은 바이트 수다.
    """
    if dest.exists() and (md5 is None or md5_matches(dest, md5)):
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            with _open(url, timeout, None) as resp, open(tmp, "wb") as out:
                shutil.copyfileobj(resp, out, 1 << 20)
            if md5 and not md5_matches(tmp, md5):
                raise ChecksumError(f"MD5 불일치: {url}")
            tmp.replace(dest)
            return dest.stat().st_size
        except urllib.error.HTTPError as err:
            if err.code == 404:
                tmp.unlink(missing_ok=True)
                raise NotFound(url) from err
            retryable = err.code in (429, 500, 502, 503, 504)
            if not retryable or attempt == retries:
                tmp.unlink(missing_ok=True)
                if err.code == 429:
                    raise SystemExit(f"HTTP 429(요청 과다)가 계속된다. 몇 시간 뒤 다시 실행하라. 우회하지 않는다: {url}")
                raise
            wait = _retry_after(err) or delay
        except (urllib.error.URLError, socket.timeout, ConnectionError, ChecksumError) as err:
            if attempt == retries:
                tmp.unlink(missing_ok=True)
                raise
            warn(f"{err}: 다시 시도한다({attempt}/{retries})")
            wait = delay
        time.sleep(wait)
        delay = min(delay * 2, 300)
    raise RuntimeError("unreachable")


def git_rev() -> str:
    try:
        out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def operator() -> str:
    return os.environ.get("BIO_OPERATOR", "").strip() or getpass.getuser()


class RunLog:
    """런북 '수집 기록 양식'과 같은 항목으로 data/logs/ 에 JSON을 남긴다."""

    def __init__(self, source: str, label: str, scope: str, path: str):
        now = dt.datetime.now().astimezone()
        self.label = label
        self.record = {
            "run_id": now.strftime("%Y-%m-%dT%H%M%S") + "-" + source,
            "source": label,
            "path": path,
            "started_at": now.isoformat(timespec="seconds"),
            "finished_at": "",
            "scope": scope,
            "file_count": 0,
            "total_bytes": 0,
            "integrity": {"checked": 0, "failed": 0},
            "license_distribution": {},
            "excluded": {},
            "script_version": git_rev(),
            "operator": operator(),
            "notes": "",
        }

    def add_file(self, nbytes: int, checked: bool = False) -> None:
        self.record["file_count"] += 1
        self.record["total_bytes"] += nbytes
        if checked:
            self.record["integrity"]["checked"] += 1

    def finish(self, summary: str = "") -> pathlib.Path:
        now = dt.datetime.now().astimezone()
        self.record["finished_at"] = now.isoformat(timespec="seconds")
        logs = data_root() / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        out = logs / f"{self.record['run_id']}.json"
        seq = 2
        while out.exists():  # 같은 초에 두 번 실행해도 기록을 덮어쓰지 않는다
            out = logs / f"{self.record['run_id']}-{seq}.json"
            seq += 1
        out.write_text(json.dumps(self.record, ensure_ascii=False, indent=2), encoding="utf-8")
        r = self.record
        notes = [x for x in (summary, r["notes"]) if x]
        if r["integrity"]["failed"]:
            notes.insert(0, f"실패 {r['integrity']['failed']:,}개(다시 실행 필요)")
        say("")
        say(f"수집 기록을 저장했다: {out}")
        say("RUNS.md 표에 아래 한 줄을 붙여 넣고 커밋하라.")
        say(f"| {now:%Y-%m-%d} | {self.label} | {r['scope']} | {r['file_count']:,} | "
            f"{human(r['total_bytes'])} | {r['operator']} | {' · '.join(notes) or '-'} |")
        return out
