# Coin Trader - 자동 매매 시스템

암호화폐 자동 매매 시스템으로, 업비트 API를 통해 24시간 단타 매매를 수행합니다.
뉴스/트위터 모니터링을 통한 인터럽트 매매와 기술적 분석 기반 자동 매매를 지원합니다.

## 주요 기능

| 기능 | 설명 | 상태 |
|------|------|------|
| **자동 매매** | JSON 규칙 기반 24시간 단타 매매 | ✅ 구현 |
| **실시간 대시보드** | 포트폴리오, 거래 내역, 시그널 모니터링 | ✅ 구현 |
| **차트** | TradingView lightweight-charts 기반 캔들 차트 | ✅ 구현 |
| **뉴스 모니터링** | Gemini API로 N분 간격 뉴스 분석 | ✅ 구현 |
| **트위터 모니터링** | RSS/Nitter 폴링 → Gemini 분석 | ✅ 구현 |
| **매매 규칙 편집** | 웹 UI에서 JSON 규칙 편집 | ✅ 구현 |
| **한국투자증권** | 국내/해외 주식 매매 | 🔜 TODO |

## 기술 스택

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy / SQLite
- **Frontend**: React 18 / TypeScript / Vite / TailwindCSS
- **차트**: TradingView lightweight-charts
- **AI 분석**: Google Gemini API
- **실시간**: WebSocket

## 빠른 시작

### 1. 사전 설치

```bash
# Python 3.11 이상 설치 (https://www.python.org/downloads/)
python --version

# pip 최신 버전으로 업그레이드
python -m pip install --upgrade pip

# Node.js 18 이상 설치 (https://nodejs.org/)
node --version
npm --version
```

### 2. API 키 발급

| API | 용도 | 발급 링크 |
|-----|------|----------|
| **업비트** | 코인 매매 | [업비트 개발자센터](https://upbit.com/mypage/open_api_management) |
| **Google Gemini** | 뉴스/트위터 분석 | [Google AI Studio](https://aistudio.google.com/apikey) |

### 3. 환경 설정

```bash
# 프로젝트 클론
git clone https://github.com/jehyeok123/coin_trader.git
cd coin_trader

# .env 파일 생성
cp .env.example .env
# .env 파일을 열어서 2번에서 발급받은 API 키 입력
```

### 4. Backend 실행

```bash
# 의존성 설치
cd backend
pip install -r requirements.txt

# 서버 실행 (프로젝트 루트에서)
cd ..
uvicorn backend.main:app --reload --reload-exclude .venv --host 0.0.0.0 --port 8000
```

### 5. Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

### 6. 접속

브라우저에서 `http://localhost:5173` 접속

## 프로젝트 구조

```
coin_trader/
├── backend/           # FastAPI 서버
│   ├── brokers/       # 브로커 추상화 (업비트, 한투 등)
│   ├── core/          # 매매 엔진, 규칙 엔진
│   ├── signals/       # 시그널 소스 (뉴스, 트위터)
│   ├── api/           # REST API + WebSocket
│   ├── models/        # DB 모델
│   └── utils/         # 유틸리티 (Markdown 로깅)
├── frontend/          # React 웹 UI
│   └── src/
│       ├── components/  # 화면 컴포넌트
│       ├── hooks/       # 커스텀 훅
│       └── services/    # API 클라이언트
├── logs/              # Markdown 형식 거래 로그
└── docs/              # 상세 문서
```

## 라이선스

MIT License
