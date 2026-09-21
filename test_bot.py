import requests
import json

url = "http://localhost:8000/webhook"
payload = {
    "sender": "85440572964888",
    "message": "¿Cuál es la factura con el monto más grande?"
}

print("Enviando petición de prueba a localhost:8000...")
response = requests.post(url, json=payload)
print(f"Status Code: {response.status_code}")
print("Response JSON:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
