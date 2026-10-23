"""openFDA 대량 파일 받기(기본: 의약품 라벨 drug/label). 계정·키 없이 받는다.

download.json에 내려받을 수 있는 모든 파일의 주소가 있다. 파일은 https://download.open.fda.gov/ 에 있고
각각 zip으로 압축한 JSON이며, 큰 항목은 여러 조각(partition)으로 나뉜다.
openFDA는 증분 갱신이 없으므로, 갱신되면 해당 항목의 파일을 전부 다시 받는다.

    python3 scripts/openfda.py list                         # 조각 수·건수·용량 확인
    python3 scripts/openfda.py download --parts 1           # 표본: 첫 조각만
    python3 scripts/openfda.py download                     # 전체
    python3 scripts/openfda.py download --endpoint drug/drugsfda

라이선스는 CC0 1.0이다(GMDN 내용만 예외). 원문 노출 등급은 A다.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.parse
import zipfile

from common import RunLog, data_root, download, http_get, human, say, warn

DOWNLOAD_JSON = os.environ.get("BIO_OPENFDA_DOWNLOAD_JSON", "https://api.fda.gov/download.json")


def load_index() -> dict:
    raw = http_get(DOWNLOAD_JSON, timeout=120)
    keep = data_root() / "meta" / f"openfda_download_{dt.date.today():%Y%m%d}.json"
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_bytes(raw)  # 받은 시점의 목록을 남겨 두면 나중에 어떤 판을 받았는지 확인할 수 있다
    return json.loads(raw)


def endpoint_info(index: dict, endpoint: str) -> dict:
    node = index.get("results", {})
    for part in endpoint.strip("/").split("/"):
        if part not in node:
            avail = ", ".join(sorted(node)) if isinstance(node, dict) else "-"
            raise SystemExit(f"download.json에 '{endpoint}'가 없다. 이 단계에서 고를 수 있는 값: {avail}")
        node = node[part]
    if "partitions" not in node:
        raise SystemExit(f"'{endpoint}'에 partitions 항목이 없다. download.json 구조가 바뀌었는지 확인하라.")
    return node


def summarize(info: dict, endpoint: str) -> None:
    parts = info["partitions"]
    size = sum(float(p.get("size_mb") or 0) for p in parts)
    recs = sum(int(p.get("records") or 0) for p in parts)
    say(f"{endpoint}: 조각 {len(parts):,}개, 레코드 {recs:,}건(조각 합계), 압축 파일 합계 약 {size:,.1f}MB")
    say(f"  export_date {info.get('export_date', '-')}, total_records {info.get('total_records', '-')}")
    for p in parts[:3]:
        say(f"  - {p.get('display_name', '')}: {p.get('file')} ({p.get('size_mb')}MB, {p.get('records')}건)")
    if len(parts) > 3:
        say(f"  … 외 {len(parts) - 3:,}개")


def cmd_list(args) -> None:
    summarize(endpoint_info(load_index(), args.endpoint), args.endpoint)


def check_zip(path: pathlib.Path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return z.testzip() is None
    except zipfile.BadZipFile:
        return False


def cmd_download(args) -> None:
    info = endpoint_info(load_index(), args.endpoint)
    summarize(info, args.endpoint)
    parts = info["partitions"][: args.parts] if args.parts else info["partitions"]
    label = "openFDA 표본" if args.parts else "openFDA 전체"
    log = RunLog("openfda", f"{label} {args.endpoint}",
                 f"조각 {len(parts):,}/{len(info['partitions']):,}개 (export_date {info.get('export_date', '-')})",
                 DOWNLOAD_JSON)
    out_dir = data_root() / "raw" / "openfda" / args.endpoint.strip("/")
    failed, skipped = [], 0

    def get(p: dict):
        url = p["file"]
        dest = out_dir / pathlib.PurePosixPath(urllib.parse.urlsplit(url).path).name
        n = download(url, dest, timeout=600)
        if not check_zip(dest):
            dest.unlink(missing_ok=True)
            raise RuntimeError(f"zip 확인 실패(파일을 지웠다, 다시 실행하라): {dest.name}")
        return dest, n

    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(get, p): p for p in parts}
        for fut in cf.as_completed(futs):
            try:
                dest, n = fut.result()
                if n:
                    log.add_file(n, checked=True)
                    say(f"  받음 {dest.name} ({human(n)})")
                else:
                    skipped += 1
            except Exception as err:  # noqa: BLE001
                failed.append(futs[fut]["file"])
                warn(str(err))
    if skipped:
        log.record["notes"] = f"이미 있던 파일 {skipped:,}개 건너뜀"
    if failed:
        log.record["integrity"]["failed"] = len(failed)
        warn(f"받지 못한 조각 {len(failed):,}개 — 같은 명령을 다시 실행하라")
    say(f"저장 위치: {out_dir}")
    log.finish()


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("list", help="조각 수·건수·용량 확인")
    dp = sub.add_parser("download", help="조각 파일 받기")
    dp.add_argument("--parts", type=int, default=0, help="앞에서부터 받을 조각 수(0이면 전부)")
    dp.add_argument("--workers", type=int, default=2, help="동시 요청 수(기본 2)")
    for sp in (lp, dp):
        sp.add_argument("--endpoint", default="drug/label", help="download.json 안의 항목(기본 drug/label)")
    args = p.parse_args(argv)
    {"list": cmd_list, "download": cmd_download}[args.cmd](args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n중단했다. 같은 명령을 다시 실행하면 받은 파일은 건너뛰고 이어 받는다.")
