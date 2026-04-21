import os
import requests
import pytest
from dotenv import load_dotenv

load_dotenv()

def test_qweather_now():
    print('QWEATHER_API_KEY:', os.getenv("QWEATHER_API_KEY"))
    print('QWEATHER_API_HOST:', os.getenv("QWEATHER_API_HOST"))
    api_key = os.getenv("QWEATHER_API_KEY")
    api_host = os.getenv("QWEATHER_API_HOST")
    assert api_key, "QWEATHER_API_KEY not set"
    assert api_host, "QWEATHER_API_HOST not set"
    url = f"https://{api_host}/v7/weather/now"
    params = {
        "location": "101010100",  # Beijing city ID
        "key": api_key
    }
    resp = requests.get(url, params=params)
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data
    assert data["code"] == "200"
    assert "now" in data

if __name__ == "__main__":
    test_qweather_now()
    print("QWeather now API test passed.")
