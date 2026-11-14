"""Version-two proposals. This module never selects a retrieval route."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from threading import RLock

import numpy as np

from .intent_library import load_library
from .intent_matching import IntentMatcher
from .intent_scoring import classifier_probabilities, normalized, rankings
from .intent_v2_rules import explicit_components, explicit_intent, requests, standalone_conversation

DEFAULT_ARTIFACT = Path(__file__).resolve().parents[3] / 'outputs/s5_intent_v2_20261113/artifact-v2'
LABELS = {'PRICE', 'NUMERIC', 'ANALYSIS', 'NEWS', 'REPORT_CONTENT', 'PERSON_ROLE',
          'ENTITY_RELATION', 'COMPANY_OVERVIEW', 'CONVERSATION', 'OUT_OF_SCOPE', 'MIXED'}
_CACHE_LOCK = RLock()


class IntentClassifier:
    """Load once at startup; reuse the application's existing embedding service."""

    @classmethod
    def load(cls, directory, embedder):
        directory = Path(directory)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        names = {'library/manifest.json', 'classifier.npz', 'fit.json'}
        if (manifest.get('format_version') != 'intent-classifier-v2'
                or manifest.get('status') != 'READY_FOR_REVIEW'
                or manifest.get('labels') != sorted(LABELS)
                or set(manifest.get('files', {})) != names):
            raise ValueError('INVALID_CLASSIFIER_MANIFEST')
        for name in names:
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != manifest['files'][name]:
                raise ValueError('CLASSIFIER_CHECKSUM_MISMATCH: ' + name)
        library = load_library(directory / 'library', expected_model=embedder.model_name,
                               expected_revision=embedder.revision)
        if {row['intent_label'] for row in library.rows} != LABELS:
            raise ValueError('CLASSIFIER_LIBRARY_LABEL_MISMATCH')
        with np.load(directory / 'classifier.npz', allow_pickle=False) as parameters:
            if set(parameters.files) != {'coefficients', 'intercepts'}:
                raise ValueError('INVALID_CLASSIFIER_PARAMETERS')
            coefficients = np.array(parameters['coefficients'], dtype=np.float64)
            intercepts = np.array(parameters['intercepts'], dtype=np.float64)
        dimension = library.manifest['model']['dimension']
        if (coefficients.shape != (len(LABELS), dimension) or intercepts.shape != (len(LABELS),)
                or not np.isfinite(coefficients).all() or not np.isfinite(intercepts).all()):
            raise ValueError('INVALID_CLASSIFIER_PARAMETERS')
        instance = cls()
        instance.manifest, instance.embedder = manifest, embedder
        instance.matcher = IntentMatcher(library, embedder)
        coefficients.flags.writeable = intercepts.flags.writeable = False
        instance.coefficients, instance.intercepts = coefficients, intercepts
        return instance

    def classify(self, question, *, context=None):
        IntentMatcher._check_question(question)
        if context is not None and not isinstance(context, dict):
            raise ValueError('INVALID_CONTEXT')
        vectors = np.asarray(self.embedder.embed_texts([question]), dtype=np.float64)
        dimension = self.coefficients.shape[1]
        if vectors.shape != (1, dimension):
            raise ValueError('QUERY_VECTOR_BATCH_SHAPE')
        vector = normalized(vectors)
        model = self.matcher.library.manifest['model']
        scores = classifier_probabilities(vector, self.coefficients, self.intercepts)
        base = rankings([question], scores, self.manifest['labels'], 'intent-linear-v2',
                        'CLASSIFIER_PROBABILITY_UNCALIBRATED', model)[0]
        base['groups'] = base['groups'][:3]
        evidence = []
        components, unresolved = set(), []
        parts = requests(question)
        for part in parts:
            label = explicit_intent(part)
            evidence.append(dict(request=part, explicit_label=label))
            if label == 'MIXED':
                components.update(explicit_components(part))
            elif label is not None:
                components.add(label)
            else:
                unresolved.append(part)
        raw = base['groups'][0]['intent_label']
        if len(components) > 1:
            label, reason = 'MIXED', 'MULTIPLE_REQUEST_TYPES'
        elif components and not unresolved:
            label, reason = next(iter(components)), 'EXPLICIT_REQUEST_TYPE'
        else:
            label, reason = raw, 'CLASSIFIER_PROPOSAL'
        status = 'PROPOSED'
        # A mixed prediction alone cannot invent its constituent requests.
        if (label == 'MIXED' and len(components) < 2) or (unresolved and len(parts) > 1):
            status = 'UNRESOLVED'
        conversation_parts = [e['request'] for e in evidence if e['explicit_label'] == 'CONVERSATION']
        # Only rule-detected follow-up wording waits for session context; a classifier guess of
        # CONVERSATION (e.g. an off-topic question) stays PROPOSED so the fallback decides (review 14/11).
        if status == 'PROPOSED' and any(not standalone_conversation(part) for part in conversation_parts):
            if not context or context.get('verified') is not True:
                status = 'NEEDS_CONTEXT'
        source = self.matcher.library.manifest
        return dict(question=question, classifier_version=self.manifest['classifier_version'],
                    library_version=source['library_version'], dataset_version=source['dataset_version'],
                    label_schema_version=source['label_schema_version'], base_ranking=base,
                    reference_ranking=self.matcher._rank(question, vector[0], 3, 5),
                    resolution=dict(question=question, intent_label=label, status=status, reason=reason,
                        component_labels=sorted(components) if label == 'MIXED' else [],
                        contains_restricted_component=label == 'OUT_OF_SCOPE' or 'OUT_OF_SCOPE' in components,
                        unresolved_requests=unresolved,
                        explicit_evidence=[dict(text=e['request'], intent_label=e['explicit_label'])
                                           for e in evidence if e['explicit_label'] is not None],
                        ranking_policy='intent-request-objectives-v2-11-r2',
                        score_type='DECISION_EVIDENCE_NO_CONFIDENCE', confidence=None,
                        runtime_enabled=False))


@lru_cache(maxsize=4)
def _loaded(directory, embedder):
    return IntentClassifier.load(directory, embedder)


def classify_intent(question, *, embedder, artifact_path=DEFAULT_ARTIFACT, context=None):
    """Return an eleven-label proposal; no network, database, or chat side effects.

    Inject get_embedding_service() from the application. The first call loads the
    immutable artifact; later calls reuse it. Deploy new versions at new paths.
    """
    with _CACHE_LOCK:
        classifier = _loaded(str(Path(artifact_path).absolute()), embedder)
    return classifier.classify(question, context=context)
