> 이 문서는 조사 단계에서 만든 수집 런북의 사본이다(2026-10-13 기준). 런북의 예시 명령은 `corpus/` 폴더를 쓰지만, 이 저장소의 스크립트는 `$BIO_DATA_ROOT`(기본값 `data/`)를 쓴다. 1차 다운로드는 README의 명령을 따르고, 이 문서는 소스별 배경·요청 한도·약관을 확인할 때 쓴다.

# 바이오 문서 코퍼스 수집 런북

- 작성일: 2026-10-13

이 런북은 '바이오 문서 기반 RAG 데이터 조사 보고서'에서 고른 문서 소스를 실제로 내려받는 방법을 정리한다. 모든 수집은 운영 기관이 공개한 대량 다운로드 경로와 API로만 하고, 웹페이지를 긁어 오는 스크레이핑은 하지 않는다.

## 수집 원칙

이 런북의 모든 단계는 다음 다섯 원칙을 따른다.

1. **공식 경로만 쓴다.** 운영 기관이 대량 다운로드용으로 열어 둔 저장소(S3·FTP)와 API만 쓴다. 웹페이지 화면을 자동으로 긁어 오는 스크레이핑(scraping)은 하지 않는다. PMC는 자동 수집 수단을 클라우드 서비스, OAI-PMH, E-utilities, BioC API 네 가지로 정해 두고 그 밖의 체계적 대량 수집을 금지한다. arXiv는 전체 코퍼스를 프로그램으로 내려받지 말고 S3나 Kaggle을 쓰라고 안내하고, bioRxiv는 대량 수집용 S3 저장소를 따로 둔다.
2. **요청 한도를 지킨다.** 기관마다 초당·분당 요청 수 한도가 있다. NCBI는 지침을 어기면 IP 주소를 차단할 수 있다고 안내한다. IP 단위로 막히므로 같은 회사 네트워크를 쓰는 동료의 접근까지 막힐 수 있다. 소스별 한도는 이 런북의 '요청 한도와 약관 요약표' 절에 모았다.
3. **라이선스 정보를 문서와 함께 보관한다.** 내려받은 문서마다 라이선스 값(PMC `license_code`, OpenAlex `best_oa_location.license`, Europe PMC `<license>`, bioRxiv `license`)을 함께 저장한다. 원문 노출 등급(A 원문 공개 가능, B 짧은 인용과 링크만, C 코퍼스 제외)은 이 값으로 판정한다. 원문 노출 등급은 조사 보고서에서 정한 자체 기준이며, RAG 답변 화면에 원문을 어디까지 보여 줄 수 있는지를 나타낸다.
4. **구독 콘텐츠는 받지 않는다.** 회사나 개인 구독으로 읽을 수 있는 논문(C 등급)은 서면 AI·TDM 라이선스를 받기 전까지 수집 대상이 아니다.
5. **수집할 때마다 기록을 남긴다.** 언제, 어떤 경로에서, 몇 개 파일을, 어떤 조건으로 받았는지를 '수집 기록 양식' 절의 양식에 남긴다. 논문의 데이터 가용성(Data Availability) 항목과 재현성 확인에 이 기록을 그대로 쓴다.

수치는 따로 적지 않으면 2026-10-13 기준이다. 명령과 주소 가운데 이번에 기관 안내 문서를 직접 열어 확인하지 못한 것은 '(일반 지식)'으로 표시했다. 이런 항목은 처음 실행할 때 작은 범위로 시험한 뒤 쓴다.

## 준비물

### 도구

- **AWS CLI(버전 2)**: S3 저장소에서 파일을 받는 명령줄 도구다. PMC와 OpenAlex는 AWS 계정 없이 `--no-sign-request` 옵션으로 받는다. bioRxiv와 arXiv 원문은 요청자 부담(requester pays) 저장소라서 AWS 계정과 `--request-payer requester` 옵션이 필요하다. 요청자 부담은 내려받는 사람이 전송 비용을 내는 방식이다.
- **wget 또는 curl**: HTTPS·FTP 파일과 API 응답을 받는 데 쓴다.
- **Python 3**: 메타데이터를 거르고 라이선스를 집계하는 데 쓴다. 이 런북의 예시 코드는 표준 라이브러리만 쓴다.

### 계정과 API 키

아래 표는 수집 전에 마련할 계정과 키, 그리고 각각이 필요한 이유다.

| 대상 | 필요한 것 | 필요한 이유 |
| --- | --- | --- |
| NCBI E-utilities | NCBI 계정의 API 키, tool·email 값 등록 | 키가 있으면 초당 10건, 없으면 초당 3건까지 요청할 수 있다. tool·email은 요청에 넣는 것만으로는 부족하고 NCBI에 등록해야 한다 |
| OpenAlex API | 무료 API 키 | 키 없이는 하루 US$0.10, 무료 키로는 하루 US$1까지 쓸 수 있다. 스냅샷은 키 없이 받는다 |
| Semantic Scholar Datasets | API 키(신청 필요) | 대량 데이터셋의 다운로드 링크를 받으려면 키가 필요하다 |
| AWS | AWS 계정과 결제 수단 | bioRxiv·arXiv 원문 저장소는 내려받는 쪽이 전송 비용을 낸다 |
| 공공데이터포털(data.go.kr) | 회원 가입과 활용 신청 | KCI 논문정보와 식약처 데이터는 활용 신청 뒤 파일이나 인증키를 받는다 |
| DOAJ | 전체 덤프 신청 | 전체 메타데이터 덤프는 신청한 사람에게 제공한다 |

### 저장 공간

아래 표는 이번 조사에서 확인한 용량이다. 실제 용량은 받는 범위(형식, 연도, 라이선스 필터)에 따라 달라지므로, 받기 전에 목록 명령으로 다시 확인한다.

| 대상 | 확인한 용량 | 받는 범위 |
| --- | --- | --- |
| OpenAlex 스냅샷 | 한 형식 약 750GB, 두 형식(JSONL과 Parquet) 약 1.5TB | 한 형식만 받는다(권장) |
| OpenAlex 전문 TEI XML | 약 20TB(약 4,300만 개) | 선택 사항이며 파일당 US$0.01 |
| OpenAlex 전문 PDF | 약 250TB(5,000만 개 이상) | 구조화 XML을 먼저 쓰는 원칙에 따라 받지 않는다 |
| arXiv 원문 전체 | 약 9.2TB(2025년 4월 기준), 매월 약 100GB 증가 | q-bio만 쓰므로 전체를 받지 않는다 |
| PMC OA Subset | 이번에 확인하지 못함 | PDF를 빼고 XML·TXT만 받는다. 목록 명령으로 산정한다 |
| PubMed 연간 기준본 | 이번에 확인하지 못함(파일 1,334개) | 전체를 받는다. 디렉터리 목록으로 산정한다 |

### 폴더 구조(권장)

원본, 메타데이터, 거른 목록, 기록을 폴더로 나눠 두면 다시 수집하거나 검증할 때 원본을 건드리지 않아도 된다.

```
corpus/
  raw/        # 원본 그대로(소스별 하위 폴더: pmc, pubmed, europepmc, openalex, s2, biorxiv, arxiv, ctgov, openfda, kci)
  meta/       # 소스별 메타데이터와 라이선스 집계 결과
  filtered/   # 거른 뒤의 문서 목록(ID, 라이선스, 원문 노출 등급)
  logs/       # 수집 기록(날짜별)
```

## PMC OA Subset

PMC OA Subset은 1차 코퍼스의 중심이다(8,087,649편, PMC 전체 12,503,975편). 메타데이터를 먼저 전부 받아 거른 뒤, 필요한 논문의 본문만 받는다. 2026-08-24이 있는 주에 라이선스별 옛 경로(`oa_comm/`, `oa_noncomm/`)와 FTP 논문 파일이 삭제됐으므로, 예전 자료에 나오는 그 경로는 쓰지 않는다.

### 1단계 — 저장소 구조 확인

```
aws s3 ls --no-sign-request s3://pmc-oa-opendata/
aws s3 cp --no-sign-request s3://pmc-oa-opendata/README.txt corpus/raw/pmc/
```

README에는 폴더 구조와 필드 설명이 있다. 논문 버전마다 `PMC{ID}.{버전}/` 폴더가 있고, 그 안에 `.xml`(JATS 전문), `.txt`(평문), `.json`(메타데이터)이 있다. 라이선스가 허용하면 `.pdf`와 부록 파일도 함께 있다.

### 2단계 — 메타데이터만 먼저 받기

```
aws s3 sync --no-sign-request s3://pmc-oa-opendata/metadata/ corpus/raw/pmc/metadata/
```

- `metadata/` 폴더에는 논문별 JSON 사본이 모여 있다. 논문 수만큼(800만 개 이상) 작은 파일이 있어 받는 데 시간이 걸린다.
- 매일 갱신되는 전체 파일 목록(CSV)은 `inventory-reports/pmc-oa-opendata/metadata/`에 30일 동안 보관된다. 규모와 파일 이름을 먼저 보려면 이 목록을 쓴다.
- JSON에는 `pmcid, version, pmid, doi, title, citation, is_pmc_openaccess, is_manuscript, is_historical_ocr, is_retracted, license_code, xml_url, pdf_url, media_urls, text_url` 필드가 있다.

### 3단계 — 거르기와 원문 노출 등급 판정

아래 코드는 메타데이터 JSON을 읽어 세 가지 일을 한다. 첫째, 옛 종이 논문을 스캔해 OCR로 만든 본문(`is_historical_ocr`)과 철회된 논문(`is_retracted`)을 뺀다. 둘째, `license_code` 값별 편수를 센다. 셋째, 논문마다 원문 노출 등급을 붙여 목록 파일로 저장한다. `license_code`의 실제 표기(띄어쓰기, 대소문자)는 집계 결과를 보고 확인해야 하므로, 코드는 표기를 정규화해서 비교한다.

```python
import json, pathlib, re, csv, collections

src = pathlib.Path("corpus/raw/pmc/metadata")
out = pathlib.Path("corpus/filtered/pmc_docs.csv")
out.parent.mkdir(parents=True, exist_ok=True)

A = {"cc0", "ccby", "ccbysa"}                            # 원문 공개 가능
B = {"ccbync", "ccbyncsa", "ccbyncnd", "ccbynd", "tdm"}  # 짧은 인용과 링크만

def norm(code):
    return re.sub(r"[^a-z0-9]", "", (code or "").lower())

def grade(code):
    n = norm(code)
    if n in A:
        return "A"
    if n in B:
        return "B"
    return "B_review"  # 표준 CC 코드가 아니면 사람이 확인할 때까지 B로 다룬다

counts = collections.Counter()
excluded = collections.Counter()
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["pmcid", "version", "doi", "license_code", "grade", "xml_url", "text_url"])
    for p in src.rglob("*.json"):
        m = json.loads(p.read_text())
        if m.get("is_historical_ocr"):
            excluded["historical_ocr"] += 1
            continue
        if m.get("is_retracted"):
            excluded["retracted"] += 1
            continue
        code = m.get("license_code")
        counts[code] += 1
        w.writerow([m.get("pmcid"), m.get("version"), m.get("doi"), code,
                    grade(code), m.get("xml_url"), m.get("text_url")])

print("license_code별 편수:", counts.most_common())
print("제외:", dict(excluded))
```

- 출력되는 `license_code별 편수`가 A 등급 규모를 확정하는 근거다. 조사 보고서의 '다음 할 일' 두 번째 항목이 이 집계다.
- `B_review`로 분류된 값이 나오면 그 값의 뜻을 확인해 A 집합이나 B 집합에 추가한다.
- 저자원고는 `license_code`가 `TDM`이다. 텍스트 마이닝은 허용되지만 CC 라이선스가 아니므로 B 등급이다.

### 4단계 — 본문 받기

거른 목록의 `xml_url`·`text_url` 값을 그대로 써서 받는다. 파일 이름을 직접 조합하지 않고 메타데이터에 적힌 주소를 쓰면, 저장 구조가 바뀌어도 수집 코드를 고칠 일이 줄어든다.

- 주소가 `s3://`로 시작하면 `aws s3 cp --no-sign-request <주소> <저장 위치>`로 받는다.
- 주소가 `https://`로 시작하면 `wget`이나 `curl`로 받는다.
- 많이 받을 때는 목록을 나눠 병렬로 받고, 실패한 파일은 목록에 모아 다시 받는다.
- PDF는 받지 않는다. XML과 평문이 있으면 OCR도 PDF 파싱도 필요 없기 때문이다.

### 보조 경로 — BioC-PMC

본문을 문단 단위로 미리 나눈 BioC 형식이 필요하면 BioC-PMC를 쓴다.

```
https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{PMCID}/unicode
```

XML이 필요하면 `BioC_json`을 `BioC_xml`로 바꾸고, PMCID 대신 PMID를 넣을 수도 있다. 대량 파일은 `https://ftp.ncbi.nlm.nih.gov/pub/wilbur/BioC-PMC/`에 있다. 이번 조사 환경에서는 이 디렉터리 목록을 열지 못했다([BioC-PMC 안내](https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/)).

## PubMed 연간 기준본과 일일 갱신본

PubMed는 초록과 서지 정보 4,000만 건 이상을 담은 데이터베이스다. 해마다 한 번 전체 레코드를 담은 연간 기준본(baseline)이 나오고, 그 뒤로는 새 레코드·수정·삭제를 담은 일일 갱신본(update files)이 매일 나온다. 2026년 기준본은 `pubmed26n0001`부터 `pubmed26n1334`까지 1,334개 파일이다(2026-01-30 공개).

### 받기

```
# 연간 기준본
wget -r -np -nd -A "pubmed26n*.xml.gz,pubmed26n*.xml.gz.md5" -P corpus/raw/pubmed/baseline/ https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/
# 일일 갱신본
wget -r -np -nd -A "pubmed26n*.xml.gz,pubmed26n*.xml.gz.md5" -P corpus/raw/pubmed/updatefiles/ https://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/
```

- 두 주소는 PubMed 도움말의 데이터 다운로드 항목에서 확인했다. NLM은 FTP 서버의 파일을 바이너리 모드로 받으라고 안내한다. HTTPS로 받는 wget은 파일을 변환하지 않고 그대로 저장한다.
- 갱신본 파일 번호는 기준본 다음 번호부터 이어진다(일반 지식). 그래서 같은 파일 이름 패턴으로 두 폴더를 받는다.
- 각 파일의 `.md5` 값과 받은 파일의 MD5를 비교해 손상 여부를 확인한다. md5 파일이 함께 있는지는 디렉터리 목록에서 먼저 확인한다(일반 지식).
- 이용 조건은 기준본 폴더의 README(`https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/README.txt`)에 있다. 데이터를 쓸 때 'Courtesy of the U.S. National Library of Medicine' 출처 표시가 필요하다.
- 초록에는 출판사 저작권이 남아 있을 수 있으므로 원문 노출 등급은 B로 둔다. NLM은 재배포 전에 법률 검토를 받으라고 권고한다.

### 갱신본 적용 순서

1. 기준본 1,334개 파일을 모두 적재한다.
2. 갱신본을 파일 번호 순서대로 적용한다. 같은 PMID가 다시 나오면 새 레코드로 바꾼다.
3. 갱신본의 삭제 목록(`DeleteCitation` 요소)에 오른 PMID는 지운다(일반 지식).
4. 마지막으로 적용한 파일 번호를 수집 기록에 남겨 다음 갱신 때 이어서 적용한다.

### E-utilities 이용 지침

E-utilities는 NCBI 데이터베이스(PubMed·PMC 등)를 검색하고 레코드를 받는 API다. 파일로 받기 어려운 조건 검색이나 건수 확인에 쓴다. 다음은 [E-utilities 이용 지침](https://www.ncbi.nlm.nih.gov/books/NBK25497/)에서 확인한 내용이다.

- API 키가 없으면 한 IP 주소에서 초당 3건을 넘겨 요청할 수 없다. 키가 있으면 기본 초당 10건이고, 더 높은 한도는 NCBI에 요청한다.
- 요청에 `tool`(공백 없는 소프트웨어 이름)과 `email`(최종 사용자가 아닌 개발자 본인의 주소)을 넣고, 두 값을 NCBI에 등록한다. 값을 넣기만 하는 것으로는 부족하다.
- 대량 작업은 주말이나 평일 미국 동부시간 오후 9시부터 오전 5시 사이에 한다. 한국 시간으로는 평일 오전 10시부터 오후 6시에 해당한다(미국 일광절약시간 기간 기준이며, 그 밖의 기간에는 1시간씩 늦다).
- 지침을 지키지 않으면 IP 주소가 차단될 수 있다.

PMC OA 편수를 확인하는 요청 예시는 다음과 같다. `retmax=0`은 목록 없이 건수만 받겠다는 뜻이다.

```
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term=open+access%5Bfilter%5D&retmax=0&tool={도구이름}&email={개발자이메일}&api_key={API키}
```

## Europe PMC 보강 수집

Europe PMC는 PMC와 겹치는 부분이 많다. 그래서 PMC를 기준으로 삼고, PMC에 없는 논문과 프리프린트를 보강하는 데 쓴다. 전체 48,606,996건 가운데 전문 보유 11,962,492건, OA 8,020,105건, 프리프린트 1,206,695건이다.

### 전문 XML 받기

```
https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML
```

- 응답은 JATS XML이고, 라이선스는 `<license>` 요소에 있다. 이 값으로 원문 노출 등급을 판정한다.
- PMC에서 이미 받은 PMCID는 건너뛴다.

### 검색으로 대상 고르기

```
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=SRC:PPR&format=json&resultType=lite&pageSize=1000&cursorMark=*
```

- `SRC:PPR`은 프리프린트만 고르는 조건이다. 다른 대상은 Europe PMC 검색 문법으로 조건을 바꾼다.
- 첫 요청의 `cursorMark`에는 `*`를 넣고, 응답의 `nextCursorMark` 값을 다음 요청에 넣어 이어 받는다. `pageSize` 최댓값은 1,000이다(일반 지식). Europe PMC REST 안내 페이지는 이번 조사 환경에서 robots 규칙 때문에 열지 못했으므로, 첫 실행 때 작은 `pageSize`로 시험한다.
- `resultType=lite`는 기본 서지 정보만 받는 옵션이다. 초록까지 필요하면 `core`를 쓴다(일반 지식).

### 요청 속도

- Europe PMC의 공식 요청 한도는 이번에 확인하지 못했다.
- 이번 조사에서 짧은 시간에 여섯 번 연속으로 요청하자 HTTP 429(요청 과다) 응답을 받았다. 초당 1\~2건으로 시작하고, 429 응답이 오면 기다렸다가 간격을 늘려 다시 요청한다(이 런북의 권장 규칙).
- OA 전문을 한꺼번에 받는 대량 다운로드 경로는 이번에 확인하지 못했다. 확인하기 전에는 위 API를 요청 한도 안에서 쓴다.

## OpenAlex 스냅샷·전문과 Semantic Scholar 데이터셋

OpenAlex는 약 5억 건의 학술 문헌을 색인한 공개 메타데이터다. 코퍼스에서는 DOI·인용·판본 정보를 맞추는 기준 데이터와 품질 신호(저널, 피인용 수)로 쓴다.

### OpenAlex 스냅샷(무료)

```
# 용량 확인
aws s3 ls --summarize --human-readable --no-sign-request --recursive "s3://openalex/"
# 한 형식만 받기(JSONL과 Parquet 가운데 하나)
aws s3 sync "s3://openalex/data/jsonl" "corpus/raw/openalex/data/jsonl" --no-sign-request
```

- AWS 계정 없이 받는다. 전체를 받으면 약 1.5TB이고, 형식 하나가 약 750GB다.
- `data/jsonl/`과 `data/parquet/`에 같은 내용이 형식만 달리 들어 있고, 폴더마다 `manifest.json`이 있다. works·authors 같은 개체 폴더 안은 `updated_date=2026-06-24`처럼 날짜별로 나뉜다.
- `legacy-data/`는 2026년 이전 구조로, 더는 갱신되지 않는다. 예전 자료의 경로를 그대로 쓰지 않는다.
- 무료 공개 스냅샷은 분기마다 나온다. 매일 갱신되는 스냅샷(`openalex-snapshots` 저장소)은 유료 회원 등급에만 제공된다.
- 데이터 라이선스는 CC0다(일반 지식).

### OpenAlex 전문(유료)

- PDF 5,000만 개 이상(약 250TB)과 GROBID TEI XML 약 4,300만 개(약 20TB)가 있다. 파일당 US$0.01이고, 무료 API 키의 하루 한도 US$1로는 하루 100개를 받는다.
- 받는 주소는 `https://content.openalex.org`이고, 명령줄 도구는 `pip install openalex-official`로 설치한다. 세부 사용법은 [OpenAlex 전문 안내](https://help.openalex.org/access/fulltext/)를 따른다. 전체 동기화(`s3://openalex-pdfs`)는 연간 요금제의 유료 추가 옵션이다.
- PDF와 TEI XML에는 원저작권이 그대로 남아 있다. 레코드의 `best_oa_location.license`로 원문 노출 등급을 판정하고, 본문을 보여 주는 것은 A 등급만으로 한정한다.
- TEI XML은 GROBID 결과를 고치지 않은 것이라 변환 오류가 섞일 수 있다. OpenAlex 권고에 따라 자기 DOI를 가리키는 참고문헌을 지우고, 제목·저자 같은 머리 정보는 OpenAlex 레코드와 맞춰 본다.
- 비용 예시: TEI XML 10만 개를 받으면 파일당 US$0.01이므로 약 US$1,000이다(단가 곱하기 개수로 계산한 값).

### OpenAlex API

- 2026년부터 사용량 과금이다. 키 없이 하루 US$0.10, 무료 키로 하루 US$1까지 쓸 수 있다.
- US$1은 목록·필터 조회 약 1만 회, 검색 1천 회, 전문 100건에 해당한다. 초과분은 1,000회당 목록·필터 US$0.10, 검색 US$1, 전문 US$10이다.
- 대량 분석은 API 대신 스냅샷으로 한다. API는 스냅샷 이후 바뀜 레코드를 확인하는 정도로만 쓴다.

### Semantic Scholar 데이터셋

```
# 최신 릴리스의 데이터셋 목록
curl -H "x-api-key: $S2_API_KEY" https://api.semanticscholar.org/datasets/v1/release/latest
# 데이터셋 하나의 다운로드 링크(예: s2orc_v2)
curl -H "x-api-key: $S2_API_KEY" https://api.semanticscholar.org/datasets/v1/release/latest/dataset/s2orc_v2
```

- 2026-05-21 릴리스 기준으로 papers 2억, abstracts 1억, s2orc\_v2 1,600만(OA PDF에서 파싱한 본문), citations 24억, tldrs 5,800만, SPECTER2 임베딩 1.2억 건이다.
- 첫 번째 주소는 이번에 직접 조회해 확인했다. 두 번째 주소의 형식은 Datasets API 안내를 따른 것이며, 안내 페이지 본문을 이번에 열지 못해 일반 지식으로 표시한다. 응답에 담긴 파일 주소는 유효 기간이 있는 임시 링크이므로 받은 즉시 내려받는다(일반 지식).
- 라이선스는 ODC-BY이고 임베딩은 Apache-2.0이다. 제품·서비스·재배포에 쓰면 arXiv:2301.10140을 인용해 달라고 요청한다.
- 수록된 초록·본문의 저작권 조건은 논문마다 다르므로 원문 노출 등급은 B로 둔다(조사 보고서의 판단).

## Crossref·DOAJ 메타데이터

두 소스는 본문이 아니라 메타데이터를 받는 곳이다. Crossref는 DOI와 서지 정보를, DOAJ는 OA 저널 목록과 논문 메타데이터를 확인하는 데 쓴다.

### Crossref

```
https://api.crossref.org/works?filter=from-pub-date:2025-01-01,until-pub-date:2025-12-31&rows=1000&cursor=*&mailto={연락처이메일}
```

- 규모는 185,793,821건이다. 서지 정보는 '사실'로 보아 재사용 제한이 없고, Crossref가 만든 데이터는 CC0이며, 초록은 출판사·저자의 저작권 대상이다.
- `cursor=*`로 시작해 응답의 `next-cursor` 값으로 이어 받는다. `rows` 최댓값은 1,000이다. `mailto`에 연락처를 넣으면 문제가 생겼을 때 Crossref가 연락할 수 있다(세 항목 모두 일반 지식).
- 스냅샷 파일, 우선 처리, 가용률 99.5% 보장은 유료 상품인 Metadata Plus로 제공된다.
- 이번 조사에서 짧은 시간에 여러 번 집계 조회를 하자 HTTP 429(요청 과다) 응답을 받았다. 요청 사이에 간격을 두고, 대량 수집은 OpenAlex 스냅샷으로 대신할 수 있는지 먼저 확인한다.
- 특정 저널의 라이선스 분포는 집계 기능(facet)으로 확인한다. 조사 보고서의 Cell 집계가 이 방식이다.

```
https://api.crossref.org/journals/0092-8674/works?filter=type:journal-article,from-pub-date:2015-01-01,until-pub-date:2025-12-31&rows=0&facet=license:%2A
```

### DOAJ

```
https://doaj.org/api/v4/search/articles/{검색어}?page=1&pageSize=100
```

- 저널 23,338종, 논문 13,731,417건이다. 논문 메타데이터는 CC0다. `page`·`pageSize` 매개변수 이름은 일반 지식이다.
- 전체 덤프는 일반 이용자에게 매월, 유료 메타데이터 서비스 이용자에게 매일 만들어진다. 이름·소속·국가·필요한 메타데이터 종류(저널, 논문)·용도를 적어 DOAJ에 신청한다([덤프 안내](https://doaj.org/docs/public-data-dump/)).
- 저널 목록 CSV는 [바로 내려받을 수 있다](https://doaj.org/docs/journal-csv).
- DOAJ는 OA 저널인지 확인하는 데 쓴다. 논문 본문은 DOAJ가 아니라 각 저널이나 PMC에서 받는다.

## bioRxiv·medRxiv·arXiv 프리프린트

프리프린트는 동료 심사 전 문헌이므로, 수집한 모든 문서에 `preprint=true`를 표시해 둔다. 세 서버 모두 연구 목적의 수집·분석은 허용하지만 원문을 우리 서버에서 다시 보여 주는 일은 막는다.

### bioRxiv 전문(요청자 부담 S3)

```
aws s3 ls --request-payer requester s3://biorxiv-src-monthly/
aws s3 cp --request-payer requester s3://biorxiv-src-monthly/{폴더}/{파일} corpus/raw/biorxiv/
```

- 저장소는 us-east-1 지역에 있고, 내려받는 사람이 AWS 계정으로 전송 비용을 낸다.
- 매월 MECA 파일이 올라온다. MECA는 manifest.xml, PDF, 전문 XML을 묶은 zip 파일이다. 목록을 먼저 보고 필요한 월의 폴더만 받는다. 본문은 묶음 안의 XML을 쓰고 PDF는 쓰지 않는다.
- 저자가 제출할 때 대량 TDM에 동의했지만 이 저장소는 재배포용이 아니다. 원문을 우리 서비스에서 다시 보여 주지 않고 bioRxiv 링크로 연결한다([bioRxiv TDM 안내](https://www.biorxiv.org/tdm)).

### bioRxiv·medRxiv 메타데이터 API

```
https://api.biorxiv.org/details/biorxiv/2026-09-01/2026-09-30/0
https://api.biorxiv.org/details/medrxiv/2026-09-01/2026-09-30/0
```

- 주소 형식은 `details/[서버]/[기간]/[커서]/[형식]`이다. 기간은 '시작일/종료일', '최근 N건', '최근 N일(예: 7d)' 세 가지 가운데 하나로 쓴다. 형식은 JSON, XML(OAI-PMH), HTML을 고를 수 있다.
- 한 번에 30건씩 돌려준다. 커서는 0부터 시작하는 시작 위치이므로 30씩 늘려 다음 쪽을 받는다.
- 응답에는 doi, title, authors, author\_corresponding, author\_corresponding\_institution, date, version, type, license, category, jats xml path, abstract, published, server 필드가 있다. `license`로 원문 노출 등급을 판정하고, `published`로 출판본 DOI를 확인한다.
- 출판본 연결만 필요하면 `https://api.biorxiv.org/pubs/[서버]/[기간]/[커서]` 주소를 쓴다. 이 주소는 한 번에 100건씩 돌려준다.
- medRxiv의 대량 전문 저장소는 이번에 확인하지 못했다. [medRxiv TDM 안내](https://www.medrxiv.org/tdm)에서 확인한 뒤 받는다.

### arXiv(선택)

생의학 분야에서 arXiv 비중은 작다(q-bio 2025년 3,229편). 필요할 때만 수집한다.

```
# 집합(set) 이름 확인
https://oaipmh.arxiv.org/oai?verb=ListSets
# 메타데이터 수집(arXiv 형식에 라이선스 정보가 들어 있다)
https://oaipmh.arxiv.org/oai?verb=ListRecords&metadataPrefix=arXiv&set={q-bio 집합 이름}
```

- **메타데이터**: OAI-PMH 주소는 `https://oaipmh.arxiv.org/oai`다. 형식은 `oai_dc`(단순 Dublin Core), `arXiv`(최신 판본, 분류와 라이선스 포함), `arXivRaw`(판본 이력 포함) 세 가지다. 집합 이름은 `physics:hep-th`처럼 계층으로 되어 있으므로, q-bio의 정확한 이름은 `ListSets` 응답에서 확인한다.
- **수집 방식**: 처음에는 날짜 범위 없이 전체를 받고, 그다음부터는 `from`에 마지막 수집일을 넣어 늘어난 것만 받는다. `until`은 넣지 않는다. 이어 받기 토큰(resumptionToken)은 하루가 지나면 만료된다. 메타데이터는 미국 동부시간 일요일\~목요일 밤 10시 30분쯤 갱신된다.
- **원문**: `s3://arxiv/`(요청자 부담)에 PDF와 소스 파일이 약 500MB 단위 tar 묶음으로 있다. 묶음 목록은 `pdf/arXiv_pdf_manifest.xml`과 `src/arXiv_src_manifest.xml`에 있다. 전체는 약 9.2TB(2025년 4월)이고 대략 매월 갱신된다. q-bio 논문만 필요하므로, 메타데이터로 대상을 고른 뒤 필요한 묶음만 받는 방법을 시험 수집 때 정한다.
- **요청 한도**: API(`https://export.arxiv.org/api/query`)는 3초에 1건으로 제한된다. 프로그램 수집은 export.arxiv.org에서 '초당 4건씩 몰아 보내고 1초 쉬기'를 지킨다. arXiv는 전체 코퍼스를 프로그램으로 내려받지 말라고 안내한다.
- **이용 조건**: 메타데이터는 CC0이고 상업·비상업 시스템에서 다시 쓸 수 있다. 원문은 저작권자 허락 없이 우리 서버에서 보여 줄 수 없고, 사용자를 arXiv.org로 연결해야 한다. CC BY·CC0 논문만 A 등급으로 다룬다.

## ClinicalTrials.gov·openFDA·KCI 논문정보

세 소스는 논문 코퍼스에 더하는 문서다. ClinicalTrials.gov와 openFDA는 논문이 아닌 생의학 문서(임상시험 등록 문서, 의약품 라벨)이고, KCI 논문정보는 국문 초록이다.

### ClinicalTrials.gov

```
https://clinicaltrials.gov/api/v2/studies?format=json&pageSize=1000
https://clinicaltrials.gov/api/v2/stats/size
```

- 등록 연구는 601,694건이다. 이 값은 `/stats/size` 주소로 집계했다.
- 응답의 `nextPageToken` 값을 다음 요청의 `pageToken`에 넣어 이어 받는다. `pageSize` 최댓값은 1,000이다(두 항목 모두 일반 지식이며, API 안내 페이지 본문을 이번에 열지 못했다).
- 세부 재사용 약관은 확인하지 못했고 NLM 일반 약관(출처 표시)을 따른다. 원문 노출 등급은 A로 둔다(조사 보고서 기준).

### openFDA 의약품 라벨

```
curl -s https://api.fda.gov/download.json -o corpus/meta/openfda_download.json
```

```python
import json

d = json.load(open("corpus/meta/openfda_download.json"))
parts = d["results"]["drug"]["label"]["partitions"]  # 구조는 파일을 열어 확인한다(일반 지식)
with open("corpus/meta/openfda_label_urls.txt", "w") as f:
    for p in parts:
        f.write(p["file"] + "\n")
```

```
wget -i corpus/meta/openfda_label_urls.txt -P corpus/raw/openfda/
```

- download.json에는 내려받을 수 있는 모든 파일의 주소가 들어 있다. 파일은 `https://download.open.fda.gov/`에 있고, 각각 zip으로 압축한 JSON이다. 큰 항목은 여러 조각으로 나뉘어 있다.
- 증분 갱신이 없다. 레코드가 갱신될 때마다 바뀔 수 있으므로, 갱신되면 해당 항목의 파일을 전부 다시 받는다.
- 규모는 262,895건(2026-10-09 갱신)이고 라이선스는 CC0 1.0이다. GMDN(의료기기 명칭 체계) 내용만 예외다. 원문 노출 등급은 A다.
- 건수만 확인할 때는 API(`https://api.fda.gov/drug/label.json`)를 쓴다.

### KCI 논문정보

- [KCI 개방데이터](https://www.kci.go.kr/kciportal/po/openapi/openDataView.kci?datasetBean.dtstSeqNo=1)와 [공공데이터포털 3049042](https://www.data.go.kr/biz/dcat/metadata/3049042.do)에서 받는다. 공공데이터포털에 가입하고 활용 신청을 한 뒤 파일이나 인증키를 받는다.
- 제목·저자·초록·발행연도·연구분야·피인용 수·DOI·UCI·원문 공개 여부가 들어 있고, 이용허락범위는 '제한 없음'이다. 원문 노출 등급은 A다.
- 받은 뒤 연구분야 값으로 생의학 논문을 거르고 건수를 확인한다. 이번 조사에서 건수는 확인하지 못했다.
- 본문이 필요하면 원문 공개 여부 필드를 보고 KoreaScience나 Synapse의 OA 전문을 더한다. 두 플랫폼은 대량 API가 확인되지 않았으므로, 본격 수집 전에 운영 기관에 수집 방법을 문의한다. 웹페이지를 긁어 오는 방식은 쓰지 않는다.

## 수집 후 확인

수집이 끝나면 아래 항목을 확인하고, 결과를 '수집 기록 양식' 절의 양식에 남긴다. 항목을 끝낼 때마다 체크해 두면 다른 사람도 진행 상황을 볼 수 있다.

- [ ] **건수 대조**: 받은 문서 수를 기관이 밝힌 규모와 비교한다. PMC OA는 E-utilities 집계(2026-10-13에 8,087,649편)와, PubMed 기준본은 파일 1,334개와, ClinicalTrials.gov는 `/stats/size` 값과 비교한다. 차이가 나면 실패한 파일 목록부터 확인한다.
- [ ] **라이선스 분포표**: 소스별로 라이선스 값마다 문서 수와 비율을 세어 표로 남긴다. 이 표가 A 등급 규모의 근거이고, 논문의 데이터 가용성 항목에 그대로 들어간다.
- [ ] **제외 기록**: `is_historical_ocr`와 `is_retracted`로 뺀 문서 수를 남긴다. 텍스트 레이어가 없어 뺀 PDF가 있으면 그 수도 남긴다.
- [ ] **무결성**: PubMed는 `.md5` 값으로, 나머지는 파일 크기와 압축 해제 성공 여부로 손상을 확인한다. 깨진 파일은 다시 받는다.
- [ ] **중복 제거**: DOI·PMID·PMCID로 같은 논문을 찾아 하나만 남긴다. 남길 판본의 우선순위는 PMC JATS XML, Europe PMC JATS XML, OpenAlex TEI XML 순서다(구조화 XML을 먼저 쓰는 원칙).
- [ ] **프리프린트와 출판본 연결**: bioRxiv의 `published` 필드와 `pubs` 주소, Europe PMC·Crossref의 관계 정보로 같은 연구의 두 판본을 묶는다.
- [ ] **원문 노출 등급 점검**: 등급이 비어 있는 문서가 없는지, `B_review`로 분류된 문서가 남아 있지 않은지 확인한다.
- [ ] **표본 열람**: 소스마다 문서 20건을 무작위로 골라 본문이 제대로 들어 있는지 사람이 확인한다. 20건은 이 런북의 권장값이다.
- [ ] **기록 저장**: 위 결과를 수집 기록에 남기고, 쓴 스크립트의 버전(커밋 해시 등)을 함께 적는다.

## 요청 한도와 약관 요약표

아래 표는 소스별 수집 규칙과 재배포·화면 노출 조건을 한곳에 모은 것이다. '확인하지 못함'으로 적은 항목은 첫 수집 전에 기관 안내를 다시 확인한다. 맨 아래 Springer Nature 행은 구독 콘텐츠의 조건을 비교하려고 참고로 넣었다.

| 소스 | 요청 한도와 수집 규칙 | 재배포·화면 노출 조건 | 근거 |
| --- | --- | --- | --- |
| PMC | 자동 수집은 클라우드 서비스, OAI-PMH, E-utilities, BioC API만 허용 | 논문별 라이선스(`license_code`)를 따름 | [PMC 텍스트 마이닝 안내](https://pmc.ncbi.nlm.nih.gov/tools/textmining/) |
| NCBI E-utilities | 키 없이 초당 3건, 키가 있으면 초당 10건. 대량 작업은 주말이나 평일 미국 동부시간 오후 9시\~오전 5시. tool·email 등록 필요 | 해당 없음 | [E-utilities 이용 지침](https://www.ncbi.nlm.nih.gov/books/NBK25497/) |
| PubMed 파일 | 바이너리 모드로 받기 | 'Courtesy of the U.S. National Library of Medicine' 출처 표시, 초록에는 출판사 저작권이 남을 수 있음 | [PubMed 도움말](https://pubmed.ncbi.nlm.nih.gov/help/), [NLM 다운로드 안내](https://www.nlm.nih.gov/databases/download.html) |
| Europe PMC | 공식 한도는 확인하지 못함(조사 중 HTTP 429 응답을 받음) | 논문별 `<license>` 요소를 따름 | Europe PMC REST |
| OpenAlex | 스냅샷은 무료, API는 사용량 과금(키 없이 하루 US$0.10, 무료 키로 하루 US$1), 전문은 파일당 US$0.01 | 메타데이터는 CC0(일반 지식), 전문은 원저작권 유지 | [스냅샷 안내](https://help.openalex.org/tutorials/download-the-snapshot/), [인증·가격](https://developers.openalex.org/api-reference/authentication), [전문 안내](https://help.openalex.org/access/fulltext/) |
| Semantic Scholar | 대량 다운로드에 API 키 필요 | ODC-BY, 제품·서비스·재배포 때 arXiv:2301.10140 인용 요청 | [Datasets API](https://api.semanticscholar.org/datasets/v1/release/latest) |
| Crossref | 기본 API는 무료, 스냅샷·우선 처리는 유료(Metadata Plus). 조사 중 HTTP 429 응답을 받음 | 서지 정보는 제한 없음, Crossref 생성 데이터는 CC0, 초록은 저작권 대상 | [Crossref 라이선스 안내](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/) |
| DOAJ | 전체 덤프는 신청 후 월간 제공 | 논문 메타데이터는 CC0 | [DOAJ 덤프 안내](https://doaj.org/docs/public-data-dump/) |
| bioRxiv | 전문은 요청자 부담 S3, API는 한 번에 30건 | 재배포·재호스팅 금지, bioRxiv 링크 필수 | [bioRxiv TDM](https://www.biorxiv.org/tdm), [bioRxiv API](https://api.biorxiv.org/) |
| medRxiv | 메타데이터 API는 bioRxiv와 같은 주소 체계, 전문 저장소는 확인하지 못함 | 세부 조건은 확인하지 못함 | [medRxiv TDM](https://www.medrxiv.org/tdm) |
| arXiv | API는 3초에 1건, 프로그램 수집은 초당 4건씩 몰아 보내고 1초 쉬기, 전체 코퍼스를 프로그램으로 받지 않기, 원문 S3는 요청자 부담 | 저작권자 허락 없이 원문 제공 불가, arXiv.org로 연결, 메타데이터는 CC0 | [API 약관](https://info.arxiv.org/help/api/tou.html), [대량 데이터 안내](https://info.arxiv.org/help/bulk_data.html) |
| ClinicalTrials.gov | 한도는 확인하지 못함 | NLM 일반 약관(출처 표시), 세부 재사용 약관은 확인하지 못함 | — |
| openFDA | 한도는 확인하지 못함, 증분 갱신 없음 | CC0 1.0(GMDN 내용만 예외) | [다운로드 안내](https://open.fda.gov/apis/downloads/), [라이선스](https://open.fda.gov/license/) |
| KCI(공공데이터포털) | 활용 신청 후 인증키 발급 | 이용허락범위 '제한 없음' | [공공데이터포털 3049042](https://www.data.go.kr/biz/dcat/metadata/3049042.do) |
| AI Hub | 신원 확인과 이용 목적 제출 | AI 학습용으로만 사용, 승인 없는 제3자 제공 금지, 국외 이용·반출은 별도 합의, 성과물에 NIA 사업 결과 명시 | [AI Hub 이용정책](https://aihub.or.kr/intrcn/guid/usagepolicy.do) |
| Springer Nature(참고, 구독 콘텐츠) | 직접 다운로드는 초당 1건, TDM API는 분당 150건(기관 구독을 거친 경우) | 비상업 연구에 한정, 제3자 접근이 없는 내부 서버에 TDM 기간 동안만 보관 | [Springer Nature TDM 정책](https://www.springernature.com/gp/researchers/text-and-data-mining) |

## 수집 기록 양식

수집할 때마다 아래 항목을 한 건씩 남긴다. 표로 관리해도 되고, 같은 항목을 가진 JSON 파일로 `corpus/logs/`에 남겨도 된다. 이 기록은 논문의 데이터 가용성 항목, 재현성 확인, 라이선스 점검에 그대로 쓴다.

| 항목 | 적는 내용 | 쓰는 곳 |
| --- | --- | --- |
| 수집 번호 | 날짜와 순번(예: 2026-10-20-01) | 기록끼리 구분 |
| 소스 | 기관과 데이터 이름(예: PMC OA Subset 메타데이터) | 데이터 가용성 항목 |
| 경로 | 받은 주소나 실행한 명령 | 재현성 확인 |
| 수집 시각 | 시작과 종료 시각, 시간대 포함 | 데이터 가용성 항목(수집일) |
| 범위 조건 | 기간, 형식, 필터 조건 | 재현성 확인 |
| 파일 수와 용량 | 받은 파일 수와 전체 바이트 | 건수 대조 |
| 무결성 확인 | 체크섬 비교 결과와 실패한 파일 수 | 재수집 판단 |
| 라이선스 분포 | 라이선스 값별 문서 수(또는 집계 파일 경로) | 라이선스 점검, 논문 부록 |
| 제외 건수 | 제외 이유별 문서 수(옛 스캔·OCR 본문, 철회, 텍스트 레이어 없음) | 논문 방법 절 |
| 스크립트 버전 | 사용한 코드의 버전(커밋 해시 등) | 재현성 확인 |
| 담당자 | 수집한 사람 | 문의 창구 |
| 비고 | 오류, 재시도, 특이 사항(예: HTTP 429 응답으로 대기 후 재개) | 다음 수집 계획 |

같은 항목을 JSON으로 남길 때의 틀은 다음과 같다. 값은 비워 둔 자리다.

```json
{
  "run_id": "",
  "source": "",
  "path": "",
  "started_at": "",
  "finished_at": "",
  "scope": "",
  "file_count": 0,
  "total_bytes": 0,
  "integrity": {"checked": 0, "failed": 0},
  "license_distribution": {},
  "excluded": {"historical_ocr": 0, "retracted": 0, "no_text_layer": 0},
  "script_version": "",
  "operator": "",
  "notes": ""
}
```

## 출처

이 런북의 명령과 조건은 아래 페이지를 직접 열어 확인했다. 소스 선정 근거와 라이선스 판단은 '바이오 문서 기반 RAG 데이터 조사 보고서'에 있다.

- **PMC**: [PMC Cloud Service 안내](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/) · [저장소 README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt) · [PMC 텍스트 마이닝 안내](https://pmc.ncbi.nlm.nih.gov/tools/textmining/) · [BioC-PMC 안내](https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/)
- **PubMed·NCBI**: [PubMed 도움말(데이터 다운로드)](https://pubmed.ncbi.nlm.nih.gov/help/) · [2026 기준본 공지](https://www.nlm.nih.gov/pubs/techbull/jf26/jf26_PubMed_2026_BaselineRelease.html) · [NLM 다운로드 안내](https://www.nlm.nih.gov/databases/download.html) · [E-utilities 이용 지침](https://www.ncbi.nlm.nih.gov/books/NBK25497/)
- **Europe PMC**: [REST API 안내](https://europepmc.org/RestfulWebService)(이번에는 robots 규칙으로 열지 못했고, 주소 형식은 1차 조사 때 확인했다)
- **OpenAlex**: [스냅샷 다운로드 안내](https://help.openalex.org/tutorials/download-the-snapshot/) · [인증·가격](https://developers.openalex.org/api-reference/authentication) · [전문 안내](https://help.openalex.org/access/fulltext/)
- **Semantic Scholar**: [Datasets API 최신 릴리스](https://api.semanticscholar.org/datasets/v1/release/latest)
- **Crossref·DOAJ**: [Crossref 메타데이터 라이선스](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/) · [DOAJ 공개 데이터 덤프](https://doaj.org/docs/public-data-dump/) · [DOAJ 저널 CSV](https://doaj.org/docs/journal-csv)
- **bioRxiv·medRxiv**: [bioRxiv TDM](https://www.biorxiv.org/tdm) · [bioRxiv API 안내](https://api.biorxiv.org/) · [medRxiv TDM](https://www.medrxiv.org/tdm)
- **arXiv**: [대량 데이터 안내](https://info.arxiv.org/help/bulk_data.html) · [S3 대량 데이터](https://info.arxiv.org/help/bulk_data_s3.html) · [OAI-PMH 안내](https://info.arxiv.org/help/oa/index.html) · [API 약관](https://info.arxiv.org/help/api/tou.html)
- **ClinicalTrials.gov·openFDA**: [ClinicalTrials.gov API v2](https://clinicaltrials.gov/api/v2/studies) · [openFDA 다운로드 안내](https://open.fda.gov/apis/downloads/) · [openFDA 라이선스](https://open.fda.gov/license/)
- **국내**: [KCI 개방데이터](https://www.kci.go.kr/kciportal/po/openapi/openDataView.kci?datasetBean.dtstSeqNo=1) · [공공데이터포털 3049042](https://www.data.go.kr/biz/dcat/metadata/3049042.do) · [AI Hub 이용정책](https://aihub.or.kr/intrcn/guid/usagepolicy.do)
- **참고(구독 콘텐츠)**: [Springer Nature TDM 정책](https://www.springernature.com/gp/researchers/text-and-data-mining)
