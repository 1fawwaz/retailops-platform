import json
import urllib.parse
import urllib.request


def test_login(url, email, password):
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
            print(
                f"SUCCESS on {url}: access_token received (length={len(body.get('access_token', ''))})"
            )
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"HTTPError {e.code} on {url}: {err_body}")
    except Exception as e:
        print(f"Exception on {url}: {e}")


if __name__ == "__main__":
    print("Testing local API...")
    test_login("http://localhost:8000", "demo@retailops.local", "_awv1jRthdu2YNJzao9CyA")
    test_login("http://localhost:8000", "test@test.com", "testpassword123")

    print("\nTesting production API (Render)...")
    test_login(
        "https://stockpilot-core.onrender.com", "demo@retailops.local", "_awv1jRthdu2YNJzao9CyA"
    )
    test_login("https://stockpilot-core.onrender.com", "test@test.com", "testpassword123")
