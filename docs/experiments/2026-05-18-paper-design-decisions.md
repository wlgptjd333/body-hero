# Design Decisions for Paper (2026-05-18)

## Overview

Body Hero is a webcam-based boxing game using MediaPipe Pose landmarks → neural network → action recognition.
This document captures the reasoning behind each ML design decision for the paper.

---

## 1. seq_len = 4 (not 2, not 1)

### Why not 1 frame?
Single-frame models cannot distinguish between "holding a pose" and "transitioning through a pose."
A transition frame (e.g., arm halfway between idle and punch) looks like a weak version of either class,
causing false positives for "none" (idle) detection.

### Why not 2 frames?
2 frames (66ms) provide marginal temporal information. The improvement over 1 frame is small (~1%).
The Conv1D kernel operating on 2 frames with padding produces near-identical outputs at both positions,
effectively computing the same linear combination twice.

### Why 4 frames?
4 frames (132ms) provide enough temporal context for the Conv1D kernel (k=3) to see genuine temporal patterns.
Each output position blends 3 adjacent frames, capturing motion trajectories.
The key metric: none recall jumps from ~92% (1/2 frames) to 97.9% (4 frames), meaning the model
can now reliably distinguish "no action" from "preparing an action" by observing smoothness over time.

### Trade-off accepted
4-frame buffer adds 132ms latency. At 30fps this is 4 frames of delay.
Imperceptible in gameplay. The accuracy gain justifies the latency.

---

## 2. GlobalAveragePooling > LSTM

### Hypothesis disproven
We hypothesized that LSTM would capture temporal dynamics of boxing motions.
Result: LSTM never outperformed GAP at any seq_len, despite 60% more parameters.

### Why LSTM fails
- 4 time steps is insufficient for LSTM's gating mechanism to be useful
- LSTM has 4 gates × (input_dim + hidden_dim + bias) × hidden_dim = ~16K additional params
- These extra params cause overfitting on limited recording data (305 recordings)
- Conv1D(k=3, padding="same") already captures temporal blending at each position

### Why GAP works
GlobalAveragePooling averages the Conv1D output across time, producing one value per filter.
This forces the Conv1D filters to learn features that are consistently present across the 4-frame window,
acting as a temporal regularizer.

### Architectural implication
For actions shorter than ~200ms, a simple Conv1D → GAP is sufficient. LSTM/Rnn should be reserved
for actions with longer temporal dependencies (500ms+), which our dataset doesn't contain.

---

## 3. Augmentation Choices

### Which augmentations we use
| Augmentation | Used? | Why |
|-------------|-------|-----|
| Gaussian noise (σ=0.03) | Yes | Camera sensor noise, landmark jitter |
| Scale (±20%) | Yes | Player-camera distance variation |
| Horizontal flip + L/R swap | Yes | Left/right data imbalance, doubles effective data for symmetric classes |

### Which augmentations we DO NOT use (and why)
| Augmentation | Not used | Why |
|-------------|----------|-----|
| Rotation | No | Landmarks are already normalized to shoulder-center coordinates. Rotation would distort realistic body geometry. |
| Translation | No | Landmark coordinates are relative to shoulder center, already translation-invariant. |
| Temporal masking | No | All recordings are clean single-action takes (60 frames of only "guard", only "punch", etc.). No unrelated segments to mask. |
| Time-warping | No | Each recording has consistent action speed. Warping would create unrealistic motion artifacts. |

### Flip augmentation effect
Adding flip augmentation improved accuracy by +0.69% (96.12% → 96.81%) in seq_len=2 experiments.
The effect comes from:
- Doubling effective data for L/R symmetric classes (punch_l/r, upper_l/r)
- Reducing L/R confusion (which was already low at 0% in final model)

---

## 4. Recording-Based Evaluation Protocol

### Why random train/val split is misleading
Standard practice: randomly split frames 80/20. This causes data leakage because:
- Frame t and frame t+1 from the same recording are virtually identical (~33ms apart)
- The model sees near-duplicates in both train and val sets
- Result: inflated accuracy (we saw 99.8% validation accuracy with random split)

### Our approach: recording-based holdout
We split by entire recordings: 80% of recordings → train, 20% → test.
This ensures no temporal correlation between train and test sets.
Result: our 97.53% ablation accuracy reflects real generalization.

### Paper recommendation
Report both metrics with clear methodology:
- Internal validation (random split): 99.8% — for comparison with literature
- Recording-based holdout: 97.53% — for real generalization estimate

---

## 5. Class Imbalance and Metric Choice

### Class distribution
The dataset has 305 recordings × 60 frames = ~18,300 labeled frames per class on average.
Some classes have fewer recordings (squat: 27, upper_l/upper_r: 35 each vs none: 76).
We use `class_weight="balanced"` in training loss to handle this.

### Why "none" recall is the most important metric
In a boxing game:
- False positive (model predicts a punch when player is idle) → **immediately noticeable, frustrating**
- False negative (model misses a real punch) → player adjusts by punching harder

Therefore we optimize for high "none" recall (minimize false positives) even at the cost of
lower individual action recall. Our final model achieves 97.9% none recall while maintaining
>85% recall for all action classes.

### Why punch_r recall varies across models
Punch_r (right punch) consistently has lower recall than punch_l across all models tested.
This is likely because:
- The dataset may have subtle bias in right-punch recording quality
- Right-handed players may execute more consistent left-hand motions
- Shoulder landmark occlusion differs between left/right during punching

The trade-off between punch_r recall and none recall is visible in our ablation:
models with high punch_r recall (94%) had low none recall (92%), and vice versa.
We chose the model with high none recall because false positives degrade gameplay more than false negatives.

---

## 6. Architecture Selection Summary

### Final model
```
Input: (4, 99)  — 4 frames × 33 landmarks × 3 coordinates
Conv1D(64 filters, kernel=3, padding="same", activation="relu")
BatchNormalization
Dropout(0.25)
GlobalAveragePooling1D
Dropout(0.3)
Dense(7, activation="softmax")  — 7 action classes
Total params: ~20K
```

### Why this architecture
- Minimal params for the dataset size (~18K labeled frames)
- No fully connected layers before the classifier (GAP → softmax)
- Uses temporal information via Conv1D without over-parameterizing (cf. LSTM)
- Proven robust across 5 training runs with <1% accuracy variance

### Training details
- Optimizer: Adam (lr=1e-3)
- Early stopping: patience=15 on val_loss
- ReduceLROnPlateau: factor=0.5, patience=6
- Batch size: 32
- Epochs: 56 (early stopped)
- Training time: ~6 minutes on CPU
