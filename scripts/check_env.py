"""수집 전에 환경을 점검한다: Python 버전, 저장 위치와 여유 공간, aws 명령, 사이트 접속.

    python3 scripts/check_env.py

사이트 접속이 '실패'로 나오면 그 네트워크에서 해당 주소가 막혀 있다는 뜻이다.
사내망이라면 네트워크 담당자에게 표의 주소를 허용해 달라고 요청한다.
"""
from __future__ import annotations

import getpass
import os
import pathlib
import shutil
import stat
import sys
import tempfile
import urllib.error

try:  # Linux·macOS에만 있다
    import grp
    import pwd
except ImportError:  # Windows
    grp = pwd = None

from common import USER_AGENT, _open, data_root_path, human, say

SITES = [
    ("PMC OA Subset (S3)", os.environ.get("BIO_PMC_BASE", "https://pmc-oa-opendata.s3.amazonaws.com") + "/README.txt"),
    ("PubMed 기준본", os.environ.get("BIO_PUBMED_BASE", "https://ftp.ncbi.nlm.nih.gov/pubmed") + "/baseline/README.txt"),
    ("openFDA 다운로드 목록", os.environ.get("BIO_OPENFDA_DOWNLOAD_JSON", "https://api.fda.gov/download.json")),
    ("ClinicalTrials.gov API", os.environ.get("BIO_CTGOV_BASE", "https://clinicaltrials.gov/api/v2") + "/stats/size"),
    ("OpenAlex 스냅샷 (S3, 선택)", os.environ.get("BIO_OPENALEX_BASE", "https://openalex.s3.amazonaws.com") + "/?list-type=2&max-keys=1"),
]


def check_site(url: str) -> tuple[bool, str]:
    """(접속 여부, 설명). 사이트가 404로 답해도 네트워크는 열려 있으므로 접속된 것으로 본다."""
    try:
        with _open(url, 20, None) as resp:
            resp.read(1024)
            return True, f"성공 (HTTP {resp.status})"
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return True, "접속됨 (HTTP 404 — 사이트는 열리지만 점검 주소가 바뀌었을 수 있다)"
        return False, f"실패 (HTTP {err.code} — 방화벽·프록시 차단이거나 사이트 오류)"
    except Exception as err:  # noqa: BLE001 - 어떤 오류든 점검표에 그대로 보여 준다
        return False, f"실패 ({type(err).__name__}: {err})"


def nearest_existing(path: pathlib.Path) -> pathlib.Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def write_test(root: pathlib.Path) -> tuple[bool, str]:
    """os.access는 ACL·네트워크 디스크에서 틀릴 수 있어 실제로 파일을 만들어 확인한다."""
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root, prefix=".write_test_"):
            pass
        return True, ""
    except OSError as err:
        return False, f"{type(err).__name__}: {err.strerror or err}"


def explain_permission(root: pathlib.Path) -> None:
    folder = nearest_existing(root)
    st = folder.stat()
    me = getpass.getuser()
    owner = group = "?"
    my_groups: list[str] = []
    if pwd and grp:
        try:
            owner = pwd.getpwuid(st.st_uid).pw_name
        except KeyError:
            owner = str(st.st_uid)
        try:
            group = grp.getgrgid(st.st_gid).gr_name
        except KeyError:
            group = str(st.st_gid)
        for gid in os.getgroups():
            try:
                my_groups.append(grp.getgrgid(gid).gr_name)
            except KeyError:
                my_groups.append(str(gid))
    say(f"       확인한 폴더: {folder} (주인 {owner}, 그룹 {group}, 권한 {stat.filemode(st.st_mode)})")
    say(f"       지금 사용자: {me} (속한 그룹: {', '.join(my_groups) or '?'})")
    say("       해결 방법 가운데 하나를 고른다.")
    say(f"       1) 폴더 주인({owner})이 ACL로 쓰기 권한을 준다(sudo 불필요):")
    say(f"            setfacl -R -m u:{me}:rwX {folder}")
    say(f"            find {folder} -type d -exec setfacl -d -m u:{me}:rwX {{}} +")
    say("       2) sudo 권한이 있는 사람이 팀 공유 그룹을 만든다(README '문제 해결'의 공유 그룹 명령).")
    say("          그룹에 추가된 사람은 다시 로그인해야 적용된다.")
    say("       3) 권한을 받기 전에는 표본만 쓸 수 있는 경로로 받는다:")
    say("            export BIO_DATA_ROOT=$HOME/bio-data-sample")


def main() -> int:
    ok = True
    say(f"User-Agent: {USER_AGENT}")
    v = sys.version_info
    py_ok = v >= (3, 9)
    ok &= py_ok
    say(f"[{'통과' if py_ok else '실패'}] Python {v.major}.{v.minor}.{v.micro} (3.9 이상 필요)")

    root = data_root_path()
    writable, why = write_test(root)
    usage = shutil.disk_usage(nearest_existing(root))
    say(f"[정보] 저장 위치: {root}  (BIO_DATA_ROOT {'설정됨' if os.environ.get('BIO_DATA_ROOT') else '미설정, 저장소 안 data/ 사용'})")
    say(f"[정보] 여유 공간: {human(usage.free)} / 전체 {human(usage.total)}")
    if usage.free < 50 * 1024**3:
        say("[주의] 여유 공간이 50GB보다 적다. 표본 수집은 되지만 전체 수집 전에 공간을 늘려라.")
    if hasattr(os, "statvfs"):
        st = os.statvfs(nearest_existing(root))
        say(f"[정보] 사용 가능한 inode(만들 수 있는 파일 수): {st.f_favail:,}")
        if st.f_favail and st.f_favail < 10_000_000:
            say("[주의] PMC 메타데이터 전체는 작은 파일 800만 개가 넘는다. inode가 모자랄 수 있다.")
    if writable:
        say("[통과] 저장 위치에 파일을 만들 수 있다")
    else:
        ok = False
        say(f"[실패] 저장 위치에 파일을 만들 수 없다 ({why})")
        explain_permission(root)

    aws = shutil.which("aws")
    say(f"[{'통과' if aws else '정보'}] aws 명령: {aws or '없음 — 표본 수집에는 필요 없고, PMC·OpenAlex 전체 수집 때 설치한다'}")

    say("")
    say("사이트 접속 점검")
    for name, url in SITES:
        reachable, result = check_site(url)
        ok &= reachable
        say(f"  - {name}: {result}\n      {url}")
    say("")
    say("모두 통과했다. README의 '빠른 시작'을 진행하라." if ok else "실패 항목을 먼저 해결하라.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
