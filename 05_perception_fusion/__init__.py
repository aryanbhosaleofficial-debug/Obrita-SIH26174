"""Module 05: explainable local evidence fusion through shared ActivityEvent."""


def __getattr__(name):
    if name == "FusionPipeline":
        from fusion.pipeline import FusionPipeline

        return FusionPipeline
    raise AttributeError(name)
