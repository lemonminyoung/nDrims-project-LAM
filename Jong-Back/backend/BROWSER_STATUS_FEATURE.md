# 브라우저 상태 체크 기능

## 개요
백엔드에서 실행 웹의 브라우저 실행 상태를 확인할 수 있는 기능을 추가했습니다.

## 구현 내용

### 1. 실행 웹 → 백엔드 (브라우저 정보 전송)

**파일**: `execution_web_service.py`

실행 웹이 `/command`를 폴링할 때마다 현재 브라우저 상태를 query parameter로 전송합니다:

```python
# 브라우저 상태 계산
browser_count = len(ACTIVE_BROWSERS)  # 활성 브라우저 개수
browser_running = browser_count > 0   # 브라우저가 하나라도 있으면 True

# 백엔드에 전송
response = requests.get(
    f"{BACKEND_URL}/command",
    params={
        "browser_running": str(browser_running).lower(),  # "true" or "false"
        "browser_count": browser_count                     # 0, 1, 2, ...
    },
    timeout=10
)
```

**폴링 주기**: 5초마다

---

### 2. 백엔드 (브라우저 정보 저장)

**파일**: `Api.py`

#### 전역 변수 추가
```python
# 브라우저 상태
BROWSER_RUNNING = False  # 브라우저가 실행 중인지
BROWSER_COUNT = 0        # 활성 브라우저 개수
```

#### `/command` 엔드포인트 수정
```python
@app.get("/command")
async def command(browser_running: str = "false", browser_count: int = 0):
    global BROWSER_RUNNING, BROWSER_COUNT

    # 브라우저 상태 업데이트
    BROWSER_RUNNING = browser_running.lower() == "true"
    BROWSER_COUNT = browser_count

    # ... (기존 로직)
```

#### `/execution_web/status` 엔드포인트 업데이트
```python
@app.get("/execution_web/status")
async def execution_web_status():
    return {
        "connected": EXECUTION_WEB_CONNECTED,
        "last_poll_time": LAST_POLL_TIME.isoformat() if LAST_POLL_TIME else None,
        "browser_running": BROWSER_RUNNING,  # 새로 추가
        "browser_count": BROWSER_COUNT        # 새로 추가
    }
```

#### `/execution_web/shutdown` 엔드포인트 업데이트
실행 웹이 종료되면 브라우저 상태도 초기화:
```python
@app.post("/execution_web/shutdown")
async def execution_web_shutdown(request: dict):
    global EXECUTION_WEB_CONNECTED, BROWSER_RUNNING, BROWSER_COUNT
    EXECUTION_WEB_CONNECTED = False
    BROWSER_RUNNING = False  # 브라우저 상태 초기화
    BROWSER_COUNT = 0        # 브라우저 개수 초기화
    # ...
```

---

## 사용 방법

### 1. 브라우저 상태 확인

**API 호출**:
```bash
curl http://localhost:8000/execution_web/status
```

**응답 예시 (실행 웹 연결됨 + 브라우저 실행 중)**:
```json
{
  "connected": true,
  "last_poll_time": "2025-11-10T11:51:20.217330",
  "browser_running": true,
  "browser_count": 1
}
```

**응답 예시 (실행 웹 연결됨 + 브라우저 없음)**:
```json
{
  "connected": true,
  "last_poll_time": "2025-11-10T11:51:25.123456",
  "browser_running": false,
  "browser_count": 0
}
```

**응답 예시 (실행 웹 연결 끊김)**:
```json
{
  "connected": false,
  "last_poll_time": "2025-11-10T11:45:10.987654",
  "browser_running": false,
  "browser_count": 0
}
```

---

### 2. 프롬프트 웹에서 활용

프롬프트 웹에서 폴링으로 상태 확인:

```javascript
// 주기적으로 브라우저 상태 확인
setInterval(async () => {
  const response = await fetch('http://localhost:8000/execution_web/status');
  const status = await response.json();

  console.log('실행 웹 연결:', status.connected);
  console.log('브라우저 실행 중:', status.browser_running);
  console.log('브라우저 개수:', status.browser_count);

  // UI 업데이트
  if (!status.connected) {
    // 실행 웹이 연결 안 됨 → 로그아웃
    logout();
  } else if (status.connected && !status.browser_running) {
    // 실행 웹은 연결됐지만 브라우저는 없음 → 대기 중
    showStatus('대기 중');
  } else if (status.browser_running) {
    // 브라우저 실행 중 → 작업 중
    showStatus(`작업 중 (브라우저 ${status.browser_count}개)`);
  }
}, 2000); // 2초마다 체크
```

---

## 상태 변화 시나리오

### 시나리오 1: 로그인 → 작업 → 종료

1. **실행 웹 시작**
   ```json
   {
     "connected": true,
     "browser_running": false,
     "browser_count": 0
   }
   ```

2. **로그인 요청 → 브라우저 실행**
   ```json
   {
     "connected": true,
     "browser_running": true,
     "browser_count": 1
   }
   ```

3. **액션 실행 중 (브라우저 유지)**
   ```json
   {
     "connected": true,
     "browser_running": true,
     "browser_count": 1
   }
   ```

4. **실행 웹 X 버튼 클릭 → 종료**
   ```json
   {
     "connected": false,
     "browser_running": false,
     "browser_count": 0
   }
   ```

---

### 시나리오 2: 브라우저만 종료 (실행 웹은 유지)

만약 나중에 브라우저를 수동으로 닫는 기능을 추가하면:

1. **브라우저 실행 중**
   ```json
   {
     "connected": true,
     "browser_running": true,
     "browser_count": 1
   }
   ```

2. **브라우저만 종료 (실행 웹은 유지)**
   ```json
   {
     "connected": true,
     "browser_running": false,
     "browser_count": 0
   }
   ```

---

## 업데이트 주기

- **실행 웹 → 백엔드**: 5초마다 폴링 (브라우저 상태 자동 업데이트)
- **프롬프트 웹 → 백엔드**: 원하는 주기로 `/execution_web/status` 조회 (권장: 2~5초)

---

## 장점

1. **실시간 상태 파악**
   - 백엔드에서 브라우저가 실행 중인지 즉시 확인 가능
   - 프롬프트 웹에서 UI 업데이트에 활용

2. **디버깅 용이**
   - 브라우저가 비정상 종료되었는지 확인 가능
   - 실행 웹은 살아있지만 브라우저만 없는 상태 감지

3. **사용자 경험 개선**
   - "작업 중" vs "대기 중" vs "연결 끊김" 구분 가능
   - 브라우저 개수로 병렬 작업 여부 확인

---

## 테스트 방법

### 1. 백엔드 재시작
```bash
cd C:\Users\김민영\Desktop\Jong-Back\backend
# 기존 백엔드 종료 (Ctrl+C)
python Api.py
```

### 2. 실행 웹 시작
```bash
cd C:\Users\김민영\Desktop\jong2
python execution_web_service.py
```

### 3. 상태 확인
```bash
# 브라우저 없는 상태
curl http://localhost:8000/execution_web/status
# → browser_running: false, browser_count: 0

# 로그인 후 (브라우저 실행 중)
curl http://localhost:8000/execution_web/status
# → browser_running: true, browser_count: 1
```

---

## 주의사항

1. **백엔드 재시작 필요**
   - `Api.py`가 수정되었으므로 백엔드를 재시작해야 새 필드가 나타납니다.

2. **폴링 지연**
   - 실행 웹이 5초마다 폴링하므로, 브라우저 상태 변경이 최대 5초 지연될 수 있습니다.

3. **연결 타임아웃**
   - 15초 동안 폴링이 없으면 `connected: false`로 전환됩니다.

---

## 향후 확장 가능성

1. **브라우저 상세 정보**
   - 각 브라우저의 현재 URL
   - 각 브라우저가 실행 중인 작업

2. **수동 브라우저 종료 API**
   - `POST /browser/close` 엔드포인트 추가
   - 특정 브라우저만 종료하는 기능

3. **브라우저 풀 관리**
   - 최대 브라우저 개수 제한
   - 유휴 브라우저 자동 종료

---

## 결론

✓ 백엔드에서 브라우저 실행 여부 확인 가능
✓ 브라우저 개수 실시간 모니터링 가능
✓ 프롬프트 웹에서 상태 기반 UI 업데이트 가능

**구현 완료!**
