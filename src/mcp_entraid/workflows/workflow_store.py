from __future__ import annotations

from datetime import datetime, timezone

from mcp_entraid.schemas.authentication_methods import ResetMfaWorkflowState


class WorkflowStore:
    def __init__(self) -> None:
        self._reset_mfa_states: dict[str, ResetMfaWorkflowState] = {}

    def save_reset_mfa_state(self, state: ResetMfaWorkflowState) -> None:
        self._reset_mfa_states[state.reset_request_id] = state.model_copy(deep=True)

    def get_reset_mfa_state(self, reset_request_id: str) -> ResetMfaWorkflowState | None:
        state = self._reset_mfa_states.get(reset_request_id)
        if state is None:
            return None
        return state.model_copy(deep=True)

    def find_active_reset_mfa_state_by_upn(self, user_upn: str) -> ResetMfaWorkflowState | None:
        normalized_upn = (user_upn or "").strip().lower()
        if not normalized_upn:
            return None

        for state in reversed(list(self._reset_mfa_states.values())):
            if state.user_principal_name.lower() != normalized_upn:
                continue
            if state.status in {"completed", "cancelled", "expired"}:
                continue
            if self.is_expired(state):
                self.mark_expired(state)
                continue
            return state.model_copy(deep=True)
        return None

    def is_expired(self, state: ResetMfaWorkflowState) -> bool:
        return self._parse_datetime(state.expires_at) <= datetime.now(timezone.utc)

    def mark_expired(self, state: ResetMfaWorkflowState) -> ResetMfaWorkflowState:
        state.status = "expired"
        state.current_step = None
        self.save_reset_mfa_state(state)
        return state

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
