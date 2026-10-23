"""PMC OA Subset 수집: 메타데이터 받기, 원문 노출 등급 판정, 본문(JATS XML·평문) 받기.

PMC 저장소(s3://pmc-oa-opendata, 가입 불필요)는 논문 판본마다 PMC{ID}.{판본}/ 폴더에
.xml(JATS 전문)·.txt(평문)·.json(메타데이터)을 두고, metadata/ 폴더에 JSON 사본을 모아 둔다.
라이선스별 폴더(oa_comm 등)는 2026-08-24 주에 없어졌으므로 JSON의 license_code로 등급을 나눈다.

    python3 scripts/pmc.py sample                  # 표본: 메타데이터 2,000건 판정, A 등급 본문 200편 받기
    python3 scripts/pmc.py grade                   # aws s3 sync로 받은 메타데이터 전체를 판정
    python3 scripts/pmc.py fetch --grade A         # 판정 목록의 본문 받기(이어받기 가능)

등급: A = CC0·CC BY·CC BY-SA(원문 공개 가능), B = 비상업·변경금지·저자원고(TDM),
B_review = 표준 CC 코드가 아니어서 사람이 확인할 값.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import csv
import json
import os
import pathlib
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

from common import NotFound, RunLog, data_root, download, http_get, human, say, warn

BASE = os.environ.get("BIO_PMC_BASE", "https://pmc-oa-opendata.s3.amazonaws.com").rstrip("/")
BUCKET = "pmc-oa-opendata"
S3NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

A_CODES = {"cc0", "ccby", "ccbysa"}
B_CODES = {"ccbync", "ccbyncsa", "ccbyncnd", "ccbynd", "tdm"}

CSV_FIELDS = ["stem", "pmcid", "version", "pmid", "doi", "license_code", "grade",
              "is_manuscript", "is_retracted", "xml_url", "text_url"]


def norm(code: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (code or "").lower())


def grade(code: str | None) -> str:
    n = norm(code)
    if n in A_CODES:
        return "A"
    if n in B_CODES:
        return "B"
    return "B_review"


def meta_dir() -> pathlib.Path:
    return data_root() / "raw" / "pmc" / "metadata"


def list_keys(prefix: str, start_after: str | None, limit: int):
    """S3 목록(ListObjectsV2)을 HTTPS로 읽어 (키, 크기)를 차례로 돌려준다."""
    token, n = None, 0
    while True:
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            q["continuation-token"] = token
        elif start_after:
            q["start-after"] = start_after
        root = ET.fromstring(http_get(f"{BASE}/?{urllib.parse.urlencode(q)}"))
        for c in root.findall(f"{S3NS}Contents"):
            yield c.findtext(f"{S3NS}Key"), int(c.findtext(f"{S3NS}Size") or 0)
            n += 1
            if limit and n >= limit:
                return
        if root.findtext(f"{S3NS}IsTruncated") != "true":
            return
        token = root.findtext(f"{S3NS}NextContinuationToken")


def to_https(url: str | None, stem: str, ext: str) -> tuple[str, str | None]:
    """메타데이터의 S3 주소(s3:// 또는 https://, md5 매개변수 포함)를 받을 수 있는 HTTPS 주소와 MD5로 바꾼다.

    주소가 비어 있으면 README의 이름 규칙(PMC{ID}.{판본}/PMC{ID}.{판본}.{확장자})으로 만든다.
    """
    if not url:
        return f"{BASE}/{stem}/{stem}.{ext}", None
    u = urllib.parse.urlsplit(url)
    # base64 MD5에는 '+'가 들어갈 수 있다. parse_qs가 '+'를 공백으로 바꾸지 않게 미리 %2B로 바꾼다.
    md5 = urllib.parse.parse_qs(u.query.replace("+", "%2B")).get("md5", [None])[0]
    if u.scheme == "s3":
        host_base = BASE if u.netloc == BUCKET else f"https://{u.netloc}.s3.amazonaws.com"
        return f"{host_base}{u.path}", md5
    if u.netloc in (f"{BUCKET}.s3.amazonaws.com", f"{BUCKET}.s3.us-east-1.amazonaws.com"):
        return f"{BASE}{u.path}", md5
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, "", "")), md5


def row_from_meta(stem: str, m: dict) -> dict:
    return {
        "stem": stem,
        "pmcid": m.get("pmcid"),
        "version": m.get("version"),
        "pmid": m.get("pmid"),
        "doi": m.get("doi"),
        "license_code": m.get("license_code"),
        "grade": grade(m.get("license_code")),
        "is_manuscript": bool(m.get("is_manuscript")),
        "is_retracted": bool(m.get("is_retracted")),
        "xml_url": m.get("xml_url") or "",
        "text_url": m.get("text_url") or "",
    }


def grade_records(records, out_csv: pathlib.Path, keep_retracted: bool, collect: bool = False):
    """(stem, 메타 dict)를 받아 판정 CSV를 쓴다.

    돌려주는 값은 (행 목록, 라이선스 분포, 등급 분포, 제외 건수)다. 행 목록은 collect=True일 때만
    모은다. 전체(800만 건 이상)를 판정할 때 메모리에 쌓지 않기 위해서다.
    """
    licenses, grades, excluded = collections.Counter(), collections.Counter(), collections.Counter()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for i, (stem, m) in enumerate(records, 1):
            if i % 100_000 == 0:
                say(f"  판정 {i:,}건 진행")
            if m.get("is_historical_ocr"):
                excluded["historical_ocr"] += 1
                continue
            if m.get("is_retracted") and not keep_retracted:
                excluded["retracted"] += 1
                continue
            row = row_from_meta(stem, m)
            licenses[str(m.get("license_code"))] += 1
            grades[row["grade"]] += 1
            w.writerow(row)
            if collect:
                rows.append(row)
    return rows, licenses, grades, excluded


def print_distribution(licenses, grades, excluded) -> None:
    total = sum(grades.values())
    say("\n원문 노출 등급 분포")
    for g in ("A", "B", "B_review"):
        n = grades.get(g, 0)
        say(f"  {g:9s} {n:>10,}편 ({(n / total * 100 if total else 0):5.1f}%)")
    say("license_code 값별 편수(많은 순)")
    for code, n in licenses.most_common():
        say(f"  {code!s:20s} {n:>10,}")
    say(f"제외: 옛 스캔·OCR 본문 {excluded.get('historical_ocr', 0):,}편, 철회 {excluded.get('retracted', 0):,}편")
    if grades.get("B_review"):
        warn("B_review 값이 있다. 값의 뜻을 확인해 scripts/pmc.py 의 A_CODES 또는 B_CODES에 더하라.")


def save_distribution(licenses, grades, excluded, name: str) -> pathlib.Path:
    out = data_root() / "meta" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"grades": grades, "license_code": licenses, "excluded": excluded},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def iter_jobs(rows, want_grade: str, formats: list[str], limit: int):
    """판정 행에서 (주소, 저장 위치, MD5) 작업을 하나씩 만든다. 목록 전체를 메모리에 올리지 않는다."""
    n = 0
    root = data_root() / "raw" / "pmc" / "articles"
    for r in rows:
        if want_grade != "all" and r["grade"] != want_grade:
            continue
        n += 1
        if limit and n > limit:
            return
        for ext in formats:
            url, md5 = to_https(r["xml_url"] if ext == "xml" else r["text_url"], r["stem"], ext)
            yield url, root / r["stem"] / f"{r['stem']}.{ext}", md5


def fetch_bodies(rows, want_grade: str, formats: list[str], limit: int, workers: int, log: RunLog) -> None:
    say(f"\n본문 받기: {want_grade} 등급, 형식 {','.join(formats)}, 동시 요청 {workers}개"
        + (f", 최대 {limit:,}편" if limit else ", 목록 전체"))
    failed: list[str] = []
    stats = {"done": 0, "skipped": 0}
    inflight: dict = {}
    base_files, base_bytes = log.record["file_count"], log.record["total_bytes"]

    def drain(keep: int) -> None:
        while len(inflight) > keep:
            finished, _ = cf.wait(list(inflight), return_when=cf.FIRST_COMPLETED)
            for fut in finished:
                url, dest, md5 = inflight.pop(fut)
                try:
                    n = fut.result()
                    if n:
                        log.add_file(n, checked=bool(md5))
                    else:
                        stats["skipped"] += 1
                except NotFound:
                    failed.append(url)
                except Exception as err:  # noqa: BLE001 - 실패한 파일은 목록에 모으고 계속 받는다
                    failed.append(url)
                    warn(f"실패 {url}: {err}")
                stats["done"] += 1
                if stats["done"] % 1000 == 0:
                    say(f"  파일 {stats['done']:,}개 처리 (새로 받음 {log.record['file_count'] - base_files:,}, "
                        f"건너뜀 {stats['skipped']:,}, 실패 {len(failed):,})")

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for url, dest, md5 in iter_jobs(rows, want_grade, formats, limit):
            inflight[pool.submit(download, url, dest, md5=md5)] = (url, dest, md5)
            if len(inflight) >= workers * 4:
                drain(workers * 2)
        drain(0)

    say(f"본문 받기 끝: 파일 {stats['done']:,}개 처리, 새로 받음 {log.record['file_count'] - base_files:,}개"
        f"({human(log.record['total_bytes'] - base_bytes)}), 이미 있어 건너뜀 {stats['skipped']:,}개, "
        f"실패 {len(failed):,}개")
    if stats["skipped"]:
        log.record["notes"] = f"이미 있던 파일 {stats['skipped']:,}개 건너뜀"
    if failed:
        fail_list = data_root() / "logs" / f"{log.record['run_id']}_failed.txt"
        fail_list.parent.mkdir(parents=True, exist_ok=True)
        fail_list.write_text("\n".join(failed) + "\n", encoding="utf-8")
        log.record["integrity"]["failed"] = len(failed)
        warn(f"받지 못한 파일 {len(failed):,}개, 목록: {fail_list} (같은 명령을 다시 실행하면 이어 받는다)")


def cmd_sample(args) -> None:
    log = RunLog("pmc-sample", "PMC 표본", f"메타 {args.n_meta:,} · {args.grade} 등급 본문 {args.n_docs:,}",
                 f"{BASE}/metadata/")
    say(f"1/3 메타데이터 목록 읽기 (최대 {args.n_meta:,}건, 시작 위치: {args.start_after or '처음'})")
    keys = [k for k, _ in list_keys("metadata/", args.start_after, args.n_meta) if k.endswith(".json")]
    say(f"2/3 메타데이터 JSON {len(keys):,}개 받기")
    md = meta_dir()

    def get_meta(key: str):
        dest = md / pathlib.Path(key).name
        try:
            n = download(f"{BASE}/{key}", dest)
            return dest.stem, json.loads(dest.read_text(encoding="utf-8")), n
        except Exception as err:  # noqa: BLE001 - 한 건이 실패해도 표본 전체를 멈추지 않는다
            warn(f"메타데이터 실패 {key}: {err}")
            return None

    records = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for got in pool.map(get_meta, keys):
            if got:
                stem, m, n = got
                records.append((stem, m))
                if n:
                    log.add_file(n)
    say(f"  메타데이터 {len(records):,}개 확보, 저장 위치: {md}")
    out_csv = data_root() / "filtered" / "pmc_docs_sample.csv"
    rows, licenses, grades, excluded = grade_records(records, out_csv, args.keep_retracted, collect=True)
    print_distribution(licenses, grades, excluded)
    log.record["license_distribution"] = dict(licenses)
    log.record["excluded"] = dict(excluded)
    say(f"판정 목록: {out_csv}")
    say(f"3/3 {args.grade} 등급 본문 받기")
    fetch_bodies(rows, args.grade, args.formats.split(","), args.n_docs, args.workers, log)
    a = grades.get("A", 0)
    log.finish(f"A 등급 {a:,}/{sum(grades.values()):,}편")


def iter_meta_files(folder: pathlib.Path):
    for p in folder.rglob("*.json"):
        try:
            yield p.stem, json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            warn(f"읽기 실패 {p}: {err}")


def cmd_grade(args) -> None:
    folder = pathlib.Path(args.meta_dir) if args.meta_dir else meta_dir()
    if not folder.exists():
        raise SystemExit(f"메타데이터 폴더가 없다: {folder}\nREADME의 'PMC 전체'에 있는 aws s3 sync 명령을 먼저 실행하라.")
    log = RunLog("pmc-grade", "PMC 등급 판정", "받아 둔 메타데이터 전체", str(folder))
    out_csv = data_root() / "filtered" / "pmc_docs.csv"
    say(f"메타데이터 판정: {folder}")
    rows, licenses, grades, excluded = grade_records(iter_meta_files(folder), out_csv, args.keep_retracted)
    print_distribution(licenses, grades, excluded)
    dist = save_distribution(licenses, grades, excluded, "pmc_license_distribution.json")
    log.record["license_distribution"] = dict(licenses)
    log.record["excluded"] = dict(excluded)
    log.record["file_count"] = sum(grades.values())  # 판정해 목록에 올린 논문 판본 수
    say(f"판정 목록: {out_csv}\n분포 파일: {dist}")
    log.finish(f"A 등급 {grades.get('A', 0):,}/{sum(grades.values()):,}편")


def cmd_fetch(args) -> None:
    csv_path = pathlib.Path(args.csv) if args.csv else data_root() / "filtered" / "pmc_docs.csv"
    if not csv_path.exists():
        raise SystemExit(f"판정 목록이 없다: {csv_path}\n먼저 'python3 scripts/pmc.py grade'를 실행하라.")
    scope = f"{args.grade} 등급 {'전체' if not args.limit else f'{args.limit:,}편'} · {args.formats}"
    log = RunLog("pmc-fetch", "PMC 본문", scope, str(csv_path))
    with csv_path.open(encoding="utf-8") as fh:
        fetch_bodies(csv.DictReader(fh), args.grade, args.formats.split(","), args.limit, args.workers, log)
    log.finish()


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="표본: 메타데이터 일부를 받아 판정하고 본문 일부를 받는다")
    s.add_argument("--n-meta", type=int, default=2000, help="받을 메타데이터 수(기본 2,000)")
    s.add_argument("--n-docs", type=int, default=200, help="본문을 받을 논문 수(기본 200)")
    s.add_argument("--start-after", default=None,
                   help="목록 시작 위치, 예: metadata/PMC9 (기본은 처음부터 — 키 이름순이라 PMC1로 시작하는 번호가 먼저 나온다)")

    g = sub.add_parser("grade", help="받아 둔 메타데이터 전체를 판정해 data/filtered/pmc_docs.csv 를 만든다")
    g.add_argument("--meta-dir", default=None, help="메타데이터 폴더(기본 $BIO_DATA_ROOT/raw/pmc/metadata)")

    f = sub.add_parser("fetch", help="판정 목록의 본문을 받는다(이미 받은 파일은 건너뛴다)")
    f.add_argument("--csv", default=None, help="판정 목록(기본 $BIO_DATA_ROOT/filtered/pmc_docs.csv)")
    f.add_argument("--limit", type=int, default=0, help="받을 논문 수 상한(0이면 전부)")

    for sp in (s, g):
        sp.add_argument("--keep-retracted", action="store_true",
                        help="철회 논문을 빼지 않고 is_retracted 열로 표시만 한다(철회 인지 실험용)")
    for sp in (s, f):
        sp.add_argument("--grade", default="A", choices=["A", "B", "B_review", "all"], help="받을 등급(기본 A)")
        sp.add_argument("--formats", default="xml,txt", help="받을 형식(기본 xml,txt)")
    for sp in (s, f):
        sp.add_argument("--workers", type=int, default=16, help="동시 요청 수(기본 16)")

    args = p.parse_args(argv)
    {"sample": cmd_sample, "grade": cmd_grade, "fetch": cmd_fetch}[args.cmd](args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n중단했다. 같은 명령을 다시 실행하면 받은 파일은 건너뛰고 이어 받는다.")
