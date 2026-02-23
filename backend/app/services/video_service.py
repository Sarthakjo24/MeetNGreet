from pathlib import Path


class VideoAnalysisService:
    def __init__(self) -> None:
        try:
            import cv2  # noqa: F401

            self.cv2_available = True
        except Exception:
            self.cv2_available = False

    def analyze(self, media_path: str) -> dict[str, float]:
        default_metrics = {
            "face_presence_ratio": 0.5,
            "smile_ratio": 0.5,
            "gaze_center_ratio": 0.5,
            "seriousness_ratio": 0.5,
        }

        if not self.cv2_available:
            return default_metrics

        path = Path(media_path)
        if not path.exists():
            return default_metrics

        try:
            import cv2

            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")

            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                return default_metrics

            frame_counter = 0
            sampled_frames = 0
            face_frames = 0
            smile_frames = 0
            centered_face_frames = 0

            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                frame_counter += 1
                if frame_counter % 12 != 0:
                    continue

                sampled_frames += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 5)

                if len(faces) == 0:
                    continue

                face_frames += 1
                largest_face = sorted(faces, key=lambda x: x[2] * x[3], reverse=True)[0]
                x, y, w, h = largest_face

                frame_h, frame_w = gray.shape
                face_center_x = x + (w / 2)
                frame_center_x = frame_w / 2
                if abs(face_center_x - frame_center_x) / frame_w <= 0.2:
                    centered_face_frames += 1

                roi = gray[y : y + h, x : x + w]
                smiles = smile_cascade.detectMultiScale(roi, 1.7, 20)
                if len(smiles) > 0:
                    smile_frames += 1

            cap.release()

            if sampled_frames == 0:
                return default_metrics

            face_presence_ratio = face_frames / sampled_frames
            smile_ratio = smile_frames / max(face_frames, 1)
            gaze_center_ratio = centered_face_frames / max(face_frames, 1)

            # Higher ratio means candidate appears composed and not laughing loudly.
            seriousness_ratio = 1.0 - min(smile_ratio, 0.85)

            return {
                "face_presence_ratio": round(max(0.0, min(face_presence_ratio, 1.0)), 3),
                "smile_ratio": round(max(0.0, min(smile_ratio, 1.0)), 3),
                "gaze_center_ratio": round(max(0.0, min(gaze_center_ratio, 1.0)), 3),
                "seriousness_ratio": round(max(0.0, min(seriousness_ratio, 1.0)), 3),
            }
        except Exception:
            return default_metrics
