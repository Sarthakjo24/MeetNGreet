import os

from locust import HttpUser, between, task


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "meetngreet_session")
COOKIE_VALUE = os.getenv("SESSION_COOKIE", "")


class CandidateFlowUser(HttpUser):
    wait_time = between(0.2, 1.0)
    host = BASE_URL

    def _auth_headers(self):
        if not COOKIE_VALUE:
            return {}
        return {"Cookie": f"{COOKIE_NAME}={COOKIE_VALUE}"}

    @task
    def complete_session(self):
        response = self.client.post(
            "/api/candidates/start",
            headers=self._auth_headers(),
        )
        if response.status_code != 200:
            return
        payload = response.json()
        session_id = payload.get("session_id")
        questions = payload.get("questions") or []
        if not session_id:
            return

        for question in questions:
            question_id = question.get("question_id")
            if not question_id:
                continue

            data = {
                "session_id": session_id,
                "question_id": question_id,
                "transcript_hint": "Load test answer.",
            }
            with open("loadtest/fixtures/sample.webm", "rb") as handle:
                files = {
                    "media_file": ("sample.webm", handle, "video/webm"),
                }
                self.client.post(
                    "/api/responses/upload",
                    data=data,
                    files=files,
                    headers=self._auth_headers(),
                )
