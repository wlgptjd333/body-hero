# -*- coding: utf-8 -*-
"""게임 리빌딩용 모델 학습.
논문 반복 비교 실험(재실험_2x2_증강수정/run_experiment.py)과 같은 구조·설정·고정 분할·증강(실제 거울상: x 반전 + 좌우 관절 교환 + 라벨 교환)을 쓰고,
선택적으로 실플레이 1회 기록(대기 블록)의 '대기' 프레임을 학습 데이터에 더한다(오른발 앞 준비 자세가 학습 데이터 대기에 9%뿐이라서).
사용: python train_game_model.py --seed 44 [--add-idle 세션폴더 ...] --out 모델경로
- 실플레이 대기 프레임은 60프레임씩 끊어 '대기' 녹화본으로 추가하고, 모두 학습 쪽에만 넣는다(검증 분할은 그대로)."""
import argparse, json, os, sys, time
ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=44)
ap.add_argument("--add-idle", nargs="*", default=[])
ap.add_argument("--out", required=True)
ap.add_argument("--threads", type=int, default=3)
a = ap.parse_args()
os.environ["BH_THREADS"] = str(a.threads); os.environ["BH_SEQ"] = "4"; os.environ["BH_ARCH"] = "gap"; os.environ["BH_SEEDS"] = str(a.seed)
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "재실험_2x2_증강수정", "run_experiment.py")
src = open(SRC, encoding="utf-8").read()
cut = src.index('print("\\nPreparing validation sets...")')
g = {"__file__": SRC, "__name__": "train_game_model"}
exec(compile(src[:cut], SRC, "exec"), g)
np = g["np"]; tf = g["tf"]
sys.path.insert(0, HERE)
import lab_common as L

added = []
for d in a.add_idle:
    recs, _ = L.load_jsonl(os.path.join(d, "frames.jsonl"))
    import csv
    blocks = [b for b in csv.DictReader(open(os.path.join(d, "blocks.csv"), encoding="utf-8")) if b["kind"] == "idle" and b["completed"] == "1"]
    for b in blocks:
        seg = []
        for r in recs:
            if not (float(b["t_start"]) <= r["t"] < float(b["t_end"])):
                continue
            if r["k"] == "c":
                seg = []
            elif r["k"] == "a":
                seg.append(r["d"])
                if len(seg) == 60:
                    added.append(np.asarray(seg, np.float32)); seg = []
X_all = g["X_all"]; labels_all = g["labels_all"]; recordings = g["recordings"]; train_ids = list(g["train_record_ids"])
for arr in added:
    start = len(X_all)
    X_all = np.concatenate([X_all, arr]); labels_all = np.concatenate([labels_all, np.asarray(["none"] * len(arr), dtype=object)])
    recordings.append({"label": "none", "start_index": start, "frame_count": 60, "source": "realplay"})
    train_ids.append(len(recordings) - 1)
g["X_all"] = X_all; g["labels_all"] = labels_all; g["recordings"] = recordings
print(f"실플레이 대기 녹화본 {len(added)}개 추가 (학습 쪽)", flush=True)

seed = a.seed
os.environ["PYTHONHASHSEED"] = str(seed)
import random
random.seed(seed); np.random.seed(seed); tf.random.set_seed(seed)
Xtr, ytr, ctr, rtr = g["extract_sequences"](train_ids, 4)
Xva, yva, _, _ = g["extract_sequences"](g["val_record_ids"], 4)
Xtr, ytr, _, _ = g["balance_sequences"](Xtr, ytr, ctr, rtr, seed)
Xtr, ytr = g["augment_training_data"](Xtr, ytr, seed)
model = g["build_model"](4, "gap")
cb = [tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=g["EARLY_STOP_PATIENCE"], restore_best_weights=True, verbose=1),
      tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=g["LR_PATIENCE"], min_lr=1e-6, verbose=1)]
t0 = time.time()
model.fit(Xtr, ytr, validation_data=(Xva, yva), epochs=g["EPOCHS"], batch_size=g["BATCH_SIZE"], shuffle=True, callbacks=cb, verbose=2)
acc = float((model.predict(Xva, batch_size=4096, verbose=0).argmax(1) == yva).mean())
model.save(a.out)
info = {"seed": seed, "added_idle_recordings": len(added), "added_from": [os.path.basename(x.rstrip("/\\")) for x in a.add_idle],
        "val_accuracy_fixed_split": round(acc * 100, 2), "train_seconds": round(time.time() - t0), "keras": tf.keras.__version__ if hasattr(tf.keras, "__version__") else None,
        "tensorflow": tf.__version__, "config": "재실험_2x2_증강수정/run_experiment.py와 같음(GAP 4프레임, 고정 분할, 실제 거울상 증강)"}
json.dump(info, open(a.out + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(info, ensure_ascii=False), flush=True)
