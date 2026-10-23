# AWS CLI 연습 — 팀 IAM 자격 증명으로 시작하기

1차 다운로드에서 AWS CLI가 하는 일은 PMC·OpenAlex 공개 저장소에서 파일을 받는 것이다. 이 일에는 자격 증명이 필요 없다(`--no-sign-request`). 팀 계정 자격 증명은 내가 누구로 로그인했는지 확인할 때, 2차 수집의 요청자 부담 저장소(bioRxiv·arXiv)를 받을 때, 팀 S3 버킷으로 데이터를 공유할 때 쓴다.

이 문서는 설치, 자격 증명 설정, 공개 PMC 저장소로 연습, 실제 메타데이터 수집 순서로 진행한다. 연습은 논문 한 편 단위로 해서 받는 양이 작다.

## 0. 먼저 알아 둘 개념

- **자격 증명(credential)**: AWS가 요청한 사람이 누구인지 확인하는 정보다. 두 가지 형태가 있다.
  - **액세스 키**: Access key ID와 Secret access key 한 쌍이다. 만료되지 않는 장기 키이며, IAM 사용자의 Access key ID는 `AKIA`로 시작한다.
  - **IAM Identity Center(SSO)**: 포털 주소로 브라우저에서 로그인하면 몇 시간짜리 임시 자격 증명을 받는다. AWS는 사람이 쓰는 자격 증명으로 이 방식을 권장한다.
- **프로필(profile)**: 자격 증명 묶음에 붙이는 이름이다. 이 문서는 `bio-team`으로 쓴다. 명령에 `--profile bio-team`을 붙이거나 `export AWS_PROFILE=bio-team`으로 정해 둔다.
- **서명(signing)**: 자격 증명으로 요청에 서명하는 일이다. 공개 저장소는 `--no-sign-request`를 붙여 서명 없이 받는다.

## 1. 관리자에게 받을 것

| 팀 계정 방식 | 받는 것 | 설정 명령 |
|---|---|---|
| IAM Identity Center(SSO), AWS 권장 방식 | SSO 시작 URL(`https://…awsapps.com/start` 형태), SSO 리전, 계정과 역할 이름 | `aws configure sso` |
| IAM 사용자 액세스 키 | Access key ID, Secret access key, 기본 리전 | `aws configure --profile bio-team` |

- 웹 콘솔 로그인 정보(계정 ID나 별칭, 사용자 이름, 초기 비밀번호)를 받았다면 첫 로그인 때 비밀번호를 바꾸고 MFA(다중 인증)를 켠다.
- 1차 다운로드에는 권한이 필요 없다. 2차에 bioRxiv·arXiv 원문을 받을 때 해당 버킷의 읽기 권한(`s3:ListBucket`, `s3:GetObject`)만 요청한다. 필요한 권한만 받는 것이 AWS의 최소 권한 원칙이다.

## 2. 설치와 확인

[설치 안내](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)의 명령이다. 버전 2를 설치한다.

```bash
# macOS
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Linux x86_64 (sudo가 없으면 마지막 줄을 ./aws/install -i ~/.local/aws-cli -b ~/.local/bin 으로 바꾼다)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# 확인: aws-cli/2. 으로 시작하면 된다
aws --version
```

Windows는 설치 안내 페이지의 MSI 설치 파일을 쓴다.

## 3. 자격 증명 설정

받은 방식에 맞는 쪽 하나만 한다.

### SSO를 받은 경우

```bash
aws configure sso
# SSO session name (Recommended): bio-team
# SSO start URL [None]: (관리자가 준 주소)
# SSO region [None]: (관리자가 준 리전)
# SSO registration scopes [None]: sso:account:access   ← 그대로 Enter
#   (브라우저가 열리면 로그인하고 허용한다. 계정·역할이 하나뿐이면 자동으로 고른다)
# Default client Region [None]: (팀 리소스 리전, 관리자에게 확인. 서울은 ap-northeast-2)
# CLI default output format [None]: json
# Profile name [...]: bio-team

aws sso login --profile bio-team   # 세션이 만료되면 이 명령으로 다시 로그인한다
```

### 액세스 키를 받은 경우

```bash
aws configure --profile bio-team
# AWS Access Key ID [None]: (관리자가 준 AKIA… 값)
# AWS Secret Access Key [None]: (관리자가 준 값)
# Default region name [None]: (팀 리소스 리전, 관리자에게 확인. 서울은 ap-northeast-2)
# Default output format [None]: json
```

- 키는 홈 폴더의 `.aws/credentials`에, 나머지 설정은 `.aws/config`에 저장된다(Windows는 `%UserProfile%\.aws\`).
- 매번 `--profile`을 붙이기 싫으면 `export AWS_PROFILE=bio-team`을 실행해 둔다. Windows는 `setx AWS_PROFILE bio-team`이다.

### 설정 확인

```bash
aws sts get-caller-identity --profile bio-team
```

- `Account`(팀 계정 번호 12자리), `UserId`, `Arn`(예: `arn:aws:iam::123456789012:user/이름`)이 나오면 설정이 맞다.
- 이 명령은 권한이 하나도 없어도 동작한다. 그래서 자격 증명이 맞는지만 확인하는 첫 명령으로 쓴다.

## 4. 공개 PMC 저장소로 연습하기(자격 증명 없이)

PMC 저장소(`s3://pmc-oa-opendata`)는 us-east-1 리전에 있고 누구나 읽을 수 있다. 아래 명령에는 모두 `--no-sign-request --region us-east-1`을 붙인다.

> 저장소 맨 위(`s3://pmc-oa-opendata/`)에는 논문 폴더가 800만 개 넘게 있다. 맨 위를 `ls`하거나 `--recursive`로 훑지 않는다. 화면이 몇 시간 동안 넘어간다.

1. **안내문 받기**: 저장소 구조와 필드 설명이 들어 있다.

    ```bash
    mkdir -p practice
    aws s3 cp --no-sign-request --region us-east-1 s3://pmc-oa-opendata/README.txt ./practice/
    ```

2. **메타데이터 몇 개 목록 보기**: 주소 끝을 `PMC1000000`처럼 일부만 적으면 그 글자로 시작하는 파일만 나온다.

    ```bash
    aws s3 ls --no-sign-request --region us-east-1 s3://pmc-oa-opendata/metadata/PMC1000000
    ```

    `PMC10000000.1.json`처럼 논문 번호와 판본 번호로 된 파일 이름이 몇 줄 나온다.

3. **메타데이터 하나를 화면에 열기**: 받을 위치에 `-`를 쓰면 파일로 저장하지 않고 화면에 출력한다.

    ```bash
    aws s3 cp --no-sign-request --region us-east-1 s3://pmc-oa-opendata/metadata/PMC10000000.1.json - | python3 -m json.tool
    ```

    `license_code`(라이선스), `is_retracted`(철회 여부), `xml_url`(본문 주소)을 찾아본다. 이 값으로 원문 노출 등급을 나눈다.

4. **논문 한 편 폴더의 파일 수와 용량 보기**

    ```bash
    aws s3 ls --no-sign-request --region us-east-1 --recursive --human-readable --summarize s3://pmc-oa-opendata/PMC10000000.1/
    ```

    마지막 두 줄의 `Total Objects`(파일 수)와 `Total Size`(용량)를 본다.

5. **미리 보기 후 받기**: `--dryrun`은 실제로 받지 않고 받을 목록만 보여 준다. `--exclude "*"` 뒤에 `--include`를 붙이면 지정한 형식만 받는다. 폴더에 PDF나 그림이 있어도 XML·평문·JSON만 받는다.

    ```bash
    aws s3 sync --no-sign-request --region us-east-1 --dryrun \
      --exclude "*" --include "*.xml" --include "*.txt" --include "*.json" \
      s3://pmc-oa-opendata/PMC10000000.1/ ./practice/PMC10000000.1/
    ```

    `(dryrun) download: …` 줄을 확인한 뒤 `--dryrun`만 빼고 다시 실행한다.

6. **같은 sync를 한 번 더 실행하기**: 이미 받은 파일은 건너뛰므로 아무것도 받지 않는다. 큰 수집이 끊겼을 때 같은 명령을 다시 실행하면 되는 이유다.

## 5. 실제 작업: PMC 메타데이터 전체 받기

메타데이터는 논문 판본마다 JSON이 하나씩, 800만 개가 넘는다. 내용은 약 11GB(표본 29개 평균 1.33KB로 환산한 추정값)이지만, 작은 파일 하나가 디스크 블록 하나(보통 4KB)를 차지해 디스크 사용량은 약 33GB가 된다. 시작하기 전에 `python3 scripts/check_env.py`로 여유 공간과 inode 수를 확인한다.

1. **동시 요청 수를 늘린다.** 기본값은 10이다. 작은 파일이 많을 때 늘리면 빨라진다.

    ```bash
    aws configure set default.s3.max_concurrent_requests 32
    # AWS_PROFILE을 정해 두었다면 그 프로필에 설정한다
    aws configure set s3.max_concurrent_requests 32 --profile bio-team
    ```

2. **tmux 안에서 실행한다.** 접속이 끊겨도 작업이 계속된다.

    ```bash
    tmux new -s pmc                  # 새 작업 창
    mkdir -p "${BIO_DATA_ROOT:-data}/logs"
    aws s3 sync --no-sign-request --region us-east-1 --only-show-errors \
      s3://pmc-oa-opendata/metadata/ "${BIO_DATA_ROOT:-data}/raw/pmc/metadata/" \
      2>&1 | tee -a "${BIO_DATA_ROOT:-data}/logs/pmc_metadata_sync.log"
    # Ctrl-b 를 누른 뒤 d 를 누르면 창에서 빠져나온다. 다시 들어갈 때는 tmux attach -t pmc
    ```

    - `--only-show-errors`는 파일마다 찍히는 진행 줄을 숨기고 오류만 보여 준다.
    - 끊기면 같은 명령을 다시 실행한다. 받은 파일은 건너뛴다.

3. **진행 상황을 확인한다.** 다른 창에서 받은 파일 수를 센다(파일이 많아 몇 분 걸릴 수 있다).

    ```bash
    find "${BIO_DATA_ROOT:-data}/raw/pmc/metadata" -name '*.json' | wc -l
    ```

4. **끝나면 등급 판정과 본문 받기로 넘어간다.**

    ```bash
    python3 scripts/pmc.py grade
    python3 scripts/pmc.py fetch --grade A --workers 32
    ```

5. **RUNS.md에 기록한다.** `aws s3 sync`는 기록 줄을 출력하지 않으므로 직접 적는다. 파일 수는 3번 명령으로, 용량은 `du -sh "${BIO_DATA_ROOT:-data}/raw/pmc/metadata"`로 확인한다.

    ```text
    | 2026-10-20 | PMC 메타데이터(aws s3 sync) | metadata/ 전체 | (파일 수) | (용량) | (이름) | - |
    ```

## 6. 팀 계정이 실제로 필요한 때

| 할 일 | 자격 증명 | 비용 |
|---|---|---|
| PMC·OpenAlex 공개 저장소 받기(1차) | 필요 없음(`--no-sign-request`) | 받는 쪽에 청구되지 않는다 |
| bioRxiv·arXiv 원문 받기(2차, 요청자 부담 저장소) | 필요(`--request-payer requester`, 해당 버킷 읽기 권한) | 요청과 다운로드 비용을 팀 계정이 낸다 |
| 팀 S3 버킷에 올려 공유하기(선택) | 필요(팀 버킷 쓰기 권한) | 저장 용량과 요청 수만큼 낸다. 작은 파일 수백만 개는 tar로 묶어 올린다 |

- 요청자 부담 저장소는 서명 없는 요청을 받지 않는다. 모든 요청에 자격 증명과 `--request-payer requester`가 있어야 한다.

    ```bash
    aws s3 ls --profile bio-team --request-payer requester s3://biorxiv-src-monthly/
    ```

- 큰 양을 받기 전에는 `ls --recursive --summarize`로 용량부터 확인하고, 예상 비용을 관리자와 확인한다. 요금은 [S3 요금 안내](https://aws.amazon.com/s3/pricing/)에서 본다.

## 7. 자격 증명 안전 수칙

- 키는 홈 폴더의 `.aws/credentials`에만 둔다. 저장소 폴더, 스크립트, RUNS.md, 메신저, GitHub 이슈에 붙이지 않는다.
- 콘솔에서 받은 액세스 키 CSV 파일은 저장소 밖에 두고, 설정을 마치면 지운다. `.gitignore`가 `*accessKeys*.csv`를 막아 두었지만, 커밋 전에 `git status`로 한 번 더 확인한다.
- AWS는 사람이 임시 자격 증명(IAM Identity Center)을 쓰도록 권장한다. 액세스 키를 받았다면 프로젝트가 끝나거나 팀원이 바뀔 때 교체나 삭제를 요청한다.
- 콘솔 로그인에는 MFA를 켠다.
- 키가 노출됐다고 생각되면 바로 관리자에게 알려 비활성화한다.

## 8. 자주 만나는 오류

| 메시지 | 뜻 | 해결 |
|---|---|---|
| `Unable to locate credentials` | 서명할 자격 증명을 찾지 못했다 | 공개 저장소면 `--no-sign-request`를 붙인다. 팀 작업이면 `--profile` 이름을 확인한다 |
| 공개 저장소에서 `AccessDenied` | `--no-sign-request`가 빠져 팀 자격 증명으로 서명됐고, 팀 정책에 그 버킷 권한이 없다. 다른 계정의 버킷은 내 쪽 정책과 버킷 쪽 정책이 모두 허용해야 열린다 | `--no-sign-request`를 붙인다 |
| `Token has expired` 같은 SSO 만료 메시지 | SSO 세션이 끝났다 | `aws sso login --profile bio-team` |
| `Unknown options: --dry-run` | 옵션 이름 오타 | `--dryrun`으로 붙여 쓴다 |
| `aws: command not found` | 설치 위치가 `PATH`에 없다 | `~/.local/bin` 같은 설치 위치를 `PATH`에 더한다 |

## 9. 연습 점검표

- [ ] `aws --version`이 `aws-cli/2.`로 시작한다.
- [ ] `aws sts get-caller-identity --profile bio-team`이 팀 계정 번호를 보여 준다.
- [ ] README.txt를 받았다.
- [ ] 메타데이터 JSON 하나를 화면에 열어 `license_code`를 확인했다.
- [ ] `--dryrun`으로 미리 본 뒤 논문 한 편 폴더를 받았다.
- [ ] 같은 sync를 다시 실행해 건너뛰는 것을 확인했다.
- [ ] 메타데이터 전체 sync를 tmux에서 시작했다.

## 출처

- [AWS CLI 설치](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) · [설정 파일과 프로필](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html) · [SSO 설정](https://docs.aws.amazon.com/cli/latest/userguide/sso-configure-profile-token.html) · [S3 전송 설정](https://docs.aws.amazon.com/cli/latest/topic/s3-config.html)
- [GetCallerIdentity(권한 불필요)](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html) · [다른 계정 요청의 정책 판단](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic-cross-account.html) · [요청자 부담 버킷](https://docs.aws.amazon.com/AmazonS3/latest/userguide/RequesterPaysBuckets.html) · [IAM 보안 모범 사례](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [PMC Cloud Service](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/) · [PMC 저장소 README](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)
