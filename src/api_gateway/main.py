# bff/main.py
import os, uuid, time, requests
from flask import Flask, request, jsonify
LOYALTY_URL = os.getenv(
    "LOYALTY_URL",
    "https://misw4406-tocayos-loyalty-751220646299.us-central1.run.app/programas-lealtad/registrar-programa-lealtad"
)
SAGALOG_URL = os.getenv(
    "SAGALOG_URL",
    "https://misw4406-tocayos-sagalog-751220646299.us-central1.run.app"  
)

TIMEOUT = 5
RETRIES = 3
def _retry_request(method, url, **kwargs):
    """Reintento simple con backoff exponencial"""
    last_err = None
    for attempt in range(RETRIES):
        try:
            return requests.request(method, url, timeout=TIMEOUT, **kwargs)
        except requests.RequestException as e:
            last_err = e
            time.sleep(0.1 * (2 ** attempt))
    raise last_err
def create_app():
    app = Flask(__name__)
    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}, 200
    @app.post("/programs")
    def create_program():
        """
        Recibe el JSON del frontend y lo reenvía tal cual al endpoint de Loyalty.
        Devuelve 202 con sagaId para que la UI consulte el estado luego.
        """
        body = request.get_json(force=True, silent=True) or {}
        # Aseguramos que el payload tenga los mismos nombres que pide Loyalty
        payload = {
            "tipo":            body.get("tipo"),
            "categoria":       body.get("categoria"),
            "marca":           body.get("marca"),
            "audiencia":       body.get("audiencia"),
            "canales":         body.get("canales"),
            "inicio_programa": body.get("inicio_programa"),
            "final_programa":  body.get("final_programa"),
        }

        try:
            resp = _retry_request(
                "POST",
                LOYALTY_URL,
                headers={"Content-Type": "application/json"},
                json=payload
            )
            saga_id = resp.json().get("id")
            print(f"Received sagaId: {saga_id}")
    

        except Exception as e:
            # Aun si no logramos confirmar con Loyalty, devolvemos sagaId para que la UI pueda hacer polling
            return jsonify({
                "message": "Request aceptado; upstream no confirmado.",
                "sagaId": saga_id,
                "statusUrl": f"/sagas/{saga_id}"
            }), 202
        if 200 <= resp.status_code < 300:
            return jsonify({
                "sagaId": saga_id,
                "statusUrl": f"/sagas/{saga_id}",
                "loyaltyStatus": resp.status_code,
                "loyaltyResponse": (resp.json() if resp.content else {})
            }), 202
        return jsonify({
            "error": "loyalty_failed",
            "upstream": resp.status_code,
            "details": resp.text
        }), resp.status_code
    @app.route("/sagas/<saga_id>", methods=["GET"])
    def get_saga_status(saga_id):
        """
        Consulta estado de la saga en el Saga Log (tu coordinador).
        """
        try:
            r = _retry_request("GET", f"{SAGALOG_URL}/sagas/{saga_id}")
            return jsonify(r.json()), r.status_code
        except Exception as e:
            return jsonify({"error": "saga_log_unavailable", "details": str(e)}), 502
    return app
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)