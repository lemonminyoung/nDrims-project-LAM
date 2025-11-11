import requests
import time

COMMAND_URL = "http://127.0.0.1:8000/command"

def poll_command():
    while True:
        try:
            resp = requests.get(COMMAND_URL, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("has_task"):
                    print("=== 새 프롬프트 수신 ===")
                    text = data.get("text", "")
                    typ = data.get("type", "")
                    if typ == "login":
                        print("[명령] 로그인 요청")
                    elif typ == "state":
                        print("[명령] 상태 요청 ")
                    elif typ == "action":
                        print("[명령] 액션 명령")
                    else:
                        print("[명령] 알 수 없는 타입:", typ)
                    print(f"text: {text}")
                    print(f"type: {typ}")
                else:
                    print("대기 중 프롬프트 없음")
            else:
                print(f"Error: Received status code {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Exception occurred: {e}")
        time.sleep(5)

if __name__ == "__main__":
    poll_command()
