# Render 배포 업데이트 가이드

**업데이트 날짜:** 2025-11-18
**커밋:** ff97da7

---

## 📦 업데이트 내용

### 1. One-Action-at-a-Time 아키텍처 구현

백엔드가 한 번에 모든 액션을 생성하는 대신, **한 번에 하나의 액션**을 생성하고 실행 후 다음 액션을 생성하는 구조로 변경되었습니다.

**실행 흐름:**
```
1. 폴링 → /command → {type: "state"}
2. /state 전송 → 백엔드가 첫 액션 생성
3. 폴링 → /command → {type: "action"}
4. /action 실행 → 첫 번째 액션 실행
5. 폴링 → /command → {type: "state"} ← 다시 state 요청
6. /state 전송 → 백엔드가 두 번째 액션 생성
7. 반복...
N. 마지막 액션 (status: "FINISH") 실행 → 완료
```

### 2. 새로운 파일

#### `mock_action_model.py`
- AI 모델 없이 테스트할 수 있는 Mock 모델
- 3단계 액션 시퀀스 제공
- 마지막 액션에 자동으로 `status: "FINISH"` 추가

### 3. 주요 변경사항

#### `Api.py`

**추가된 전역 변수:**
```python
# 9~13줄
USE_MOCK_MODEL = True  # Mock 모드 설정

# 43~45줄
ACTION_SESSION_ACTIVE = False
ACTION_SESSION_REQUEST_ID = None
```

**수정된 엔드포인트:**

1. **`POST /state`** (248~380줄)
   - 세션이 없으면 초기화 + 첫 액션 생성
   - 세션이 있으면 다음 액션 생성
   - Mock/실제 모델 선택 가능

2. **`GET /action`** (438~527줄)
   - `action.status == "FINISH"` 확인
   - 마지막 액션이면 세션 종료 (TASK_TYPE=0)
   - 중간 액션이면 state 재요청 (TASK_TYPE=2)

---

## 🚀 Render 배포 확인

### 1. 자동 배포 확인

Render는 GitHub main 브랜치에 푸시되면 자동으로 배포됩니다.

**확인 방법:**
1. Render 대시보드 접속: https://dashboard.render.com
2. `nDrims-project-LAM` 서비스 선택
3. "Events" 탭에서 배포 진행 상황 확인

**기대 로그:**
```
==> Cloning from https://github.com/lemonminyoung/nDrims-project-LAM...
==> Downloading cache...
==> Starting service with 'uvicorn Api:app --host 0.0.0.0 --port $PORT'
==> Your service is live 🎉
```

### 2. 배포 후 테스트

배포가 완료되면 프론트엔드에서 바로 테스트할 수 있습니다.

**테스트 시나리오:**
1. 프론트엔드 접속
2. 로그인
3. 아무 프롬프트나 입력 (예: "학적부 조회")
4. 3개 액션이 순차 실행되는지 확인

**기대 동작:**
- 액션 1 실행 → 대기 → 액션 2 실행 → 대기 → 액션 3 실행 → 완료

---

## ⚙️ Mock 모드 vs 실제 모드

### 현재 설정: Mock 모드 (USE_MOCK_MODEL = True)

**장점:**
- ✅ AI 모델 없이도 전체 흐름 테스트 가능
- ✅ 즉시 테스트 가능
- ✅ 예측 가능한 3단계 액션

**단점:**
- ❌ 항상 동일한 액션만 실행
- ❌ 프롬프트에 따른 동적 액션 생성 불가

### 실제 모드로 전환 (나중에)

실제 AI 모델을 연결할 준비가 되면:

**Api.py (12줄) 수정:**
```python
USE_MOCK_MODEL = False  # ← False로 변경
```

**필요한 작업:**
1. `action_model_2.py` 파일 추가
2. 모델 파일 (weights) 업로드
3. requirements.txt에 모델 의존성 추가
4. Render에 푸시

---

## 🔍 배포 문제 해결

### 문제 1: 배포 실패

**증상:** Render 로그에 빌드 오류

**해결:**
1. Render 로그 확인
2. `requirements.txt` 의존성 확인
3. Python 버전 확인 (Render는 Python 3.11 기본)

### 문제 2: Mock 모델을 찾을 수 없음

**증상:** `ModuleNotFoundError: No module named 'mock_action_model'`

**해결:**
- `mock_action_model.py`가 `Api.py`와 같은 디렉토리에 있는지 확인
- Git에 정상 푸시되었는지 확인

### 문제 3: 액션이 실행되지 않음

**증상:** 프롬프트 입력 후 아무 반응 없음

**해결:**
1. Render 로그 확인: 백엔드에서 오류 발생하는지 체크
2. 실행 웹 연결 확인: `/execution_web/status` 엔드포인트 호출
3. 브라우저 콘솔 확인: 프론트엔드 오류 체크

### 문제 4: 무한 반복

**증상:** 액션이 계속 반복 실행됨

**해결:**
- 백엔드 로그에서 `TASK_TYPE` 값 확인
- 마지막 액션에 `status: "FINISH"` 포함되는지 확인
- `ACTION_SESSION_ACTIVE` 상태 확인

---

## 📊 Render 로그 확인

### 정상 로그 예시

```
[State] Mock 모델 사용 (테스트 모드)
[State] 새로운 액션 세션 초기화...
[Mock] 세션 초기화: 학적부 조회
[State] 세션 초기화 완료: 3 단계
[Mock] 액션 생성: step 1/3 - 메인 페이지로 이동
[State] 첫 액션 생성 완료

[Action] One-Action-at-a-Time 모드
[Action] 중간 액션 전달, TASK_TYPE=2로 변경

[State] 세션 진행 중, 다음 액션 생성
[Mock] 액션 생성: step 2/3 - 학적 메뉴 클릭

[Action] One-Action-at-a-Time 모드
[Action] 중간 액션 전달, TASK_TYPE=2로 변경

[State] 세션 진행 중, 다음 액션 생성
[Mock] 액션 생성: step 3/3 - 학적부열람 클릭
[Mock] 마지막 액션에 status='FINISH' 추가

[Action] One-Action-at-a-Time 모드
[Action] 마지막 액션 감지 (action.status: FINISH)
[Action] 마지막 액션 전달, 세션 종료
```

---

## 🎯 다음 단계

### 1. Mock 모드 테스트
- [ ] Render 배포 완료 확인
- [ ] 프론트엔드에서 프롬프트 입력
- [ ] 3단계 액션 순차 실행 확인
- [ ] 완료 메시지 출력 확인

### 2. 실제 모델 준비
- [ ] `action_model_2.py` 작성
- [ ] 모델 weights 업로드
- [ ] requirements.txt 업데이트
- [ ] `USE_MOCK_MODEL = False` 설정

### 3. 성능 최적화
- [ ] 액션 생성 속도 측정
- [ ] 메모리 사용량 모니터링
- [ ] 에러 핸들링 강화

---

## 📝 커밋 정보

**커밋 해시:** ff97da7
**브랜치:** main
**푸시 완료:** 2025-11-18

**변경된 파일:**
- `Api.py` (수정)
- `mock_action_model.py` (신규)

**GitHub 저장소:**
https://github.com/lemonminyoung/nDrims-project-LAM.git

---

**배포 완료! 🚀**

Render가 자동으로 배포를 시작합니다. 약 2-3분 후 프론트엔드에서 테스트 가능합니다.
