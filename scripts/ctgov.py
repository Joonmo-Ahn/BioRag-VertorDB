"""ClinicalTrials.gov 등록 연구 받기(API v2, 계정·키 불필요).

한 번에 최대 1,000건씩 받고, 응답의 nextPageToken을 다음 요청의 pageToken에 넣어 이어 받는다.
요청 간격은 기본 1.5초다(분당 약 40건). 외부 정리 문서에는 'IP당 분당 약 50건' 한도가 적혀 있으나
공식 안내 페이지 본문은 이번에 확인하지 못했으므로 그보다 느리게 보낸다.

    python3 scripts/ctgov.py size          # 등록 연구 수 확인(/stats/size)
    python3 scripts/ctgov.py sample        # 표본: 1,000건(1쪽)
    python3 scripts/ctgov.py all           # 전체(중단돼도 같은 명령으로 이어 받는다)
    python3 scripts/ctgov.py all --restart # 처음부터 다시

쪽마다 data/raw/ctgov/studies_p00001.json.gz 형식으로 저장한다(JSON 응답을 gzip으로 압축).
원문 노출 등급은 A로 둔다(NLM 일반 약관, 출처 표시).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
import urllib.parse

from common import RunLog, data_root, http_get, human, say, warn

BASE = os.environ.get("BIO_CTGOV_BASE", "https://clinicaltrials.gov/api/v2").rstrip("/")


def out_dir():
    d = data_root() / "raw" / "ctgov"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_page(page_size: int, token: str | None, count_total: bool) -> dict:
    q = {"format": "json", "pageSize": str(page_size)}
    if count_total:
        q["countTotal"] = "true"
    if token:
        q["pageToken"] = token
    return json.loads(http_get(f"{BASE}/studies?{urllib.parse.urlencode(q)}", timeout=180))


def save_page(page_no: int, data: dict) -> int:
    path = out_dir() / f"studies_p{page_no:05d}.json.gz"
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    with gzip.open(path, "wb") as fh:
        fh.write(raw)
    return path.stat().st_size


def cmd_size(args) -> None:
    say(json.dumps(json.loads(http_get(f"{BASE}/stats/size")), ensure_ascii=False, indent=2))


def cmd_sample(args) -> None:
    log = RunLog("ctgov-sample", "ClinicalTrials.gov 표본", f"{args.page_size:,}건 1쪽", f"{BASE}/studies")
    data = get_page(args.page_size, None, True)
    n = save_page(1, data)
    log.add_file(n)
    studies = len(data.get("studies", []))
    say(f"연구 {studies:,}건 저장 ({human(n)}), 전체 {data.get('totalCount', '-')}건")
    log.finish(f"전체 {data.get('totalCount', '-')}건 중 {studies:,}건")


def cmd_all(args) -> None:
    state_path = out_dir() / "_state.json"
    state = {"page": 0, "token": None, "total": None, "saved": 0}
    if state_path.exists() and not args.restart:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("done"):
            say("이미 끝난 수집이다. 다시 받으려면 --restart 를 붙인다.")
            return
        say(f"이어 받기: {state['page'] + 1}쪽부터 (지금까지 {state['saved']:,}건)")
    log = RunLog("ctgov-all", "ClinicalTrials.gov 전체", f"pageSize {args.page_size:,}", f"{BASE}/studies")
    while True:
        try:
            data = get_page(args.page_size, state["token"], state["page"] == 0)
        except Exception as err:  # noqa: BLE001
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            if state["token"]:
                warn("이어 받기 토큰이 만료됐을 수 있다. 계속 실패하면 --restart 로 처음부터 받는다.")
            raise SystemExit(f"요청 실패: {err}")
        state["page"] += 1
        if state["page"] == 1:
            state["total"] = data.get("totalCount")
        n = save_page(state["page"], data)
        log.add_file(n)
        state["saved"] += len(data.get("studies", []))
        state["token"] = data.get("nextPageToken")
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        if state["page"] % 10 == 0 or not state["token"]:
            say(f"  {state['page']:,}쪽, 누적 {state['saved']:,}건 / 전체 {state['total'] or '-'}건")
        if not state["token"]:
            break
        time.sleep(args.sleep)
    state["done"] = True
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    total = state.get("total")
    if total and state["saved"] != total:
        warn(f"받은 건수 {state['saved']:,}와 첫 쪽의 totalCount {total:,}가 다르다. 수집 중 등록·삭제가 있었을 수 있다.")
    log.finish(f"누적 {state['saved']:,}건 / totalCount {total or '-'}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("size", help="등록 연구 수 확인")
    s = sub.add_parser("sample", help="1쪽(기본 1,000건)만 받는다")
    a = sub.add_parser("all", help="전체를 받는다")
    a.add_argument("--sleep", type=float, default=1.5, help="요청 간격 초(기본 1.5)")
    a.add_argument("--restart", action="store_true", help="이어 받지 않고 처음부터")
    for sp in (s, a):
        sp.add_argument("--page-size", type=int, default=1000, help="쪽당 건수(최대 1,000)")
    args = p.parse_args(argv)
    {"size": cmd_size, "sample": cmd_sample, "all": cmd_all}[args.cmd](args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n중단했다. 'python3 scripts/ctgov.py all'을 다시 실행하면 이어 받는다.")
