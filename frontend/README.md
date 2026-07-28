# AI Character Chat React Frontend

FastAPI 백엔드의 인증, 캐릭터, 기억, 대화 기록과 SSE 스트리밍을 직접 확인하는
React + TypeScript 클라이언트입니다. 25단계에서 단일 HTML 파일을 Vite 프로젝트로
분리했습니다.

## 필요한 환경

- Node.js 20 이상
- npm
- `http://127.0.0.1:8000`에서 실행 중인 백엔드

로컬 Node.js 20.18에서도 실행할 수 있도록 Vite 6을 사용합니다. 최신 Vite 7은
Node.js 20.19 이상이 필요하므로 Node를 올리기 전에는 임의로 major version을
변경하지 않습니다. CI는 Node.js 22로 검증합니다.

## 설치와 실행

먼저 백엔드를 실행합니다.

```powershell
cd backend
Copy-Item .env.example .env
docker compose up --build
```

다른 터미널에서 프론트엔드 의존성을 설치하고 개발 서버를 엽니다.

```powershell
cd frontend
npm install
npm run dev
```

브라우저에서 `http://127.0.0.1:5173`으로 접속합니다.

## 사용 순서

1. API Base URL이 `http://127.0.0.1:8000`인지 확인합니다.
2. 회원가입 후 로그인합니다.
3. 세션을 끝낼 때는 로그아웃해 사용자별 화면 상태를 함께 제거합니다.
4. 캐릭터를 생성하거나 목록에서 공용·기존 캐릭터를 선택합니다.
5. 내 캐릭터라면 상세 설정을 수정하거나 삭제할 수 있습니다.
6. 전역 또는 캐릭터별 장기 기억을 작성하고 중요도·활성 상태를 관리합니다.
7. 자연어로 활성 기억을 의미 검색하거나 필요한 기억을 재색인합니다.
8. 메시지를 보내 토큰 단위 스트리밍을 확인합니다.
9. 대화 목록을 새로고침해 이전 대화를 열거나 삭제합니다.

토큰, 선택 캐릭터 ID, 현재 대화 ID와 API URL은 새로고침 후에도 이어서 테스트할 수
있도록 `localStorage`에 저장합니다. 이 방식은 학습·개발용이며, 운영에서는
HttpOnly cookie와 refresh token 정책을 별도로 설계해야 합니다.

## 파일별 책임

```text
frontend/
├─ index.html                 Vite가 React를 연결하는 HTML 진입점
├─ package.json               실행·테스트·빌드 명령과 버전
├─ vite.config.ts             개발/미리보기 서버 설정
├─ tsconfig.json              strict TypeScript 검사 설정
└─ src/
   ├─ main.tsx                React root 연결
   ├─ App.tsx                 인증·캐릭터·대화의 공통 상태와 흐름
   ├─ components/             인증·캐릭터 목록·대화·채팅 표현과 입력
   ├─ hooks/                  localStorage 연동 상태
   ├─ lib/api.ts              HTTP/SSE API client
   ├─ lib/sse.ts              chunk 경계와 무관한 SSE parser
   └─ types/api.ts            백엔드 요청·응답 타입
```

컴포넌트는 화면 입력과 표현을 담당하고, `App`은 작업 순서를 조정하며, `ApiClient`는
HTTP 세부사항을 숨깁니다. 따라서 백엔드 경로나 인증 방식이 바뀌었을 때 JSX 전체를
찾아다니지 않고 API 계층을 중심으로 수정할 수 있습니다.

## 테스트와 production build

```powershell
cd frontend
npm test
npm run build
npm run preview
```

- `npm test`: SSE 분할 chunk, CRLF, 마지막 이벤트와 URL 정규화를 검증합니다.
- `npm run build`: TypeScript strict 검사 후 `dist/` production bundle을 만듭니다.
- `npm run preview`: 만들어진 `dist/`를 로컬에서 확인합니다.

GitHub Actions의 `frontend-ci.yml`도 push와 pull request마다 `npm ci`, 테스트,
production build를 같은 순서로 실행합니다.

## 현재 한계

- 기억 목록은 최근 100개를 브라우저에서 필터링하므로 pagination이 아직 없습니다.
- access token은 localStorage에 저장하며 refresh token 자동 갱신은 아직 없습니다.
- 토큰 만료 후 자동 갱신과 로그아웃 UI는 아직 없습니다.
- API 오류를 상태 문구 하나로 표시하며 재시도 UX는 단순합니다.
- 브라우저 E2E 테스트는 아직 없고 API/SSE 단위 테스트부터 적용했습니다.
