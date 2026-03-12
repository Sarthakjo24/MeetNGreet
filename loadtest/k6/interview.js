import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const COOKIE_NAME = __ENV.SESSION_COOKIE_NAME || "meetngreet_session";
const COOKIE_VALUE = __ENV.SESSION_COOKIE || "";
const MEDIA_BYTES = open("./loadtest/fixtures/sample.webm", "b");

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "1m", target: 50 },
        { duration: "2m", target: 200 },
        { duration: "1m", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
  },
};

function authHeaders() {
  if (!COOKIE_VALUE) {
    return {};
  }
  return {
    Cookie: `${COOKIE_NAME}=${COOKIE_VALUE}`,
  };
}

export default function () {
  const startRes = http.post(`${BASE_URL}/api/candidates/start`, null, {
    headers: authHeaders(),
  });
  check(startRes, { "start 200": (r) => r.status === 200 });
  if (startRes.status !== 200) {
    sleep(1);
    return;
  }

  const payload = startRes.json();
  const sessionId = payload.session_id;
  const questions = payload.questions || [];

  for (const question of questions) {
    const form = {
      session_id: sessionId,
      question_id: question.question_id,
      transcript_hint: "Load test answer.",
      media_file: http.file(MEDIA_BYTES, "sample.webm", "video/webm"),
    };
    const uploadRes = http.post(`${BASE_URL}/api/responses/upload`, form, {
      headers: authHeaders(),
    });
    check(uploadRes, { "upload 200": (r) => r.status === 200 });
  }

  sleep(1);
}
