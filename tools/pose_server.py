"""
포즈 분류 추론 서버: POST /predict 에 정규화된 랜드마크(99 float)를 보내면
none, guard, jab_l, jab_r, upper_l, upper_r, hook_l, hook_r 중 하나를 반환합니다.
Godot 연동 시 웹캠 클라이언트가 이 서버를 호출한 뒤 UDP로 액션만 전송합니다.

실행: cd tools → python pose_server.py
기본 포트: 5000
"""
import os
import sys
import threading

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = os.path.join(SCRIPT_DIR, "pose_classifier.keras")
CLASS_NAMES = ["none", "guard", "jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r"]
# 확신이 이보다 낮으면 none 반환 (오판 감소). --threshold 로 변경 가능
DEFAULT_CONFIDENCE_THRESHOLD = 0.55

try:
    import numpy as np
    import tensorflow as tf
    from flask import Flask, request, jsonify
except ImportError as e:
    print("pip install tensorflow flask numpy")
    raise SystemExit(1) from e

app = Flask(__name__)
_model = None
_confidence_threshold = DEFAULT_CONFIDENCE_THRESHOLD
_predict_lock = threading.Lock()


def load_model(path=None):
    global _model
    path = path or DEFAULT_MODEL
    if not os.path.isfile(path):
        h5 = path.replace(".keras", ".h5") if path.endswith(".keras") else os.path.join(SCRIPT_DIR, "pose_classifier.h5")
        if os.path.isfile(h5):
            path = h5
        else:
            raise FileNotFoundError(f"모델 파일 없음: {path} (먼저 train_pose_classifier.py 실행)")
    _model = tf.keras.models.load_model(path)
    return _model


@app.route("/predict", methods=["POST"])
def predict():
    global _model
    if _model is None:
        try:
            load_model()
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 500

    data = request.get_json()
    if not data or "landmarks" not in data:
        return jsonify({"error": "landmarks (99 floats) required"}), 400

    landmarks = data["landmarks"]
    if len(landmarks) != 99:
        return jsonify({"error": "landmarks must have 99 elements"}), 400

    X = np.array(landmarks, dtype=np.float32).reshape(1, -1)
    with _predict_lock:
        pred = _model.predict(X, verbose=0)[0]
    idx = int(np.argmax(pred))
    conf = float(pred[idx])
    label = CLASS_NAMES[idx]
    if conf < _confidence_threshold:
        label = "none"
    return jsonify({"result": label, "confidence": conf})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model_loaded": _model is not None})


def main():
    global _confidence_threshold
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD, help="Min confidence (below → none)")
    args = parser.parse_args()
    _confidence_threshold = args.threshold
    try:
        load_model(args.model)
        print(f"모델 로드됨. POST http://127.0.0.1:{args.port}/predict (confidence threshold={_confidence_threshold})")
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)
    app.run(host="127.0.0.1", port=args.port, threaded=True)


if __name__ == "__main__":
    main()
