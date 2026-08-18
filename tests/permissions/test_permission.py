import pytest
from clairecoder.permissions.types import (
    AutonomyLevel, PermissionCategory, ResourceScope, 
    PermissionRequest, PermissionRule,
    PermissionDeniedError, PermissionRequiredError
)
from clairecoder.core.types import PermissionState
from clairecoder.permissions.engine import PermissionEngine

def test_default_supervised_behavior():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    req = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    assert engine.evaluate_request(req) == PermissionState.ASK
    
def test_explicit_allow_rule():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    engine.add_rule(PermissionRule(
        decision=PermissionState.ALLOW,
        tool_id="tool",
        priority=10
    ))
    req = PermissionRequest("tool", "write", "file.txt", PermissionCategory.WRITE, ResourceScope.FILE)
    assert engine.evaluate_request(req) == PermissionState.ALLOW

def test_high_priority_allow_vs_low_priority_deny():
    engine = PermissionEngine()
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, priority=10))
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, priority=20))
    req = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    assert engine.evaluate_request(req) == PermissionState.ALLOW

def test_high_priority_deny_vs_low_priority_allow():
    engine = PermissionEngine()
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, priority=10))
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, priority=20))
    req = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    assert engine.evaluate_request(req) == PermissionState.DENY

def test_category_specific_vs_general_rule():
    engine = PermissionEngine()
    # General rule denies everything
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, priority=10))
    # Category specific allows reads
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, category=PermissionCategory.READ, priority=20))
    
    req1 = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    assert engine.evaluate_request(req1) == PermissionState.ALLOW
    
    req2 = PermissionRequest("tool", "write", "file.txt", PermissionCategory.WRITE, ResourceScope.FILE)
    assert engine.evaluate_request(req2) == PermissionState.DENY

def test_tool_specific_vs_general_rule():
    engine = PermissionEngine()
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, priority=10))
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, tool_id="good_tool", priority=20))
    
    req1 = PermissionRequest("good_tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    assert engine.evaluate_request(req1) == PermissionState.ALLOW
    
    req2 = PermissionRequest("bad_tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    assert engine.evaluate_request(req2) == PermissionState.DENY

def test_scope_specific_vs_general_rule():
    engine = PermissionEngine()
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, priority=10))
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, resource_scope=ResourceScope.FILE, priority=20))
    
    req1 = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    assert engine.evaluate_request(req1) == PermissionState.ALLOW
    
    req2 = PermissionRequest("tool", "read", "project", PermissionCategory.READ, ResourceScope.PROJECT)
    assert engine.evaluate_request(req2) == PermissionState.DENY

def test_session_specific_vs_general_rule():
    engine = PermissionEngine()
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, priority=10))
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, session_id="ses_1", priority=20))
    
    req1 = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE, session_id="ses_1")
    assert engine.evaluate_request(req1) == PermissionState.ALLOW
    
    req2 = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE, session_id="ses_2")
    assert engine.evaluate_request(req2) == PermissionState.DENY

def test_explicit_deny_precedence():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.YOLO)
    engine.add_rule(PermissionRule(
        decision=PermissionState.DENY,
        category=PermissionCategory.ACCESS_CREDENTIAL,
        priority=100
    ))
    req = PermissionRequest("tool", "read", "secret", PermissionCategory.ACCESS_CREDENTIAL, ResourceScope.CREDENTIAL)
    assert engine.evaluate_request(req) == PermissionState.DENY

def test_assisted_autonomy():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.ASSISTED)
    req_read = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    req_write = PermissionRequest("tool", "write", "file.txt", PermissionCategory.WRITE, ResourceScope.FILE)
    
    assert engine.evaluate_request(req_read) == PermissionState.ALLOW
    assert engine.evaluate_request(req_write) == PermissionState.ASK

def test_autonomous_autonomy():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)
    req_write = PermissionRequest("tool", "write", "file.txt", PermissionCategory.WRITE, ResourceScope.FILE)
    req_delete = PermissionRequest("tool", "delete", "file.txt", PermissionCategory.DELETE, ResourceScope.FILE)
    
    assert engine.evaluate_request(req_write) == PermissionState.ALLOW
    assert engine.evaluate_request(req_delete) == PermissionState.ASK

def test_enforce_raises_errors():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    req = PermissionRequest("tool", "delete", "file.txt", PermissionCategory.DELETE, ResourceScope.FILE)
    
    with pytest.raises(PermissionRequiredError):
        engine.enforce(req)
        
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, priority=10))
    with pytest.raises(PermissionDeniedError):
        engine.enforce(req)

def test_revoke_rule():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    rule = PermissionRule(decision=PermissionState.ALLOW, category=PermissionCategory.READ, priority=10)
    engine.add_rule(rule)
    
    req = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE)
    assert engine.evaluate_request(req) == PermissionState.ALLOW
    
    engine.revoke_rule(rule)
    assert engine.evaluate_request(req) == PermissionState.ASK

def test_credential_always_denied_or_asked():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.YOLO)
    req = PermissionRequest("tool", "read", "secret", PermissionCategory.ACCESS_CREDENTIAL, ResourceScope.CREDENTIAL)
    # Default behavior denies credentials even in YOLO mode unless explicitly allowed
    assert engine.evaluate_request(req) == PermissionState.DENY

def test_credential_allow_vs_credential_deny():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.YOLO)
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, category=PermissionCategory.ACCESS_CREDENTIAL, priority=100))
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, category=PermissionCategory.ACCESS_CREDENTIAL, priority=10))
    req = PermissionRequest("tool", "read", "secret", PermissionCategory.ACCESS_CREDENTIAL, ResourceScope.CREDENTIAL)
    
    # An explicit high-priority user ALLOW rule overrides the default DENY and low-priority DENY
    assert engine.evaluate_request(req) == PermissionState.ALLOW

def test_workflow_specific_vs_general_rule():
    engine = PermissionEngine()
    engine.add_rule(PermissionRule(decision=PermissionState.DENY, priority=10))
    engine.add_rule(PermissionRule(decision=PermissionState.ALLOW, workflow_id="wf_1", priority=20))
    
    req1 = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE, workflow_id="wf_1")
    assert engine.evaluate_request(req1) == PermissionState.ALLOW
    
    req2 = PermissionRequest("tool", "read", "file.txt", PermissionCategory.READ, ResourceScope.FILE, workflow_id="wf_2")
    assert engine.evaluate_request(req2) == PermissionState.DENY

def test_scope_normalization_compatibility():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    # Passed as strings, engine compatibility layer should normalize to Enums
    state = engine.check_permission("read", "file.txt", tool_id="test_tool", category="read", resource_scope="file")
    assert state == PermissionState.ASK

def test_grant_session_permission():
    engine = PermissionEngine(autonomy_level=AutonomyLevel.SUPERVISED)
    req1 = PermissionRequest("pytest", "execute", "tests/", PermissionCategory.EXECUTE, ResourceScope.COMMAND, session_id="sess_1")
    req2 = PermissionRequest("pytest", "execute", "tests/", PermissionCategory.EXECUTE, ResourceScope.COMMAND, session_id="sess_2")
    
    # Initially both require ASK in SUPERVISED mode
    assert engine.evaluate_request(req1) == PermissionState.ASK
    assert engine.evaluate_request(req2) == PermissionState.ASK
    
    # Grant session-scoped permission for sess_1
    rule = engine.grant_session_permission(session_id="sess_1", tool_id="pytest")
    assert rule.decision == PermissionState.ALLOW
    assert rule.session_id == "sess_1"
    
    # Now sess_1 is ALLOW, sess_2 is still ASK
    assert engine.evaluate_request(req1) == PermissionState.ALLOW
    assert engine.evaluate_request(req2) == PermissionState.ASK

