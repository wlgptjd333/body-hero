"""
포즈 분류 추론 서버: 시퀀스(8프레임) + 가드만 단일 프레임 폴백.
- 가드는 "유지" 동작이라 시퀀스에서 잘 안 잡힘 → 시퀀스의 마지막 프레임으로 단일 프레임 모델을 돌려
  guard면 guard 반환 (빠른 인식·유지 가능).
- 나머지 동작은 시퀀스 모델로만 판정.

필요: pose_classifier_seq.keras (필수), pose_classifier.keras (가드 폴백용, 있으면 사용)
가드 폴백 모델이 없으면 시퀀스만 사용. 단일 프레임 모델은 train_pose_classifier.py 로 생성.

실행: cd tools → python pose_server.py
"""
import os
import sys
import threading

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = os.path.join(SCRIPT_DIR, "pose_classifier_seq.keras")
DEFAULT_MODEL_SINGLE = os.path.join(SCRIPT_DIR, "pose_classifier.keras")
SEQ_LEN = 8
CLASS_NAMES = ["none", "guard", "jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r"]
GUARD_INDEX = 1
DEFAULT_CONFIDENCE_THRESHOLD = 0.95
# 가드 폴백: 단일 프레임에서 이 확신 이상이면 guard 반환 (시퀀스 결과 무시)
DEFAULT_GUARD_FALLBACK_THRESHOLD = 0.50

try:
    import numpy as np
    import tensorflow as tf
    from flask import Flask, request, jsonify
except ImportError as e:
    print("pip install tensorflow flask numpy")
    raise SystemExit(1) from e

app = Flask(__name__)
_model = None
_model_single = None
_confidence_threshold = DEFAULT_CONFIDENCE_THRESHOLD
_guard_fallback_threshold = DEFAULT_GUARD_FALLBACK_THRESHOLD
_predict_lock = threading.Lock()


def load_model(path=None):
    global _model
    path = path or DEFAULT_MODEL
    if not os.path.isfile(path):
        raise FileNotFoundError(f"모델 파일 없음: {path} (먼저 train_pose_classifier_seq.py 실행)")
    _model = tf.keras.models.load_model(path)
    return _model


def load_model_single(path=None):
    global _model_single
    path = path or DEFAULT_MODEL_SINGLE
    if not os.path.isfile(path):
        return None
    _model_single = tf.keras.models.load_model(path)
    return _model_single


@app.route("/predict", methods=["POST"])
def predict():
    global _model, _model_single
    if _model is None:
        try:
            load_model()
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 500

    data = request.get_json()
    if not data or "sequence" not in data:
        return jsonify({"error": f"sequence ({SEQ_LEN} frames × 99 floats) required"}), 400

    sequence = data["sequence"]
    if not isinstance(sequence, (list, tuple)) or len(sequence) != SEQ_LEN:
        return jsonify({"error": f"sequence must be list of {SEQ_LEN} frames"}), 400
    for i, frame in enumerate(sequence):
        if len(frame) != 99:
            return jsonify({"error": f"frame[{i}] must have 99 elements"}), 400

    sequence = list(sequence)
    last_frame = np.array(sequence[-1], dtype=np.float32).reshape(1, -1)

    # 가드 폴백: 단일 프레임 모델로 마지막 프레임만 보고 guard면 guard 반환 (유지·느린 올리기 대응)
    if _model_single is not None:
        with _predict_lock:
            single_pred = _model_single.predict(last_frame, verbose=0)[0]
        single_idx = int(np.argmax(single_pred))
        single_conf = float(single_pred[single_idx])
        if single_idx == GUARD_INDEX and single_conf >= _guard_fallback_threshold:
            return jsonify({"result": "guard", "confidence": single_conf})

    X = np.array(sequence, dtype=np.float32).reshape(1, SEQ_LEN, -1)
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
    return jsonify({"status": "ok", "model_loaded": _model is not None, "guard_fallback_loaded": _model_single is not None})


def main():
    global _confidence_threshold, _guard_fallback_threshold
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="시퀀스 모델 (필수)")
    parser.add_argument("--model-single", default=DEFAULT_MODEL_SINGLE, help="가드 폴백용 단일 프레임 모델 (있으면 사용)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD, help="Min confidence (below → none)")
    parser.add_argument("--guard-threshold", type=float, default=DEFAULT_GUARD_FALLBACK_THRESHOLD, help="가드 폴백 확신 하한")
    args = parser.parse_args()
    _confidence_threshold = args.threshold
    _guard_fallback_threshold = args.guard_threshold
    try:
        load_model(args.model)
        load_model_single(args.model_single)
        guard_ok = "가드 폴백 O" if _model_single is not None else "가드 폴백 X (pose_classifier.keras 없음)"
        print(f"시퀀스 모델 로드됨. {guard_ok}. POST http://127.0.0.1:{args.port}/predict")
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)
    app.run(host="127.0.0.1", port=args.port, threaded=True)


if __name__ == "__main__":
    main()
