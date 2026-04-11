"""Retention planning helpers for the artifact truth store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import RetentionAction, RetentionCandidate, RetentionPlan

if TYPE_CHECKING:
    from .write import ArtifactStore


def plan_retention(
    store: "ArtifactStore",
    *,
    refs_to_keep: set[str] | None = None,
) -> RetentionPlan:
    keep_refs = set() if refs_to_keep is None else {str(item) for item in refs_to_keep}
    keep: list[RetentionCandidate] = []
    review: list[RetentionCandidate] = []
    for artifact_ref in store.list_refs():
        if artifact_ref in keep_refs:
            keep.append(
                RetentionCandidate(
                    artifact_ref=artifact_ref,
                    action=RetentionAction.KEEP,
                    reason="requested in refs_to_keep",
                )
            )
        else:
            review.append(
                RetentionCandidate(
                    artifact_ref=artifact_ref,
                    action=RetentionAction.REVIEW,
                    reason="active artifact not explicitly pinned for retention",
                )
            )
    return RetentionPlan(keep=tuple(keep), review=tuple(review))


__all__ = ["plan_retention"]
