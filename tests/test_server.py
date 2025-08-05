from fastapi.testclient import TestClient
from src.server.main import app

client = TestClient(app, base_url="http://localhost")


def test_tokencount_valid():
    response = client.post("/tokencount", json={"input_text": "Hello world!", "model_id": "openai-community/gpt2"}, headers={"host": "localhost"})
    if response.status_code != 200:
        print("Response content:", response.content)
    assert response.status_code == 200
    data = response.json()
    assert "token_count" in data
    assert isinstance(data["token_count"], int)
    assert data["token_count"] > 0

def test_tokencount_missing_input():
    response = client.post("/tokencount", json={"model_id": "openai-community/gpt2"}, headers={"host": "localhost"})
    if response.status_code != 400:
        print("Response content:", response.content)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data 