from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
    invalid = 'invalid'
class RecalcStatus(str, Enum):
    running = 'running'
    waiting_approval = 'waiting_approval'
    switched = 'switched'
class QuarantineStatus(str, Enum):
    active = 'active'
    restored = 'restored'
