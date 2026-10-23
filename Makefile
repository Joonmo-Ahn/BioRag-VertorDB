# 자주 쓰는 명령 모음. make 가 없으면 README의 python3 명령을 그대로 쓴다.
PY ?= python3

.PHONY: help check sample sample-pmc sample-pubmed sample-openfda sample-ctgov

help:
	@echo "make check   환경 점검(Python, 용량, 사이트 접속)"
	@echo "make sample  소스 4곳 표본 받기"

check:
	$(PY) scripts/check_env.py

sample: sample-pmc sample-pubmed sample-openfda sample-ctgov

sample-pmc:
	$(PY) scripts/pmc.py sample

sample-pubmed:
	$(PY) scripts/pubmed.py sample

sample-openfda:
	$(PY) scripts/openfda.py download --parts 1

sample-ctgov:
	$(PY) scripts/ctgov.py sample
