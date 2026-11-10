"""S5-WBS04.1: cosine ranking of intent candidates, without route/threshold decisions."""
import numpy as np

RANKING_POLICY = 'cosine-max-per-label-v1'


class IntentMatcher:
    """Bind an artifact returned by load_library to its exact query encoder."""

    def __init__(self, library, embedder):
        model = library.manifest['model']
        if embedder.model_name != model['name']:
            raise ValueError('MODEL_MISMATCH')
        if embedder.revision != model['revision']:
            raise ValueError('REVISION_MISMATCH')
        self.library, self.embedder = library, embedder
        values = library.vectors.astype(np.float64)
        self._unit_vectors = values / np.linalg.norm(values, axis=1, keepdims=True)

    @staticmethod
    def _check_limits(top_groups, top_examples):
        if any(type(k) is not int or k < 1 for k in (top_groups, top_examples)):
            raise ValueError('INVALID_TOP_K')

    @staticmethod
    def _check_question(question):
        if not isinstance(question, str) or not question.strip():
            raise ValueError('INVALID_QUESTION')

    def match(self, question, *, top_groups=3, top_examples=5):
        self._check_limits(top_groups, top_examples)
        self._check_question(question)
        return self._rank(question, self.embedder.embed_query(question), top_groups, top_examples)

    def match_many(self, questions, *, top_groups=3, top_examples=5):
        self._check_limits(top_groups, top_examples)
        if isinstance(questions, str):
            raise ValueError('QUESTIONS_MUST_BE_A_SEQUENCE')
        questions = list(questions)
        for question in questions:
            self._check_question(question)
        if not questions:
            return []
        values = np.asarray(self.embedder.embed_texts(questions), dtype=np.float64)
        if values.shape != (len(questions), self._unit_vectors.shape[1]):
            raise ValueError('QUERY_VECTOR_BATCH_SHAPE')
        return [self._rank(question, vector, top_groups, top_examples)
                for question, vector in zip(questions, values)]

    def _rank(self, question, vector, top_groups, top_examples):
        vector = np.asarray(vector, dtype=np.float64)
        if vector.shape != (self._unit_vectors.shape[1],) or not np.isfinite(vector).all():
            raise ValueError('QUERY_VECTOR_SHAPE_OR_NONFINITE')
        norm = np.linalg.norm(vector)
        if not np.isfinite(norm) or norm == 0:
            raise ValueError('QUERY_VECTOR_ZERO_OR_INVALID_NORM')
        scores = np.clip(self._unit_vectors @ (vector / norm), -1, 1)
        order = sorted(range(len(scores)), key=lambda i: (
            -float(scores[i]), self.library.rows[i]['intent_label'], self.library.rows[i]['id']))
        examples, best_by_label = [], {}
        for index in order:
            row = self.library.rows[index]
            example = dict(id=row['id'], text=row['text'], intent_label=row['intent_label'],
                           score=float(scores[index]), component_intents=list(row['component_intents']))
            examples.append(example)
            best_by_label.setdefault(row['intent_label'], example)
        groups = [dict(rank=i + 1, intent_label=label, score=example['score'], best_example=example)
                  for i, (label, example) in enumerate(best_by_label.items())]
        source = self.library.manifest
        return dict(question=question, ranking_policy=RANKING_POLICY,
                    score_type='COSINE_SIMILARITY_NOT_PROBABILITY',
                    model=dict(name=source['model']['name'], revision=source['model']['revision']),
                    library_version=source['library_version'], dataset_version=source['dataset_version'],
                    label_schema_version=source['label_schema_version'],
                    groups=groups[:top_groups], examples=examples[:top_examples])


def summarize_evaluation(cases, rankings, labels):
    """Score top-1/top-3 only on labeled cases; null cases remain observations."""
    if len(cases) != len(rankings) or not labels:
        raise ValueError('EVALUATION_INPUT_MISMATCH')
    matrix = {label: {predicted: 0 for predicted in labels} for label in labels}
    top1 = top3 = count = 0
    wrong = []
    for case, ranking in zip(cases, rankings):
        gold = case['intent_label']
        if gold is None:
            continue
        candidates = [g['intent_label'] for g in ranking['groups']]
        if gold not in matrix or not candidates or any(c not in matrix for c in candidates):
            raise ValueError('INVALID_EVALUATION_LABEL')
        count += 1
        matrix[gold][candidates[0]] += 1
        top1 += candidates[0] == gold
        top3 += gold in candidates[:3]
        if candidates[0] != gold:
            wrong.append(case['id'])
    metrics = {}
    for label in labels:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        predicted = sum(matrix[gold][label] for gold in labels)
        precision, recall = (tp / predicted if predicted else 0), (tp / support if support else 0)
        metrics[label] = dict(support=support, precision=precision, recall=recall,
                              f1=2 * precision * recall / (precision + recall) if precision + recall else 0)
    return dict(labeled_cases=count, unlabeled_cases=len(cases) - count,
                top1_accuracy=top1 / count if count else None,
                top3_recall=top3 / count if count else None,
                macro_f1=sum(m['f1'] for m in metrics.values()) / len(labels) if count else None,
                per_label=metrics, confusion_matrix=matrix, wrong_case_ids=wrong)
