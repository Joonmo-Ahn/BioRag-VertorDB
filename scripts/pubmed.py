"""PubMed 연간 기준본(baseline)과 일일 갱신본(update files) 받기. 파일마다 MD5를 확인한다.

2026년 기준본은 pubmed26n0001~pubmed26n1334 파일 1,334개다(2026-01-30 공개). 갱신본은 pubmed26n1335부터다.
NLM 안내: 기준본을 전부 적재한 뒤에 갱신본을 번호 순서대로 적용한다.

    python3 scripts/pubmed.py sample                       # 기준본 첫 파일 1개 + 레코드 수 세기
    python3 scripts/pubmed.py baseline                     # 기준본 1,334개 전부(이어받기 가능)
    python3 scripts/pubmed.py baseline --first 1 --last 100
    python3 scripts/pubmed.py updates                      # 일일 갱신본 전부

PubMed 초록에는 출판사 저작권이 남아 있을 수 있어 원문 노출 등급은 B다.
데이터를 쓸 때 'Courtesy of the U.S. National Library of Medicine' 출처 표시가 필요하다.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
import os
import re
import sys
import xml.etree.ElementTree as ET

from common import NotFound, RunLog, data_root, download, http_get, human, say, warn

BASE = os.environ.get("BIO_PUBMED_BASE", "https://ftp.ncbi.nlm.nih.gov/pubmed").rstrip("/")
MD5_RE = re.compile(rb"\b([0-9a-fA-F]{32})\b")


def fetch_md5(url: str) -> str | None:
    try:
        m = MD5_RE.search(http_get(url + ".md5"))
        return m.group(1).decode().lower() if m else None
    except NotFound:
        warn(f"MD5 파일이 없다: {url}.md5 (확인 없이 받는다)")
        return None


def get_file(folder: str, name: str, log: RunLog) -> tuple[str, int, bool]:
    url = f"{BASE}/{folder}/{name}"
    md5 = fetch_md5(url)
    dest = data_root() / "raw" / "pubmed" / folder / name
    n = download(url, dest, md5=md5, timeout=300)
    return name, n, bool(md5)


def run_files(folder: str, names: list[str], workers: int, log: RunLog) -> None:
    failed, skipped = [], 0
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(get_file, folder, n, log): n for n in names}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            name = futs[fut]
            try:
                _, n, checked = fut.result()
                if n:
                    log.add_file(n, checked=checked)
                else:
                    skipped += 1
            except Exception as err:  # noqa: BLE001
                failed.append(name)
                warn(f"실패 {name}: {err}")
            if i % 20 == 0 or i == len(names):
                say(f"  {i:,}/{len(names):,} (새로 받음 {log.record['file_count']:,}, 건너뜀 {skipped:,}, 실패 {len(failed):,})")
    if skipped:
        log.record["notes"] = f"이미 있던 파일 {skipped:,}개 건너뜀"
    if failed:
        log.record["integrity"]["failed"] = len(failed)
        warn(f"받지 못한 파일 {len(failed):,}개: {', '.join(failed[:10])}{' …' if len(failed) > 10 else ''}"
             " — 같은 명령을 다시 실행하면 이어 받는다")


def count_records(path) -> tuple[int, int]:
    """기준본 파일 하나의 레코드 수와 초록이 있는 레코드 수를 센다."""
    total = with_abs = 0
    with gzip.open(path, "rb") as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if el.tag == "PubmedArticle":
                total += 1
                if el.find(".//Abstract") is not None:
                    with_abs += 1
                el.clear()
    return total, with_abs


def cmd_sample(args) -> None:
    name = f"{args.prefix}{1:04d}.xml.gz"
    log = RunLog("pubmed-sample", "PubMed 표본", f"기준본 {name}", f"{BASE}/baseline/")
    say(f"기준본 첫 파일 받기: {name}")
    run_files("baseline", [name], 1, log)
    path = data_root() / "raw" / "pubmed" / "baseline" / name
    total, with_abs = count_records(path)
    say(f"레코드 {total:,}건, 그중 초록이 있는 레코드 {with_abs:,}건 ({human(path.stat().st_size)})")
    log.finish(f"레코드 {total:,} · 초록 {with_abs:,}")


def cmd_baseline(args) -> None:
    names = [f"{args.prefix}{i:04d}.xml.gz" for i in range(args.first, args.last + 1)]
    log = RunLog("pubmed-baseline", "PubMed 기준본", f"{names[0]}~{names[-1]} ({len(names):,}개)", f"{BASE}/baseline/")
    say(f"기준본 {len(names):,}개 받기 (동시 {args.workers}개)")
    run_files("baseline", names, args.workers, log)
    log.finish()


def cmd_updates(args) -> None:
    html = http_get(f"{BASE}/updatefiles/").decode("utf-8", "replace")
    names = sorted(set(re.findall(rf'href="({re.escape(args.prefix)}\d{{4}}\.xml\.gz)"', html)))
    if not names:
        raise SystemExit("갱신본 목록에서 파일을 찾지 못했다. --prefix 값(예: pubmed26n)을 확인하라.")
    log = RunLog("pubmed-updates", "PubMed 갱신본", f"{names[0]}~{names[-1]} ({len(names):,}개)", f"{BASE}/updatefiles/")
    say(f"갱신본 {len(names):,}개 받기 (동시 {args.workers}개). 적용은 파일 번호 순서대로 한다.")
    run_files("updatefiles", names, args.workers, log)
    log.finish()


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prefix", default="pubmed26n", help="파일 이름 앞부분(기본 pubmed26n — 2027년 기준본은 pubmed27n)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample", help="기준본 첫 파일 1개를 받아 레코드 수를 센다")
    b = sub.add_parser("baseline", help="기준본 받기")
    b.add_argument("--first", type=int, default=1)
    b.add_argument("--last", type=int, default=1334)
    u = sub.add_parser("updates", help="일일 갱신본 받기")
    for sp in (b, u):
        sp.add_argument("--workers", type=int, default=3, help="동시 요청 수(기본 3)")
    args = p.parse_args(argv)
    {"sample": cmd_sample, "baseline": cmd_baseline, "updates": cmd_updates}[args.cmd](args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n중단했다. 같은 명령을 다시 실행하면 받은 파일은 건너뛰고 이어 받는다.")
