"""
lm_studio_client.py - Lokaler Client fuer LM Studio (OpenAI-kompatible API).
Keine Cloud-Verbindung. Keine externen Dienste.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class LmStudioClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234/v1",
        model: str = "local-model",
        timeout_seconds: float = 60.0,
        temperature: float = 0.1,
        max_tokens: int = 1200,
        context_length: int = 4096,
        top_p: float = 0.95,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        stream: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_length = context_length
        self.top_p = top_p
        self.top_k = top_k
        self.repeat_penalty = repeat_penalty
        self.stream = stream

    def analyze(self, system_prompt: str, user_message: str):
        try:
            import httpx
        except ImportError:
            return "httpx ist nicht installiert.", False

        url = self.base_url + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
            "stream": self.stream,
            # Von LM Studio unterstuetzte Zusatzoption; falls ein Server sie
            # ignoriert, bleibt die Anfrage OpenAI-kompatibel.
            "n_ctx": self.context_length,
        }
        logger.info("LLM-Anfrage an %s (Modell: %s)", url, self.model)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            choices = data.get("choices", [])
            if not choices:
                return "LM Studio hat keine Antwort zurueckgegeben (leere choices).", False

            message = choices[0].get("message", {})
            content = message.get("content", "").strip()

            if not content:
                finish_reason = choices[0].get("finish_reason", "unbekannt")
                msg = (
                    "LM Studio hat leeren Inhalt zurueckgegeben.\n"
                    "finish_reason: " + str(finish_reason) + "\n"
                    "Hinweis: Bei Reasoning-Modellen kann der Inhalt leer sein."
                )
                return msg, False

            logger.info("LLM-Antwort empfangen (%d Zeichen)", len(content))
            return content, True

        except Exception as e:
            try:
                import httpx as _httpx
                if isinstance(e, _httpx.ConnectError):
                    msg = "LM Studio ist nicht erreichbar. Bitte pruefen ob LM Studio laeuft auf: " + self.base_url
                elif isinstance(e, _httpx.TimeoutException):
                    msg = "Timeout nach " + str(self.timeout_seconds) + "s. Modell antwortet nicht rechtzeitig."
                elif isinstance(e, _httpx.HTTPStatusError):
                    msg = "HTTP-Fehler: " + str(e.response.status_code) + " - " + str(e.response.text)
                else:
                    msg = "Unerwarteter Fehler: " + str(e)
            except Exception:
                msg = "Fehler bei LM-Studio-Anfrage: " + str(e)
            logger.error(msg)
            return msg, False

    def check_connection(self):
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                response = client.get(self.base_url + "/models")
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    model_str = ", ".join(models) if models else "keine"
                    return True, "LM Studio erreichbar. Modelle: " + model_str
                return False, "LM Studio antwortet mit Status " + str(response.status_code)
        except Exception as e:
            return False, "LM Studio nicht erreichbar: " + str(e)
