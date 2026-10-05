"""Weighted mean of supporting evidence; missing sources are not zero votes."""


def aggregate(evidence, weights):
    total = sum(weights[source] for source in sorted(evidence))
    return sum(weights[source] * evidence[source][1] for source in sorted(evidence)) / total if total else 0.0
