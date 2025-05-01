# 🎮 Game Log Simulator

**가상의 모바일 로그라이크 게임**을 운영하며며 간단한 로그를 생성하는 시뮬레이터입니다.  

현실감 있는 **접속/게임/과금/이탈/복귀** 이벤트를 자동 생성해줍니다.

개인적으로 게임로그 데이터 분석 인프라 구성 연습에 활용하고자 ChatGPT를 활용해 만들었고 동일한 필요가 있는 분들이 활용하실 수 있습니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)  
[![Build: Stable](https://img.shields.io/badge/Build-Stable-success)]()  
[![Language: Python](https://img.shields.io/badge/Language-Python%203.10+-brightgreen)]()

---

## 📚 About

- 30개 챕터로 구성된 로그라이크 게임
- 현실적인 접속, 게임 플레이, 과금, 이탈 흐름 재현
- 유저 성장에 따른 챕터 클리어 확률 조정
- 특별 챕터(10, 20, 30)에서 매출 최적화 이벤트 발생
- JSON/Parquet 포맷 데이터 생성 가능

---

## 🚀 Features

- **DAU 시뮬레이션** (Retention + Recovery 반영)
- **Game Play 로그** (에너지 소모/회복 기반)
- **Item 구매 로직** (STEP1~3, STEP_SPECIAL 구매 흐름)
- **자연스러운 이탈/복귀** (15회 재도전 이탈 + 7일 내 5% 복귀)
- **시간대별 접속 빈도 조정**

---

## 🗂️ 생성되는 데이터

| 파일명 | 설명 |
|:---|:---|
| login_YYYYMMDD | 유저 로그인/접속 로그 |
| gamelog_YYYYMMDD | 챕터 클리어 게임 로그 |
| item_YYYYMMDD | 아이템 구매 로그 |

저장 경로: {현재 경로}/results/{로그파일 형식}/{날짜}/

---

## ⚙️ How to Run
uv를 활용한 프로젝트 세팅이 이루어졌기 때문에 uv 설치가 선행 필요합니다.
```bash
# uv 가 설치되어있지 않다면 다음 명령어로 설치
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# 환경 세팅
uv sync

# 실행
uv run main.py
```

### 파라미터:

start_date: 시작일 (기본값: 2025-04-01)

days: 시뮬레이션 일수

output_format: 'json' 또는 'parquet'

---
## 🎯 Key Simulation Rules
### 접속
- 시간대별 접속 빈도 차등 조정
- 하루 평균 세션 수 조정 가능

### 게임 플레이
- 접속 및 이전 게임 플레이 후 80% 확률로 플레이
- 1시간마다 5 에너지 회복
- 게임당 5 에너지 소모

### 챕터 클리어 확률
- 1챕터: 98% → 30챕터: 35% 선형 감소
- 10, 20, 30챕터 추가 난이도 상승(클리어 확률 감소)
- 유저 성장(접속 일수)에 따라 추가 성공 보너스 부여

### 과금
- 3회 이상 재도전 시 구매 이벤트 확률적으로 발생
- 10, 20, 30챕터: 8% 확률로 STEP_SPECIAL 구매 (성공률 +7%)
- 일반 챕터: 5% 확률로 STEP1~3 순서 구매

### 이탈과 복귀
- retention_curve에 따라 자연 이탈탈
- 하루 동안 한 챕터 15회 이상 연속 실패 시 이탈
- 이탈 후 7일 이내 5% 확률 복귀