# Coin Trader 사용법

## 목차

1. [설치 및 환경 설정](#설치-및-환경-설정)
2. [API 키 설정](#api-키-설정)
3. [서버 실행](#서버-실행)
4. [웹 UI 사용법](#웹-ui-사용법)
5. [매매 규칙 설정](#매매-규칙-설정)
6. [시그널 모니터링](#시그널-모니터링)
7. [API 엔드포인트](#api-엔드포인트)
8. [문제 해결](#문제-해결)

---

## 설치 및 환경 설정

### 시스템 요구사항

| 항목 | 최소 요구사항 |
|------|-------------|
| Python | 3.11 이상 |
| Node.js | 18 이상 |
| OS | Windows / macOS / Linux |

### 설치

```bash
# 1. Backend 의존성 설치
cd backend
pip install -r requirements.txt

# 2. Frontend 의존성 설치
cd ../frontend
npm install
```

---

## API 키 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 키를 입력합니다.

```env
# 업비트 API (필수)
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key

# Google Gemini API (뉴스/트위터 분석용)
GEMINI_API_KEY=your_gemini_key

# 트위터 감시 계정 (쉼표로 구분)
TWITTER_MONITOR_ACCOUNTS=elonmusk,VitalikButerin

# 뉴스 확인 간격 (분)
NEWS_CHECK_INTERVAL_MINUTES=5
```

### 업비트 API 키 발급

1. [업비트](https://upbit.com) 로그인
2. 마이페이지 → Open API 관리
3. API 키 발급 (주문하기 권한 필요)
4. **IP 제한 설정 권장**

### Gemini API 키 발급

1. [Google AI Studio](https://aistudio.google.com/apikey) 접속
2. API 키 생성

---

## 서버 실행

### Backend (API 서버)

```bash
# 프로젝트 루트에서 실행
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

서버 시작 시 자동으로:
- SQLite 데이터베이스 생성
- 업비트 브로커 초기화
- 매매 엔진 및 스케줄러 준비

### Frontend (웹 UI)

```bash
cd frontend
npm run dev
```

`http://localhost:5173` 에서 웹 UI에 접속합니다.

---

## 웹 UI 사용법

### 대시보드

- **매매 시작/중지**: 우측 상단 버튼으로 자동 매매를 제어합니다.
- **시스템 상태**: 매매 엔진, 뉴스 모니터, 트위터 모니터의 실행 상태를 확인합니다.
- **포트폴리오**: 보유 자산, 현금 잔고, 개별 포지션의 수익률을 실시간으로 확인합니다.
- **최근 거래**: 최근 10건의 거래 내역을 확인합니다.

### 차트

- 종목을 선택하고 시간 간격(1분~1일)을 변경할 수 있습니다.
- TradingView 스타일의 캔들스틱 차트와 거래량이 표시됩니다.
- 30초마다 자동 갱신됩니다.

### 거래 내역

- 모든 자동 매매 기록을 조회합니다.
- 매수/매도 필터링, 페이지네이션을 지원합니다.
- 각 거래의 **매매 근거**를 확인할 수 있습니다.

### 매매 규칙

- **폼 편집**: 개별 항목을 직관적으로 수정합니다.
- **JSON 편집**: 고급 사용자를 위해 직접 JSON을 편집합니다.
- **초기화**: 기본 규칙으로 되돌립니다.

### 시그널

- 뉴스/트위터에서 감지된 시그널을 실시간으로 확인합니다.
- 각 시그널의 **1줄 요약**, **신뢰도**, **매수/매도 액션**을 확인합니다.
- **수동 확인** 버튼으로 즉시 뉴스를 분석할 수 있습니다.

### 설정

- API 연결 상태를 확인합니다.
- 뉴스 검색 간격을 변경합니다 (기본: 5분).
- 트위터 감시 계정을 추가/제거합니다.

---

## 매매 규칙 설정

### 기본 매매 설정

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `stop_loss_pct` | 3.0 | 손절 퍼센트 |
| `take_profit_pct` | 5.0 | 익절 퍼센트 |
| `trailing_stop_pct` | 1.5 | 트레일링 스톱 |
| `max_position_size_pct` | 10.0 | 최대 포지션 크기 (자산 대비 %) |
| `max_concurrent_positions` | 5 | 최대 동시 보유 종목 수 |
| `min_order_amount_krw` | 5,000 | 최소 주문 금액 (KRW) |
| `cooldown_seconds` | 60 | 매매 주기 (초) |

### 기술적 지표

현재 지원되는 지표:
- **RSI**: 과매수/과매도 판단
- **MACD**: 골든크로스/데드크로스
- **거래량 급증**: 평균 대비 급증 감지
- **볼린저 밴드**: 밴드 이탈 감지
- **이동평균선**: 골든크로스/데드크로스

> 지표의 구체적인 파라미터와 전략은 향후 상세화 예정입니다.

### 인터럽트 시그널

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `news_confidence_threshold` | 0.8 | 뉴스 시그널 실행 신뢰도 임계값 |
| `twitter_confidence_threshold` | 0.9 | 트위터 시그널 실행 신뢰도 임계값 |
| `max_interrupt_position_pct` | 5.0 | 인터럽트 매매 최대 포지션 크기 |

---

## 시그널 모니터링

### 뉴스 모니터링

1. 설정된 간격(기본 5분)마다 Gemini API가 최신 뉴스를 검색
2. 분석 결과를 JSON 형태의 시그널로 변환
3. 신뢰도가 임계값 이상이면 자동으로 매매 실행
4. 시그널 요약이 UI에 실시간으로 표시

### 트위터 모니터링

1. 설정된 계정의 RSS/Nitter 피드를 주기적으로 폴링
2. 새 글이 발견되면 즉시 Gemini로 분석
3. 인터럽트 시그널로 처리 (높은 신뢰도 필요)
4. 실시간으로 UI에 표시

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/trading/status` | 매매 엔진 상태 |
| `POST` | `/api/trading/start` | 매매 시작 |
| `POST` | `/api/trading/stop` | 매매 중지 |
| `GET` | `/api/trading/history` | 거래 내역 조회 |
| `GET` | `/api/trading/positions` | 보유 포지션 조회 |
| `GET` | `/api/rules` | 매매 규칙 조회 |
| `PUT` | `/api/rules` | 매매 규칙 수정 |
| `POST` | `/api/rules/reset` | 기본 규칙 초기화 |
| `GET` | `/api/charts/{symbol}` | 차트 데이터 |
| `GET` | `/api/charts/symbols` | 심볼 목록 |
| `GET` | `/api/signals` | 시그널 기록 |
| `GET` | `/api/signals/latest` | 최신 시그널 |
| `POST` | `/api/signals/check-news` | 수동 뉴스 확인 |
| `GET` | `/api/settings` | 설정 조회 |
| `PUT` | `/api/settings` | 설정 변경 |
| `WS` | `/ws` | WebSocket 실시간 |

---

## 문제 해결

### 업비트 API 오류

```
RuntimeError: 업비트 API 키가 설정되지 않았습니다.
```
→ `.env` 파일에 `UPBIT_ACCESS_KEY`와 `UPBIT_SECRET_KEY`를 설정하세요.

### Gemini API 오류

```
Gemini 모델이 초기화되지 않았습니다.
```
→ `.env` 파일에 `GEMINI_API_KEY`를 설정하세요.

### 프론트엔드 연결 오류

프록시 설정으로 인해 Backend가 먼저 실행되어야 합니다.
1. Backend: `uvicorn backend.main:app --port 8000`
2. Frontend: `npm run dev`

### 로그 확인

거래 로그는 `logs/` 디렉토리에 일별 Markdown 파일로 저장됩니다.
```
logs/trading_2026-02-28.md
```
