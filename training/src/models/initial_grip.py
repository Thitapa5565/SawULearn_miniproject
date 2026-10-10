"""Shared selective prediction for early grip; support is not calibrated accuracy."""
import numpy as np

GUARD = {'policy':'veto_disputed_correct', 'range_margin_fraction': .20, 'range_margin_minimum': .02}
RIGHTMOST_GUARD = {'policy':'direct_rightmost', 'range_margin_fraction': .20,
                  'range_margin_minimum': .02, 'minimum_support': .55, 'minimum_margin': .10}

def predict(bundle, values):
    features = bundle['feature_columns']
    if not all(k in values and np.isfinite(values[k]) for k in features):
        return {'status':'unavailable','prediction':None,'reason':'missing_grip_features'}
    X = np.array([[values[k] for k in features]])
    policy = bundle['guard']
    lo, hi = np.array(bundle['train_min']), np.array(bundle['train_max'])
    margin = np.maximum((hi-lo)*policy['range_margin_fraction'],policy['range_margin_minimum'])
    if np.any(X[0]<lo-margin) or np.any(X[0]>hi+margin):
        return {'status':'unavailable','prediction':None,'reason':'outside_training_range'}
    model_input = X
    if hasattr(bundle['model'], 'feature_names_in_'):
        import pandas as pd
        model_input = pd.DataFrame(X, columns=features)
    probabilities = bundle['model'].predict_proba(model_input)[0]
    order = np.argsort(probabilities)[::-1]
    label = str(bundle['model'].classes_[order[0]])
    support = float(probabilities[order[0]])
    gap = float(probabilities[order[0]]-probabilities[order[1]])
    if policy['policy'] == 'direct_rightmost':
        ambiguous = support < policy['minimum_support'] or gap < policy['minimum_margin']
        return {'status':'ready','prediction':'uncertain' if ambiguous else label,
                'reason':'low_model_support' if ambiguous else None,'raw_prediction':label,
                'model_support':dict(zip(map(str,bundle['model'].classes_),map(float,probabilities))),
                'support_margin':gap}
    original = str(bundle['base_model'].predict([[values['bow_side_horizontal_ratio']]])[0])
    # The challenger has better high recall but more false alarms. It may veto
    # an old 'correct' result, not promote disagreement to a definite error.
    ambiguous = original=='none' and label!='none'
    return {'status':'ready','prediction':'uncertain' if ambiguous else original,
            'reason':'model_disagreement' if ambiguous else None,'raw_prediction':label,
            'base_prediction':original,'candidate_prediction':label if ambiguous else None,
            'model_support':dict(zip(map(str,bundle['model'].classes_),map(float,probabilities))),
            'support_margin':gap}
