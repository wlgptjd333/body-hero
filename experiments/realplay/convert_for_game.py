# -*- coding: utf-8 -*-
"""새 모델을 게임의 python_embed(Keras 3.12)에서 읽을 수 있게 다시 저장한다.
1단계(실험 환경, Keras 3.15): python convert_for_game.py export <모델.keras> <가중치.weights.h5>
2단계(게임 python_embed, Keras 3.12): python convert_for_game.py build <가중치.weights.h5> <출력.keras>
구조는 재실험_2x2_증강수정/run_experiment.py의 build_model(4, "gap")과 같다(층 이름 포함)."""
import os, sys
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np
import keras


def build():
    inp = keras.Input(shape=(4, 99), name="pose_sequence")
    x = keras.layers.Conv1D(64, kernel_size=3, padding="same", activation="relu", name="conv1d")(inp)
    x = keras.layers.BatchNormalization(name="batch_norm")(x)
    x = keras.layers.Dropout(0.25, name="dropout_conv")(x)
    x = keras.layers.GlobalAveragePooling1D(name="global_average_pooling")(x)
    x = keras.layers.Dropout(0.30, name="dropout_head")(x)
    out = keras.layers.Dense(7, activation="softmax", name="classifier")(x)
    return keras.Model(inp, out, name="gap_seq4")


mode = sys.argv[1]
if mode == "export":
    m = keras.models.load_model(sys.argv[2], compile=False)
    m.save_weights(sys.argv[3])
    np.save(sys.argv[3] + ".probe.npy", m.predict(np.random.default_rng(0).normal(size=(16, 4, 99)).astype("float32"), verbose=0))
    print("exported", keras.__version__)
elif mode == "build":
    m = build(); m.load_weights(sys.argv[2])
    probe = m.predict(np.random.default_rng(0).normal(size=(16, 4, 99)).astype("float32"), verbose=0)
    ref = np.load(sys.argv[2] + ".probe.npy")
    diff = float(np.abs(probe - ref).max())
    assert diff < 1e-5, diff
    m.save(sys.argv[3])
    keras.models.load_model(sys.argv[3], compile=False)
    print("built", keras.__version__, "max diff", diff)
