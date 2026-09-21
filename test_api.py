import requests
import json
import time

BASE_URL = 'http://localhost:8000'

def test_status():
    print("Testing /db_status...")
    resp = requests.get(f"{BASE_URL}/db_status")
    print(resp.status_code, resp.json())
    assert resp.status_code == 200

def test_cambiar_empresa():
    print("Testing /cambiar_empresa (valid)...")
    resp = requests.post(f"{BASE_URL}/cambiar_empresa", json={"sender": "TEST_USER", "empresa": "SBA_PROD"})
    print(resp.status_code, resp.json())
    assert resp.status_code == 200
    
def test_cambiar_empresa_invalid():
    print("Testing /cambiar_empresa (missing sender)...")
    resp = requests.post(f"{BASE_URL}/cambiar_empresa", json={"empresa": "SBA_PROD"})
    print(resp.status_code, resp.json())
    assert resp.status_code == 400

def test_webhook_no_empresa():
    print("Testing /webhook (without setting empresa for new user)...")
    resp = requests.post(f"{BASE_URL}/webhook", json={"sender": "TEST_USER_2", "message": "Hola"})
    print(resp.status_code, resp.json())
    # The webhook defaults to None if no session
    # We expect it to respond normally, possibly asking to select an enterprise

def test_webhook_with_empresa():
    print("Testing /webhook (with empresa)...")
    resp = requests.post(f"{BASE_URL}/webhook", json={"sender": "TEST_USER", "message": "¿Cuantas facturas hay?"})
    print(resp.status_code, resp.json())

def test_registrar_destinatario():
    print("Testing /registrar_destinatario...")
    resp = requests.post(f"{BASE_URL}/registrar_destinatario", json={"destino": "12345@c.us"})
    print(resp.status_code, resp.json())
    assert resp.status_code == 200

if __name__ == '__main__':
    test_status()
    test_cambiar_empresa()
    test_cambiar_empresa_invalid()
    test_registrar_destinatario()
    test_webhook_no_empresa()
    test_webhook_with_empresa()
    print("ALL API TESTS PASSED!")
