"""Standalone side branch; detector/semantic workers and ObjectFrame stay intact."""

import logging
from dataclasses import asdict, replace

from yolo.alerts.contracts import AlertEvent
from yolo.alerts.manager import AlertManager
from yolo.alerts.timing import host_time
from yolo.procedure.event_log import EventLog
from yolo.procedure.fast_actions import FastClassifier
from yolo.procedure.fusion import ActionFusion
from yolo.procedure.relevance import ActionRelevance
from yolo.procedure.validator import ProcedureValidator


class ProcedureAssistant:
    def __init__(
        self,
        definition,
        action_objects,
        *,
        fast_config=None,
        voice_config=None,
        event_log=None,
        tts=None,
        player=None,
        clock=host_time,
    ):
        self.definition = definition
        self.clock = clock
        self.log = event_log or EventLog()
        self.validator = ProcedureValidator(definition, clock=clock)
        self.classifier = FastClassifier(fast_config, action_objects)
        self.fast_coverage = self.classifier.coverage(definition)
        self.log.emit({"event": "fast_path_coverage", "actions": self.fast_coverage})
        coverage_text = ", ".join(
            f"{action}: {'YES' if supported else 'NO'}"
            for action, supported in self.fast_coverage.items()
        )
        logging.getLogger(__name__).info("Fast-path coverage: %s", coverage_text)
        unsupported = [
            a for a, supported in self.fast_coverage.items() if not supported
        ]
        if unsupported:
            warning = (
                "Fast action classifier is not calibrated for: "
                + ", ".join(unsupported)
                + ". Procedure warnings may depend on Qwen and may exceed the 1.5 s "
                "target. Provide --fast-config with home/work ROIs for low-latency "
                "supported actions."
            )
            logging.getLogger(__name__).warning(warning)
            self.log.emit(
                {
                    "event": "fast_path_uncalibrated",
                    "warning": warning,
                    "unsupported_actions": unsupported,
                }
            )
        self.fusion = ActionFusion(action_objects, clock=clock)
        self.relevance = ActionRelevance(definition, action_objects)
        self._incidental_key = None
        self.alerts = AlertManager(
            definition,
            voice_config,
            tts=tts,
            player=player,
            emit=self.log.emit,
            clock=clock,
        )
        self.log.emit(
            {
                "event": "procedure_loaded",
                "name": definition.name,
                "steps": len(definition.steps),
            }
        )
        self._next_step(0, 0.0)

    @property
    def state(self):
        return self.validator.state

    def _next_step(self, frame_id, timestamp_s):
        step = self.validator.expected
        self.log.emit(
            {
                "event": "step_started" if step else "procedure_completed",
                "step_id": step.step_id if step else None,
                "frame_id": frame_id,
            }
        )
        if step:
            self.log.emit(
                {
                    "event": "next_step",
                    "step_id": step.step_id,
                    "action": step.action,
                    "instruction": step.instruction,
                }
            )
            from yolo.alerts.manager import step_message

            message = step_message(step, "NEXT_STEP")
        else:
            message = "Procedure complete."
        self.alerts.enqueue(
            AlertEvent(
                "NEXT_STEP" if step else "COMPLETED",
                message,
                3,
                frame_id,
                timestamp_s,
                step.step_id if step else None,
                "NONE",
                self.clock(),
            )
        )

    def accept_confirmed(self, action):
        """Explicit injection seam for deterministic tests, never camera evidence."""
        self.log.emit({"event": "action_confirmed", **asdict(action)})
        if self.relevance.incidental(action.action, action.object_name):
            event = self.relevance.diagnostic(action, self.state.next_action)
            self.log.emit(asdict(event))
            return event
        event = self.validator.observe(action)
        if event is None:
            return None
        self.log.emit(asdict(event))
        alert = self.alerts.alert_for(event, self.definition)
        if alert:
            self.alerts.enqueue(alert)
        if event.event == "STEP_COMPLETED":
            if self.alerts.config.speak_success:
                self.alerts.enqueue(
                    AlertEvent(
                        "SUCCESS",
                        "Correct. Continue.",
                        4,
                        action.frame_id,
                        action.timestamp_s,
                        event.step_id,
                        action.action,
                        action.confirmed_monotonic_s,
                    )
                )
            self._next_step(action.frame_id, action.timestamp_s)
        return event

    def observe(self, objects, semantic=None, *, reset_required=False):
        if reset_required:
            self.reset()
        candidate = self.classifier.classify(objects)
        self.log.emit(
            {"event": "action_candidate", "source": "fast", **asdict(candidate)}
        )
        if self.relevance.incidental(candidate.action, candidate.object_name):
            key = (candidate.action, candidate.object_name)
            if key != self._incidental_key:
                self.log.emit(
                    {
                        "event": "NON_PROCEDURAL_ACTION",
                        **asdict(candidate),
                        "source": "fast",
                    }
                )
            self._incidental_key = key
            candidate = replace(candidate, action="UNCERTAIN", object_name=None)
        else:
            self._incidental_key = None
        confirmed = self.fusion.fast_action(
            candidate, self.validator.confirmation_frames(candidate.action)
        )
        if confirmed:
            self.classifier.acknowledge(confirmed)
            self.accept_confirmed(confirmed)
        # A semantic event is consumed once. It cannot retract a fast commit or
        # generate retroactive speech. Refine only when the fast evidence is
        # uncertain, and require multiple distinct chronological event votes.
        if candidate.action == "UNCERTAIN" or confirmed:
            if semantic and self.relevance.incidental(
                semantic.action, semantic.object_name
            ):
                if semantic.event_id > self.fusion.last_semantic_event:
                    self.log.emit(
                        {
                            "event": "NON_PROCEDURAL_ACTION",
                            **asdict(semantic),
                            "source": "semantic",
                        }
                    )
                semantic = replace(semantic, action="UNCERTAIN", object_name=None)
            action, disagreement = self.fusion.semantic_action(
                semantic,
                self.validator.confirmation_frames(semantic.action) if semantic else 3,
                current_timestamp_s=objects.timestamp_s,
            )
            if disagreement:
                self.log.emit(disagreement)
            if action and candidate.action == "UNCERTAIN":
                self.accept_confirmed(action)
        timeout = self.validator.tick(objects.frame_id, objects.timestamp_s)
        if timeout:
            self.log.emit(asdict(timeout))
            self.alerts.enqueue(self.alerts.alert_for(timeout, self.definition))
        return self.state

    def reset(self):
        self.classifier.reset()
        self._incidental_key = None
        self.fusion.reset()
        self.validator.reset()
        self.alerts.reset()
        self.log.emit({"event": "procedure_reset"})
        self._next_step(0, 0.0)

    def close(self):
        self.alerts.close()
        self.log.close()
