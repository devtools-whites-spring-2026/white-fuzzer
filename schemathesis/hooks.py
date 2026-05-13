# hooks.py
import requests
import schemathesis


@schemathesis.hook
def before_call(context, case, kwargs):
    response = requests.post(
        "http://127.0.0.1:80/api/token/",
        json={"username": "admin", "password": "password"},
    )
    hook_auth = response.json()["access"]
    case.headers["Authorization"] = f"Bearer {hook_auth}"
