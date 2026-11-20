"""Create router embeddings, train the reviewed classifier, and evaluate it."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support
from sklearn.multiclass import OneVsRestClassifier


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from src.core.config import get_settings  # noqa: E402
from src.documents.embeddings import get_embedding_service  # noqa: E402
from src.retrieval_orchestration.hybrid_router.baseline_rule import (  # noqa: E402
    classify_by_keywords,
)


DATA_DIR = ROOT / "data" / "router" / "v3"
DATASET_PATH = DATA_DIR / "router_dataset.csv"
EXTENSION_PATH = DATA_DIR / "router_training_extension.csv"
ANNOTATIONS_PATH = DATA_DIR / "router_annotations.json"
SPLITS_PATH = DATA_DIR / "router_splits.json"
OUTPUT_DIR = ROOT / "models"
EMBEDDINGS_PATH = OUTPUT_DIR / "router_embeddings.npz"
MODEL_PATH = OUTPUT_DIR / "router_classifier.joblib"
MANIFEST_PATH = OUTPUT_DIR / "router_manifest.json"
EVALUATION_PATH = OUTPUT_DIR / "router_evaluation.json"
LABELS = ("needs_graph", "needs_content")
THRESHOLDS = tuple(round(value / 100, 2) for value in range(30, 71, 5))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> tuple[list[dict[str, str]], dict, dict]:
    with DATASET_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    annotations = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    split_document = json.loads(SPLITS_PATH.read_text(encoding="utf-8"))
    if len(rows) != 200 or len({row["id"] for row in rows}) != 200:
        raise ValueError("The reviewed router dataset must contain 200 unique rows")
    if annotations.get("training_authorized") is not True:
        raise ValueError("Training is not authorized by router_annotations.json")
    if annotations.get("second_review_completed") is not True:
        raise ValueError("The second label review is not complete")
    if file_sha256(DATASET_PATH) != split_document.get("dataset_sha256"):
        raise ValueError("router_dataset.csv does not match the approved split manifest")
    with EXTENSION_PATH.open(encoding="utf-8-sig", newline="") as handle:
        extension_rows = list(csv.DictReader(handle))
    if not 30 <= len(extension_rows) <= 40:
        raise ValueError("The router training extension must contain 30-40 rows")
    if len({row["id"] for row in extension_rows}) != len(extension_rows):
        raise ValueError("The router training extension IDs must be unique")
    if {row["id"] for row in rows} & {row["id"] for row in extension_rows}:
        raise ValueError("The router training extension IDs must not overlap the reviewed dataset")
    rows.extend(extension_rows)
    if any(row[label] not in {"0", "1"} for row in rows for label in LABELS):
        raise ValueError("needs_graph and needs_content must contain only 0 or 1")
    return rows, annotations, split_document


def build_indices(rows: list[dict[str, str]], split_document: dict) -> dict[str, np.ndarray]:
    positions = {row["id"]: index for index, row in enumerate(rows)}
    indices = {
        split: np.asarray([positions[row_id] for row_id in split_document["splits"][split]])
        for split in ("train", "validation", "test")
    }
    reviewed_ids = {
        row_id for split in ("train", "validation", "test")
        for row_id in split_document["splits"][split]
    }
    extension_ids = [row["id"] for row in rows if row["id"] not in reviewed_ids]
    indices["train"] = np.concatenate(
        [indices["train"], np.asarray([positions[row_id] for row_id in extension_ids])]
    )
    all_indices = np.concatenate(list(indices.values()))
    if len(all_indices) != len(rows) or len(set(all_indices.tolist())) != len(rows):
        raise ValueError("The reviewed splits plus extension must partition all rows")
    if {name: len(values) for name, values in indices.items()} != {
        "train": 140 + len(extension_ids),
        "validation": 30,
        "test": 30,
    }:
        raise ValueError("Expected the approved 140/30/30 split")
    return indices


def predict_at(scores: np.ndarray, threshold: float) -> np.ndarray:
    return (scores >= threshold).astype(np.int64)


def route_name(labels: np.ndarray) -> str:
    return {
        (0, 0): "NONE",
        (0, 1): "VECTOR",
        (1, 0): "GRAPH",
        (1, 1): "BOTH",
    }[tuple(int(value) for value in labels)]


def evaluate_labels(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, average=None, zero_division=0
    )
    exact = np.all(y_true == y_pred, axis=1)
    pair_confusion = Counter(
        f"{route_name(actual)}->{route_name(predicted)}"
        for actual, predicted in zip(y_true, y_pred)
    )
    return {
        "rows": int(len(y_true)),
        "exact_match_count": int(exact.sum()),
        "exact_match_ratio": float(exact.mean()),
        "predicted_none_count": int(np.all(y_pred == 0, axis=1).sum()),
        "per_label": {
            label: {
                "support": int(support[index]),
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "combination_confusion": dict(sorted(pair_confusion.items())),
    }


def baseline_predictions(questions: list[str]) -> np.ndarray:
    return np.asarray(
        [
            [prediction.needs_graph, prediction.needs_content]
            for prediction in map(classify_by_keywords, questions)
        ],
        dtype=np.int64,
    )


def select_threshold(y_true: np.ndarray, scores: np.ndarray) -> tuple[float, list[dict]]:
    candidates = []
    for threshold in THRESHOLDS:
        predicted = predict_at(scores, threshold)
        report = evaluate_labels(y_true, predicted)
        candidates.append({"threshold": threshold, **report})
    chosen = max(
        candidates,
        key=lambda item: (
            item["exact_match_ratio"],
            sum(label["f1"] for label in item["per_label"].values()) / len(LABELS),
            -abs(item["threshold"] - 0.5),
        ),
    )
    return float(chosen["threshold"]), candidates


def main() -> None:
    rows, annotations, split_document = load_inputs()
    indices = build_indices(rows, split_document)
    questions = [row["question"] for row in rows]
    targets = np.asarray(
        [[int(row[label]) for label in LABELS] for row in rows], dtype=np.int64
    )

    settings = get_settings()
    embedding_started = time.perf_counter()
    vectors = get_embedding_service().embed_texts(questions)
    embedding_seconds = time.perf_counter() - embedding_started
    features = np.asarray(vectors, dtype=np.float32)
    if features.shape != (len(rows), settings.embedding_dim):
        raise ValueError(
            f"Expected {len(rows)} x {settings.embedding_dim} embeddings, got {features.shape}"
        )
    if not np.isfinite(features).all():
        raise ValueError("Embedding output contains non-finite numbers")
    norms = np.linalg.norm(features, axis=1)
    if not all(math.isclose(float(norm), 1.0, rel_tol=1e-4, abs_tol=1e-4) for norm in norms):
        raise ValueError("Embedding output is not L2-normalized")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        EMBEDDINGS_PATH,
        ids=np.asarray([row["id"] for row in rows]),
        vectors=features,
    )

    X_train = features[indices["train"]]
    y_train = targets[indices["train"]]

    classifier = OneVsRestClassifier(LogisticRegression(max_iter=2000))
    classifier.fit(X_train, y_train)
    joblib.dump(classifier, MODEL_PATH)

    validation_indices = indices["validation"]
    validation_scores = classifier.predict_proba(features[validation_indices])
    threshold, threshold_candidates = select_threshold(
        targets[validation_indices], validation_scores
    )

    evaluation = {
        "evaluation_policy": {
            "threshold_selected_on": "validation",
            "test_used_for_threshold_selection": False,
            "threshold": threshold,
            "threshold_candidates": threshold_candidates,
        },
        "splits": {},
        "limitations": [
            "The dataset has only 30 validation and 30 test rows.",
            f"All {len(rows)} classifier questions are synthetic.",
            "Route accuracy does not prove that GRAPH/BOTH adapters are live or answerable.",
        ],
    }
    for split in ("train", "validation", "test"):
        split_indices = indices[split]
        split_questions = [questions[index] for index in split_indices]
        model_prediction = predict_at(
            classifier.predict_proba(features[split_indices]), threshold
        )
        baseline_prediction = baseline_predictions(split_questions)
        evaluation["splits"][split] = {
            "classifier": evaluate_labels(targets[split_indices], model_prediction),
            "keyword_baseline": evaluate_labels(targets[split_indices], baseline_prediction),
        }
    EVALUATION_PATH.write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    manifest = {
        "artifact_version": "finmind-hybrid-router-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": annotations["dataset_version"],
        "dataset": {
            "path": DATASET_PATH.relative_to(ROOT).as_posix(),
            "sha256": file_sha256(DATASET_PATH),
            "annotations_sha256": file_sha256(ANNOTATIONS_PATH),
            "splits_sha256": file_sha256(SPLITS_PATH),
            "rows_embedded": len(rows),
            "reviewed_rows": 200,
            "training_extension_rows": len(rows) - 200,
            "training_extension_path": EXTENSION_PATH.relative_to(ROOT).as_posix(),
            "training_extension_sha256": file_sha256(EXTENSION_PATH),
            "split_sizes": {name: int(len(value)) for name, value in indices.items()},
            "training_authorized": annotations["training_authorized"],
        },
        "embedding": {
            "service": "src.documents.embeddings.get_embedding_service",
            "method": "embed_texts",
            "model": settings.embedding_model,
            "revision": settings.embedding_model_revision,
            "model_ref": settings.embedding_model_ref,
            "dimension": settings.embedding_dim,
            "normalized": True,
            "batch_size": settings.embedding_batch_size,
            "elapsed_seconds": embedding_seconds,
            "artifact": EMBEDDINGS_PATH.relative_to(ROOT).as_posix(),
            "artifact_sha256": file_sha256(EMBEDDINGS_PATH),
        },
        "classifier": {
            "type": "OneVsRestClassifier(LogisticRegression(max_iter=2000))",
            "labels": list(LABELS),
            "feature_dimension": settings.embedding_dim,
            "threshold": threshold,
            "artifact": MODEL_PATH.relative_to(ROOT).as_posix(),
            "artifact_sha256": file_sha256(MODEL_PATH),
            "trusted_local_artifact_only": True,
        },
        "evaluation": {
            "artifact": EVALUATION_PATH.relative_to(ROOT).as_posix(),
            "artifact_sha256": file_sha256(EVALUATION_PATH),
            "validation": evaluation["splits"]["validation"],
            "test": evaluation["splits"]["test"],
        },
        "challenge_set_in_training": False,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    loaded = joblib.load(MODEL_PATH)
    loaded_shape = loaded.predict_proba(features[indices["test"][:1]]).shape
    if loaded_shape != (1, 2):
        raise ValueError(f"Reloaded model returned unexpected shape {loaded_shape}")
    print(
        json.dumps(
            {
                "status": "TRAINED",
                "model": MODEL_PATH.relative_to(ROOT).as_posix(),
                "manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
                "threshold": threshold,
                "validation_exact_match": evaluation["splits"]["validation"]["classifier"]["exact_match_ratio"],
                "test_exact_match": evaluation["splits"]["test"]["classifier"]["exact_match_ratio"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
