# 모델 통합 가이드

## 개요
이 문서는 nDRIMS 자동화 시스템에 액션 생성 모델을 통합하는 방법을 설명합니다.

현재 시스템은 **임시 액션**(trajectory_student_check.json)을 사용하고 있으며, 모델을 통합하면 사용자의 프롬프트에 맞는 액션을 자동으로 생성할 수 있습니다.

---

## 현재 시스템 흐름

```
프롬프트 웹 (React)
    ↓ POST /prompt (프롬프트 전송)
백엔드 (FastAPI)
    ↓ GET /command (폴링)
실행 웹 (Python + Playwright)
    ↓ 스크린샷 + UI 상태 캡처
    ↓ POST /state (상태 전송)
백엔드 (FastAPI)
    ↓ [임시] 고정된 액션 생성
    ↓ state.json 저장
실행 웹
    ↓ GET /action (액션 가져오기)
    ↓ Playwright로 액션 실행
```

---

## 모델 통합 후 흐름

```
프롬프트 웹 (React)
    ↓ POST /prompt ("학적부 조회")
백엔드 (FastAPI)
    ↓ GET /command (폴링)
실행 웹 (Python + Playwright)
    ↓ 스크린샷 + UI 상태 캡처
    ↓ POST /state (프롬프트 + 스크린샷 + UI 상태)
백엔드 (FastAPI)
    ↓ [모델 호출] 프롬프트와 현재 상태를 입력으로 전달
    ↓ 모델이 액션 생성 (trajectory JSON)
    ↓ state.json 저장
실행 웹
    ↓ GET /action (생성된 액션 가져오기)
    ↓ Playwright로 액션 실행
```

---

## 모델 입력 데이터

모델은 다음 세 가지 데이터를 입력으로 받습니다:

### 1. **프롬프트 (PROMPT_TEXT)**
- 타입: `str`
- 설명: 사용자가 입력한 작업 요청
- 예시:
  - "학적부 조회"
  - "성적 확인"
  - "수강신청 내역 확인"

### 2. **스크린샷 (screenshot)**
- 타입: `str` (base64 인코딩)
- 설명: 현재 nDRIMS 화면의 전체 스크린샷
- 용도: 현재 화면의 시각적 정보를 모델에 제공
- 크기: 평균 500KB ~ 2MB (base64 인코딩 후)

### 3. **UI 상태 (ui_state)**
- 타입: `dict`
- 설명: 현재 nDRIMS 페이지의 구조화된 상태 정보
- 구조:
```json
{
  "url": "https://ndrims.dongguk.edu/main/main.clx",
  "sidebar": [
    {
      "label": "학적/확인서",
      "expanded": false,
      "checked": false,
      "sub_items": []
    },
    {
      "label": "수강신청",
      "expanded": true,
      "checked": false,
      "sub_items": [
        {
          "label": "희망강의신청",
          "expanded": false,
          "checked": true,
          "sub_items": []
        }
      ]
    }
  ],
  "current_page": {
    "title": "희망강의신청",
    "form_fields": [
      {
        "id": "input_0",
        "label": "조직분류",
        "type": "input",
        "input_type": "text",
        "value": "학부(서울)"
      }
    ]
  }
}
```

**UI 상태 필드 설명:**
- `url`: 현재 페이지 URL
- `sidebar`: 왼쪽 사이드바 메뉴 트리 (expanded/checked 상태 포함)
- `current_page.title`: 현재 활성화된 페이지 제목
- `current_page.form_fields`: 현재 페이지의 입력 필드들

---

## 모델 출력 데이터

모델은 다음 형식의 액션을 생성해야 합니다:

```python
{
    "type": "trajectory",
    "actions_file": "trajectory_xxx.json",
    "description": "액션 설명"
}
```

### 출력 필드 설명:
- `type`: 항상 `"trajectory"` (향후 다른 타입 추가 가능)
- `actions_file`: 생성한 trajectory JSON 파일 이름
- `description`: 액션에 대한 간단한 설명 (사용자에게 표시됨)

### Trajectory JSON 파일 형식

모델은 trajectory 파일을 생성하여 `jong2/` 디렉토리에 저장해야 합니다.

**권장 형식 (자동 검증):**
```json
[
  {
    "action": {
      "name": "click",
      "args": {
        "selector": "role=treeitem[name='학적/확인서']"
      }
    }
  },
  {
    "action": {
      "name": "click",
      "args": {
        "selector": "text=학적부열람"
      }
    }
  },
  {
    "action": {
      "name": "sleep",
      "args": {
        "timeout_ms": 2000
      }
    }
  }
]
```

**중요: 자동 페이지 검증**
- 시스템이 **자동으로** 마지막 click 액션에서 페이지 제목을 추출합니다
- 예: `"selector": "text=학적부열람"` → "학적부열람" 추출
- 예: `"selector": "role=treeitem[name='성적조회']"` → "성적조회" 추출
- 액션 실행 후 실제 페이지 제목과 비교하여 검증

**마지막 액션 작성 가이드:**
- 마지막 click 액션의 selector에는 **목표 페이지 이름**이 포함되어야 합니다
- `text=페이지이름` 또는 `name='페이지이름'` 패턴 사용 권장
- sleep 액션은 검증에 영향을 주지 않습니다

**고급 형식 (수동 검증 지정):**
```json
{
  "actions": [
    {
      "action": {
        "name": "click",
        "args": {
          "selector": "role=treeitem[name='학적/확인서']"
        }
      }
    },
    {
      "action": {
        "name": "click",
        "args": {
          "selector": "text=학적부열람"
        }
      }
    }
  ],
  "verification": {
    "type": "page_title",
    "selector": "role=tabpanel >> div.h3 >> text=학적부열람",
    "expected_text": "학적부열람"
  }
}
```

**Verification 필드 (선택사항):**
- `type`: 검증 타입 (현재 `"page_title"` 지원)
- `selector`: Playwright selector (자동 추출이 실패할 경우 사용)
- `expected_text`: 예상되는 페이지 제목

**대부분의 경우 verification 필드 없이 간단한 배열 형식만 사용하면 됩니다!**

**지원하는 액션 타입:**
- `click`: 요소 클릭
- `type`: 텍스트 입력
- `select`: 드롭다운 선택
- `sleep`: 대기
- `wait_for_selector`: 특정 요소가 나타날 때까지 대기

자세한 액션 정의는 `jong2/explaywright.py`의 `ActionExecutor` 클래스를 참고하세요.

---

## 통합 방법

### 1단계: 모델 모듈 작성

`Jong-Back/backend/model.py` 파일을 생성하고 다음 함수를 구현합니다:

```python
import json
from pathlib import Path

def generate_action(prompt: str, screenshot: str, ui_state: dict) -> dict:
    """
    프롬프트와 현재 상태를 입력으로 받아 액션을 생성

    Args:
        prompt (str): 사용자 프롬프트 (예: "학적부 조회")
        screenshot (str): 현재 화면 스크린샷 (base64)
        ui_state (dict): 현재 UI 상태 (sidebar, current_page)

    Returns:
        dict: {
            "type": "trajectory",
            "actions_file": "trajectory_xxx.json",
            "description": "액션 설명"
        }
    """

    # TODO: 여기에 모델 호출 로직 구현
    # 1. 프롬프트, 스크린샷, UI 상태를 모델에 전달
    # 2. 모델이 액션 시퀀스 생성
    # 3. trajectory JSON 파일 생성
    # 4. 결과 반환

    # 예시 (실제 모델 호출로 대체 필요):
    trajectory_data = [
        {"action": {"name": "click", "args": {"selector": "role=treeitem[name='학적/확인서']"}}},
        {"action": {"name": "click", "args": {"selector": "text=학적부열람"}}},
        {"action": {"name": "sleep", "args": {"timeout_ms": 2000}}}
    ]

    # Trajectory 파일 저장
    filename = f"trajectory_{prompt.replace(' ', '_')}.json"
    trajectory_path = Path(__file__).parent.parent.parent / "jong2" / filename

    with open(trajectory_path, "w", encoding="utf-8") as f:
        json.dump(trajectory_data, f, ensure_ascii=False, indent=2)

    return {
        "type": "trajectory",
        "actions_file": filename,
        "description": f"{prompt} 액션"
    }
```

### 2단계: Api.py 수정

`Jong-Back/backend/Api.py`의 `/state` 엔드포인트를 수정합니다:

**현재 코드 (line 92-164):**
```python
@app.post("/state")
async def save_state(request: StateData):
    global PROMPT_TEXT

    state_data_to_save = request.data.copy()

    if PROMPT_TEXT:
        # ========== 모델 통합 지점 ==========
        # 임시 액션 (모델 통합 전)
        temp_action = {
            "type": "trajectory",
            "actions_file": "trajectory_student_check.json",
            "description": "학적부 열람 액션 (임시)"
        }
        state_data_to_save["generated_action"] = temp_action
        # ====================================

    # state.json 저장
    save_path = os.path.join(os.path.dirname(__file__), "state.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(state_data_to_save, f, ensure_ascii=False, indent=2)

    return {"ok": True, "message": "state.json 저장 완료", "path": save_path}
```

**수정 후 코드:**
```python
from model import generate_action  # 추가

@app.post("/state")
async def save_state(request: StateData):
    global PROMPT_TEXT

    state_data_to_save = request.data.copy()

    if PROMPT_TEXT:
        print(f"[State] 프롬프트: {PROMPT_TEXT}")
        print(f"[State] 모델 호출 중...")

        # 모델 호출하여 액션 생성
        generated_action = generate_action(
            prompt=PROMPT_TEXT,
            screenshot=request.data.get("screenshot", ""),
            ui_state=request.data.get("ui_state", {})
        )

        state_data_to_save["generated_action"] = generated_action
        print(f"[State] 모델 액션 생성 완료: {generated_action['actions_file']}")

    # state.json 저장
    save_path = os.path.join(os.path.dirname(__file__), "state.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(state_data_to_save, f, ensure_ascii=False, indent=2)

    return {"ok": True, "message": "state.json 저장 완료", "path": save_path}
```

### 3단계: 테스트

1. 백엔드 재시작:
```bash
cd C:\Users\김민영\Desktop\Jong-Back\backend
uvicorn Api:app --reload --port 8000
```

2. 실행 웹 실행:
```bash
cd C:\Users\김민영\Desktop\jong2
python execution_web_service.py
```

3. 프롬프트 웹 실행:
```bash
cd C:\Users\김민영\my-chat-ui
npm run dev
```

4. 테스트 시나리오:
   - 로그인 수행
   - 프롬프트 입력 (예: "성적 조회")
   - 백엔드 터미널에서 모델 호출 로그 확인
   - 실행 웹에서 생성된 액션 실행 확인

---

## 주의사항

### 1. **스크린샷 크기**
- base64 인코딩된 스크린샷은 매우 큽니다 (평균 500KB ~ 2MB)
- 모델 API에 전송 시 payload 크기 제한 확인 필요
- 필요하면 이미지 압축 또는 리사이징 고려

### 2. **응답 시간**
- 모델 호출에 시간이 걸릴 수 있습니다 (수 초 ~ 수십 초)
- 프론트엔드의 타임아웃 설정 확인 (현재 30초)
- 필요하면 `Api.py:71`의 타임아웃 값 조정

### 3. **Trajectory 파일 저장 위치**
- 모델이 생성한 trajectory 파일은 반드시 `jong2/` 디렉토리에 저장
- 파일명은 `trajectory_*.json` 형식 권장

### 4. **오류 처리**
- 모델 호출 실패 시 폴백 메커니즘 구현 권장
- 예: 모델 실패 시 기본 액션 반환 또는 사용자에게 오류 알림

---

## 예시: 완전한 모델 통합 코드

```python
# Jong-Back/backend/model.py

import json
import requests
from pathlib import Path

MODEL_API_URL = "http://your-model-api:5000/generate"  # 모델 API URL

def generate_action(prompt: str, screenshot: str, ui_state: dict) -> dict:
    """모델을 호출하여 액션 생성"""

    try:
        # 모델 API 호출
        response = requests.post(
            MODEL_API_URL,
            json={
                "prompt": prompt,
                "screenshot": screenshot,
                "ui_state": ui_state
            },
            timeout=60  # 모델 응답 대기 시간
        )

        if response.status_code != 200:
            raise Exception(f"모델 API 오류: {response.status_code}")

        model_output = response.json()
        trajectory_data = model_output["trajectory"]  # 모델이 생성한 액션 시퀀스

        # Trajectory 파일 저장
        filename = f"trajectory_{prompt.replace(' ', '_')}_{int(time.time())}.json"
        trajectory_path = Path(__file__).parent.parent.parent / "jong2" / filename

        with open(trajectory_path, "w", encoding="utf-8") as f:
            json.dump(trajectory_data, f, ensure_ascii=False, indent=2)

        print(f"[모델] Trajectory 파일 생성: {filename}")

        return {
            "type": "trajectory",
            "actions_file": filename,
            "description": f"{prompt} 자동 생성 액션"
        }

    except Exception as e:
        print(f"[모델 오류] {e}")
        # 폴백: 기본 액션 반환
        return {
            "type": "trajectory",
            "actions_file": "trajectory_student_check.json",
            "description": f"{prompt} (기본 액션)"
        }
```

---

## 참고 파일

- **실행 웹**: `jong2/execution_web_service.py` - 스크린샷 캡처 로직 (line 170-198)
- **백엔드**: `Jong-Back/backend/Api.py` - 모델 통합 지점 (line 92-164)
- **UI 상태 수집**: `jong2/scrape.py` - UI 상태 수집 함수
- **액션 실행**: `jong2/explaywright.py` - ActionExecutor 클래스

---

## 문의

모델 통합 중 문제가 발생하면:
1. 백엔드 터미널 로그 확인
2. 실행 웹 터미널 로그 확인
3. `Jong-Back/backend/state.json` 파일 내용 확인
