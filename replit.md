# 입금 바랍니다 — 유튜브 성과 관리 대시보드

유튜브 웹시리즈 "입금 바랍니다"의 재생목록 영상별 조회수·좋아요·댓글을 실시간으로 모니터링하는 Streamlit 대시보드.

## Run & Operate

- `streamlit run artifacts/youtube-dashboard/app.py --server.port 5000` — 대시보드 실행 (port 5000)
- Workflow: "Start application" 으로 자동 실행됨
- 필요 입력값: YouTube Data API v3 Key, Playlist ID (앱 사이드바에서 입력)

## Stack

- Python 3.11, Streamlit 1.45.1
- Google API Python Client (YouTube Data API v3)
- pandas 2.2.3

## Where things live

- `artifacts/youtube-dashboard/app.py` — 메인 Streamlit 앱
- `artifacts/youtube-dashboard/.streamlit/config.toml` — 앱별 Streamlit 설정
- `.streamlit/config.toml` — 루트 Streamlit 설정 (실행 시 사용됨)
- `artifacts/youtube-dashboard/requirements.txt` — Python 의존성 목록

## Architecture decisions

- Streamlit 워크플로는 workspace root에서 실행되므로 `.streamlit/config.toml`은 루트에 위치해야 함
- `@st.cache_data(ttl=600)`로 10분 캐싱 → API 할당량 절약 + 자동 새로고침 구현
- 자동 새로고침은 `time.sleep(1)` + `st.rerun()` 루프로 구현 (10분 경과 시 캐시 클리어 후 재실행)
- YouTube API commentThreads는 댓글 비활성화 영상에서 403 오류 발생 → `HttpError` 핸들링으로 graceful 처리

## Product

- 재생목록 내 모든 영상 목록 자동 조회 (페이지네이션 지원)
- 영상별 실시간 조회수 / 좋아요 / 댓글 수 표 출력
- 영상별 최근 댓글 5개 아코디언 방식 표출
- 누적 합계(조회수·좋아요·댓글·영상 수) 상단 메트릭 카드
- 블랙 테마 + 유튜브 레드 포인트 컬러 디자인
- 10분 자동 새로고침

## User preferences

- 기술 스택: Python + Streamlit
- 디자인: 블랙 테마, 유튜브 레드 포인트
- 언어: 한국어 UI

## Gotchas

- pip 직접 사용 불가 — `installLanguagePackages` 콜백으로 패키지 설치
- Streamlit 최초 실행 시 이메일 입력 프롬프트가 뜰 수 있음 → `gatherUsageStats = false` 설정으로 해결
- `.streamlit/config.toml`은 반드시 루트에도 복사해야 워크플로에서 읽힘

## Pointers

- YouTube Data API v3 문서: https://developers.google.com/youtube/v3
- Streamlit docs: https://docs.streamlit.io
