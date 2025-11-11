"""
브라우저 상태 체크 기능 테스트
"""
import requests
import time

BACKEND_URL = "http://localhost:8000"


def check_status():
    """현재 실행 웹 및 브라우저 상태 확인"""
    try:
        response = requests.get(f"{BACKEND_URL}/execution_web/status", timeout=5)
        status = response.json()

        print("\n" + "=" * 60)
        print("실행 웹 및 브라우저 상태")
        print("=" * 60)
        print(f"실행 웹 연결:     {status.get('connected', False)}")
        print(f"마지막 폴링:     {status.get('last_poll_time', 'N/A')}")
        print(f"브라우저 실행:   {status.get('browser_running', False)}")
        print(f"브라우저 개수:   {status.get('browser_count', 0)}")
        print("=" * 60)

        # 상태 해석
        if not status.get('connected'):
            print("[상태] 실행 웹이 연결되어 있지 않습니다.")
        elif status.get('browser_running'):
            count = status.get('browser_count', 0)
            print(f"[상태] 브라우저 {count}개가 실행 중입니다.")
        else:
            print("[상태] 실행 웹은 연결되었지만 브라우저는 실행되지 않았습니다.")

        return status

    except requests.exceptions.ConnectionError:
        print("\n[오류] 백엔드 서버에 연결할 수 없습니다.")
        print("  → 백엔드가 실행 중인지 확인하세요: python Api.py")
        return None
    except Exception as e:
        print(f"\n[오류] 예외 발생: {e}")
        return None


def monitor_status(interval=2, duration=30):
    """
    브라우저 상태를 주기적으로 모니터링

    Args:
        interval: 체크 간격 (초)
        duration: 총 모니터링 시간 (초)
    """
    print(f"\n브라우저 상태 모니터링 시작 ({duration}초 동안 {interval}초마다 체크)")
    print("Ctrl+C를 눌러 중단할 수 있습니다.\n")

    start_time = time.time()

    try:
        while time.time() - start_time < duration:
            status = check_status()

            if status:
                # 간단한 로그
                connected = "O" if status.get('connected') else "X"
                browser = "O" if status.get('browser_running') else "X"
                count = status.get('browser_count', 0)
                print(f"[{time.strftime('%H:%M:%S')}] 연결:{connected} | 브라우저:{browser} | 개수:{count}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n모니터링 중단됨 (Ctrl+C)")


def test_lifecycle():
    """
    전체 라이프사이클 테스트

    테스트 순서:
    1. 실행 웹 연결 전 상태
    2. 실행 웹 시작 후 상태 (브라우저 없음)
    3. 로그인 후 상태 (브라우저 실행)
    4. 실행 웹 종료 후 상태
    """
    print("\n" + "=" * 60)
    print("브라우저 상태 라이프사이클 테스트")
    print("=" * 60)

    print("\n[1단계] 현재 상태 확인...")
    status = check_status()

    if not status:
        return

    if not status.get('connected'):
        print("\n→ 실행 웹이 연결되지 않았습니다.")
        print("  실행 웹을 시작하세요: python execution_web_service.py")
        return

    if status.get('browser_running'):
        print("\n→ 브라우저가 이미 실행 중입니다.")
        print(f"  브라우저 개수: {status.get('browser_count', 0)}")
    else:
        print("\n→ 실행 웹은 연결되었지만 브라우저는 없습니다.")
        print("  로그인을 하면 브라우저가 실행됩니다.")

    print("\n[2단계] 10초 동안 상태 모니터링...")
    monitor_status(interval=2, duration=10)

    print("\n테스트 완료!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "check":
            # 한 번만 체크
            check_status()

        elif command == "monitor":
            # 계속 모니터링
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            interval = int(sys.argv[3]) if len(sys.argv) > 3 else 2
            monitor_status(interval=interval, duration=duration)

        elif command == "test":
            # 라이프사이클 테스트
            test_lifecycle()

        else:
            print(f"알 수 없는 명령: {command}")
            print("\n사용법:")
            print("  python test_browser_status.py check              # 한 번 체크")
            print("  python test_browser_status.py monitor [초]       # 모니터링 (기본: 60초)")
            print("  python test_browser_status.py test               # 라이프사이클 테스트")
    else:
        # 인자 없으면 한 번 체크
        check_status()
