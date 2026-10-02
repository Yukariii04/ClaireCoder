"""Tests for the authoritative agent run state machine."""
import pytest
import threading
from clairecoder.interaction.run_state import RunState, AgentRun


class TestRunStateEnum:
    def test_all_states_exist(self):
        assert RunState.IDLE == "idle"
        assert RunState.RUNNING == "running"
        assert RunState.WAITING_FOR_USER == "waiting_for_user"
        assert RunState.COMPLETED == "completed"
        assert RunState.FAILED == "failed"
        assert RunState.CANCELLED == "cancelled"
        assert RunState.INTERRUPTED == "interrupted"


class TestAgentRun:
    def test_initial_state_is_idle(self):
        run = AgentRun("test-1")
        assert run.state == RunState.IDLE
        assert not run.is_terminal
        assert not run.is_cancelled

    def test_start_transitions_to_running(self):
        run = AgentRun("test-1")
        run.start()
        assert run.state == RunState.RUNNING
        assert run.attempt_number == 1
        assert run.can_start_work

    def test_complete_transitions_to_completed(self):
        run = AgentRun("test-1")
        run.start()
        run.complete()
        assert run.state == RunState.COMPLETED
        assert run.is_terminal
        assert not run.can_start_work

    def test_fail_transitions_to_failed(self):
        run = AgentRun("test-1")
        run.start()
        run.fail("test reason")
        assert run.state == RunState.FAILED
        assert run.is_terminal
        assert run.failure_reason == "test reason"

    def test_cancel_sets_cancellation_flag(self):
        run = AgentRun("test-1")
        run.start()
        run.cancel()
        assert run.state == RunState.CANCELLED
        assert run.is_cancelled
        assert run.is_terminal

    def test_interrupt_transitions_to_interrupted(self):
        run = AgentRun("test-1")
        run.start()
        run.interrupt()
        assert run.state == RunState.INTERRUPTED
        assert run.is_terminal
        assert run.is_cancelled

    def test_terminal_states_are_idempotent(self):
        run = AgentRun("test-1")
        run.start()
        run.complete()
        run.complete()  # No error
        run.fail("should not override")
        assert run.state == RunState.COMPLETED  # Not overridden

    def test_wait_for_user_and_resume(self):
        run = AgentRun("test-1")
        run.start()
        run.wait_for_user()
        assert run.state == RunState.WAITING_FOR_USER
        run.resume_from_wait()
        assert run.state == RunState.RUNNING

    def test_cannot_start_from_running(self):
        run = AgentRun("test-1")
        run.start()
        with pytest.raises(RuntimeError):
            run.start()

    def test_max_attempts_enforced(self):
        run = AgentRun("test-1")
        for _ in range(AgentRun.MAX_ATTEMPTS):
            run.start()
            run.fail("retry")
        # Next start should auto-fail
        run.start()
        assert run.state == RunState.FAILED
        assert "Max attempts" in run.failure_reason

    def test_reset_clears_state(self):
        run = AgentRun("test-1")
        run.start()
        run.complete()
        run.reset()
        assert run.state == RunState.IDLE
        assert run.attempt_number == 0
        assert run.failure_reason is None

    def test_cannot_reset_from_running(self):
        run = AgentRun("test-1")
        run.start()
        with pytest.raises(RuntimeError):
            run.reset()

    def test_state_change_callback(self):
        transitions = []
        def on_change(old, new):
            transitions.append((old.value, new.value))
        
        run = AgentRun("test-1", on_state_change=on_change)
        run.start()
        run.complete()
        assert transitions == [("idle", "running"), ("running", "completed")]

    def test_callback_exception_does_not_corrupt_state(self):
        def bad_callback(old, new):
            raise RuntimeError("callback boom")

        run = AgentRun("test-1", on_state_change=bad_callback)
        run.start()  # Should not raise despite callback error
        assert run.state == RunState.RUNNING

    def test_thread_safety(self):
        """Verify concurrent state transitions don't corrupt the state machine."""
        run = AgentRun("test-1")
        run.start()
        errors = []
        
        def cancel_it():
            try:
                run.cancel()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=cancel_it) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert not errors
        assert run.is_terminal
