# 수집 기록

받을 때마다 스크립트가 마지막에 출력한 한 줄을 표 맨 아래에 붙여 넣고 커밋한다. 자세한 기록(시작·종료 시각, 라이선스 분포, 제외 건수, 스크립트 버전)은 `/hdd_2/bio-data/logs/`의 JSON에 있다.

- 마지막 정리: 2026-10-23 10:50(KST). 팀 페이지 '수집 기록'과 단계 체크(진행 상황)를 합쳐 정리했다.
- 용량 단위: 스크립트 출력의 `GB`와 `du -sh`의 `G`는 모두 1024 기준(GiB)이다.
- 저장 위치: `/hdd_2/bio-data` (서버 server179-96)

## 요약 (2026-10-23 기준)

| 소스 | 담당(실행) | 상태 | 파일 수 | 용량 | 저장 경로 |
|---|---|---|---|---|---|
| PubMed 기준본 | 담당 2 (hyungil) | 완료 | 1,334 | 50.5 GB | `/hdd_2/bio-data/raw/pubmed/baseline` |
| PubMed 갱신본 | 담당 2 (hyungil) | 완료 | 353 | 19.4 GB | `/hdd_2/bio-data/raw/pubmed/updatefiles` |
| openFDA 의약품 라벨 | 담당 3 (lucia) | 완료 | 14 | 1.6 GB | `/hdd_2/bio-data/raw/openfda` |
| ClinicalTrials.gov | 담당 3 (lucia) | 완료 | 608쪽(연구 607,349건) | 2.0 GB | `/hdd_2/bio-data/raw/ctgov` |
| OpenAlex 스냅샷 JSONL | 담당 1 선택 단계 (jmahn) | 완료 | 3,131 | 704 G | `/hdd_2/bio-data/raw/openalex/data/jsonl` |
| PMC 메타데이터 | 담당 1 (lucia) | 진행 중(약 43%, 10-22 저녁) | 3,516,919(10-22 측정, 전체 약 830만) | 측정 전 | `/hdd_2/bio-data/raw/pmc/metadata` |
| PMC A 등급 본문 | 담당 1 | 대기(메타데이터 완료 뒤) | - | 약 1.1 TB(추정) | `/hdd_2/bio-data/raw/pmc` |

- 완료분 합계: 파일 5,440개(ClinicalTrials.gov는 608쪽으로 계산), 약 777.5 GiB(PubMed 69.9 + openFDA 1.6 + ClinicalTrials.gov 2.0 + OpenAlex 704).
- 사람별: hyungil 69.9 GiB(PubMed), lucia 3.6 GiB(openFDA·ClinicalTrials.gov) + PMC 메타데이터 진행 중, jmahn 704 GiB(OpenAlex) + PMC 표본.
- 저장 경로는 스크립트 기본 경로다. 실제 폴더와 다르면 실제 경로로 고친다.

## 단계 진행 (팀 페이지 체크 기준)

| 담당 | 담당자 | 진행 | 체크한 단계(체크한 사람, 날짜) |
|---|---|---|---|
| 담당 1 PMC | lucia | 5/7 | 1-1 표본(jmahn, 10-19) · 1-2 AWS CLI(lucia, 10-21) · 1-3 동시 요청 수(lucia, 10-21) · 1-4 메타데이터 전체(lucia, 10-21, 시작 시점에 체크 — 현재 진행 중) · 1-7 OpenAlex(jmahn, 10-23) |
| 담당 2 PubMed | hyungil | 5/5 | 2-1 ~ 2-5 (hyungil, 10-19) |
| 담당 3 openFDA·ClinicalTrials.gov | lucia | 5/5 | 3-1 ~ 3-5 (lucia, 10-19) |

- 담당 1에서 1-5 등급 판정과 1-6 A 등급 본문 받기가 아직 진행 전이다. PMC 메타데이터 받기가 끝나면(10-24 03:00 무렵 추정) 시작한다.

## 다운로드 기록

| 날짜 | 소스 | 범위 | 새로 받은 파일 수 | 용량 | 담당 | 비고 |
|---|---|---|---|---|---|---|
| 2026-10-19 | PMC 표본 | 메타데이터 2,000건 판정 · A 등급 본문 200편 | - | - | jmahn | 팀 페이지 1-1. 스크립트 기록 줄을 붙이지 않았다. 파일 수·용량은 `/hdd_2/bio-data/logs/`의 pmc JSON에서 옮겨 적는다 |
| 2026-10-19 | openFDA 전체 drug/label | 조각 14/14개 (export_date 2026-10-16) | 13 | 1.6 GB | lucia | 이미 있던 파일 1개 건너뜀 |
| 2026-10-19 | ClinicalTrials.gov 표본 | 1,000건 1쪽 | 1 | 3.3 MB | lucia | 전체 607,349건 중 1,000건 |
| 2026-10-19 | ClinicalTrials.gov 전체 | pageSize 1,000 | 608 | 2.0 GB | lucia | 누적 607,349건 / totalCount 607,349 |
| 2026-10-19 | PubMed 표본 | 기준본 pubmed26n0001.xml.gz | 1 | 18.8 MB | hyungil | 레코드 30,000 · 초록 15,377 · 전체 추정 약 24.5GB(×1,334) |
| 2026-10-19 | PubMed 기준본 | pubmed26n0001.xml.gz~pubmed26n1334.xml.gz (1,334개) | 1,333 | 50.5 GB | hyungil | 이미 있던 파일 1개 건너뜀(2-1 표본) · MD5 실패 0 · 가이드 추정(27~36GB)보다 큼 |
| 2026-10-19 | PubMed 갱신본 | pubmed26n1335.xml.gz~pubmed26n1687.xml.gz (353개) | 353 | 19.4 GB | hyungil | MD5 실패 0 · 적용은 번호 순서대로 |
| 2026-10-21 | PMC 메타데이터(aws s3 sync) | metadata/ 전체 | 진행 중 | - | lucia | 10-21 18:00 시작 · 10-22 저녁 3,516,919개(약 43%, 초당 약 40개) · 끝나면 jmahn이 같은 sync를 한 번 더 실행해 빠진 파일을 채운다 |
| 2026-10-23 | OpenAlex 스냅샷 JSONL(aws s3 sync) | data/jsonl 전체 | 3,131 | 704G | jmahn | 로그 없음, dryrun 0으로 완료 확인 |

## 계정·키 발급 기록

키 값은 여기에 적지 않는다. 각자 보관한다.

| 날짜 | 대상 | 단계 | 담당 | 비고 |
|---|---|---|---|---|
| 2026-10-19 | NCBI API 키 | 2-5 API 키 발급 · tool·email 등록 | hyungil | 키 발급 완료 · tool·email 등록 완료(2026-10-20 NCBI 회신) |
| 2026-10-19 | OpenAlex API 키 | 2-4 무료 API 키 신청 | hyungil | 발급 완료 · 무료 키 하루 US$1 한도 |
| 2026-10-21~22 | AWS IAM 사용자 · CLI 프로필 | 연습용 | jmahn | 프로필 `aws-ajm` 설정, `aws sts get-caller-identity` 확인. 1차 다운로드는 `--no-sign-request`로 받아 키를 쓰지 않았다 |
