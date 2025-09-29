def test_get_generate_qr(client):
    response = client.get("/generateqr")
    assert response.status_code == 200

def test_post_generate_qr(client):
    request_body = {"url": "https://www.google.com"}
    response = client.post("/generateqr", data=request_body)
    assert response.status_code == 200
