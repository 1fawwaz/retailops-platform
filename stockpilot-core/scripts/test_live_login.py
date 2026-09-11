import json
import os
import urllib.error
import urllib.parse
import urllib.request


def test_login(url: str, email: str, password: str) -> None:
    data = urllib.parse.urlencode({"username": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/auth/login",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            token_len = len(body.get("access_token", ""))
            print(f"SUCCESS on {url}: access_token received (length={token_len})")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"HTTPError {e.code} on {url}: {err_body}")
    except Exception as e:
        print(f"Exception on {url}: {e}")


if __name__ == "__main__":
    demo_email = os.getenv("DEMO_USER_EMAIL", "demo@retailops.local")
    demo_password = os.getenv("DEMO_USER_PASSWORD", "demo-password-placeholder")

    print("Testing local API...")
    test_login("http://localhost:8000", demo_email, demo_password)

    print("\nTesting production API (Render)...")
    test_login("https://retail-hta8.onrender.com", demo_email, demo_password)
