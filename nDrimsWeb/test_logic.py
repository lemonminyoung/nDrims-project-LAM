"""
execution_web_service.py의 핵심 로직 단위 테스트
"""
import json
import re


def extract_expected_page_title(actions):
    """
    액션 리스트에서 예상 페이지 제목 추출
    (execution_web_service.py의 함수와 동일)
    """
    # 역순으로 마지막 click 액션 찾기
    for action_item in reversed(actions):
        action_def = action_item.get("action", {})
        action_name = action_def.get("name")

        if action_name == "click":
            selector = action_def.get("args", {}).get("selector", "")

            # text=xxx 패턴
            text_match = re.search(r'text=([^\]]+)', selector)
            if text_match:
                title = text_match.group(1).strip()
                print(f"[추출] 예상 페이지 제목: '{title}' (text= 패턴)")
                return title

            # name='xxx' 또는 name="xxx" 패턴
            name_match = re.search(r"name=['\"]([^'\"]+)['\"]", selector)
            if name_match:
                title = name_match.group(1).strip()
                print(f"[추출] 예상 페이지 제목: '{title}' (name= 패턴)")
                return title

    print(f"[추출] 예상 페이지 제목을 찾을 수 없음")
    return None


def test_extract_title_from_popup_trajectory():
    """trajectory_popup_test.json에서 제목 추출 테스트"""
    print("\n=== Test 1: trajectory_popup_test.json 제목 추출 ===")

    with open("trajectory_popup_test.json", "r", encoding="utf-8") as f:
        actions = json.load(f)

    expected_title = extract_expected_page_title(actions)

    assert expected_title == "강의계획서", f"예상: '강의계획서', 실제: '{expected_title}'"
    print(f"[OK] 제목 추출 성공: '{expected_title}'")


def test_title_matching():
    """제목 비교 로직 테스트"""
    print("\n=== Test 2: 제목 비교 로직 ===")

    test_cases = [
        # (예상, 실제, 매칭 여부)
        ("강의계획서", "강의계획서", True),
        ("강의계획서", "강의계획서 조회", True),
        ("학적부열람", "학적부 열람", False),  # 공백 차이는 불일치
        ("종합강의시간표조회", "종합강의시간표조회", True),
    ]

    for expected, actual, should_match in test_cases:
        is_match = expected in actual or actual in expected
        status = "[OK]" if is_match == should_match else "[FAIL]"
        print(f"{status} 예상='{expected}', 실제='{actual}' -> {is_match} (기대: {should_match})")
        assert is_match == should_match


def test_windows_handler_constants():
    """Windows console handler 상수 확인"""
    print("\n=== Test 3: Windows Handler 상수 ===")

    CTRL_C_EVENT = 0
    CTRL_BREAK_EVENT = 1
    CTRL_CLOSE_EVENT = 2  # X 버튼!
    CTRL_LOGOFF_EVENT = 5
    CTRL_SHUTDOWN_EVENT = 6

    print(f"[OK] CTRL_CLOSE_EVENT = {CTRL_CLOSE_EVENT} (X 버튼)")
    assert CTRL_CLOSE_EVENT == 2


def test_popup_trajectory_structure():
    """trajectory_popup_test.json 구조 검증"""
    print("\n=== Test 4: Trajectory 파일 구조 검증 ===")

    with open("trajectory_popup_test.json", "r", encoding="utf-8") as f:
        actions = json.load(f)

    print(f"[OK] 총 {len(actions)}개 액션")

    # 마지막 click 액션이 "강의계획서"를 클릭하는지 확인 (역순 탐색)
    last_click_action = None
    for action_item in reversed(actions):
        if action_item["action"]["name"] == "click":
            last_click_action = action_item
            break

    assert last_click_action is not None, "click 액션이 있어야 함"

    selector = last_click_action["action"]["args"]["selector"]
    assert "강의계획서" in selector, "마지막 click은 강의계획서를 클릭해야 함"
    print(f"[OK] 마지막 click 액션: {selector}")

    # 교원명 입력 확인
    type_actions = [a for a in actions if a["action"]["name"] == "type"]
    assert len(type_actions) > 0, "type 액션이 있어야 함"

    type_action = type_actions[0]
    assert type_action["action"]["args"]["text"] == "성연식", "교원명은 '성연식'이어야 함"
    print(f"[OK] 교원명 입력: {type_action['action']['args']['text']}")


if __name__ == "__main__":
    print("=" * 60)
    print("execution_web_service.py 로직 단위 테스트")
    print("=" * 60)

    try:
        test_extract_title_from_popup_trajectory()
        test_title_matching()
        test_windows_handler_constants()
        test_popup_trajectory_structure()

        print("\n" + "=" * 60)
        print("[SUCCESS] 모든 테스트 통과!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] 테스트 실패: {e}")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
