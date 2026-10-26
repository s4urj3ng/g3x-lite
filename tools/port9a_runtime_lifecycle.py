"""PORT-9A: offline lifecycle model for CHDK runtime integration on the G3 X.

This is a pure-Python state model of four CHDK runtime interfaces:

  * task-creation interception (the CreateTask_my pattern),
  * the InitFileModules readiness gate (core_spytask_can_start),
  * SpyTask startup ordering,
  * the keyboard task (mykbd_task replacing PhySw) lifecycle.

It models ordering rules only. It contains no firmware addresses, reads no
ROM or binary, starts no process and touches no hardware. Nothing here
installs, emulates or activates a firmware hook. Interface status and evidence
for GM1.10C are in docs/PORT9A_RUNTIME_INTEGRATION_MAP.md.

Deliberate differences from upstream CHDK r5491 (core/main.c:101-103,136,156):
  * readiness is latched; SpyTask never clears it, so an early signal is not
    lost;
  * there is no timeout bypass: a SpyTask that times out on the gate fails
    instead of running.
"""

from dataclasses import dataclass
from enum import Enum


class TaskState(Enum):
    NOT_CREATED = "NOT_CREATED"
    WAITING_GATE = "WAITING_GATE"
    RUNNING = "RUNNING"
    FAILED = "FAILED"


class InterceptState(Enum):
    NOT_INSTALLED = "NOT_INSTALLED"
    INSTALLED = "INSTALLED"
    REFUSED = "REFUSED"


class GateState(Enum):
    NOT_ARMED = "NOT_ARMED"   # InitFileModules not routed to the CHDK replacement
    ARMED = "ARMED"           # replacement created, file modules not finished
    READY = "READY"           # file modules finished successfully (latched)
    FAILED = "FAILED"         # file modules reported failure (latched)


class Action(Enum):
    PASS_THROUGH = "PASS_THROUGH"
    REPLACE = "REPLACE"


# Firmware task name -> CHDK replacement entry, as in the reference ports.
# Matching by name is a model simplification: the real hook compares the
# entry pointer passed in r3 (CHDK r5491 platform/g5x/sub/100c/boot.c).
REPLACEMENTS = {
    "InitFileModules": "init_file_modules_task",
    "PhySw": "mykbd_task",
}


@dataclass(frozen=True)
class Preconditions:
    """Evidence that must exist before an interface may be modelled as usable.

    Each flag stands for a GM1.10C fact that has to be verified first.
    """
    create_task_prologue_verified: bool = False
    init_file_modules_entry_verified: bool = False
    physw_entry_verified: bool = False


# Current GM1.10C status: none of the three facts is verified (see the map).
GM110C_PRECONDITIONS = Preconditions()

# Only for exercising the model's happy path in tests. Not a claim about GM1.10C.
HYPOTHETICAL_ALL_VERIFIED = Preconditions(True, True, True)


@dataclass(frozen=True)
class InterceptDecision:
    task_name: str
    action: Action
    entry: str


class LifecycleError(Exception):
    """An operation was requested out of order."""


class RuntimeLifecycle:
    def __init__(self, preconditions=GM110C_PRECONDITIONS):
        self.preconditions = preconditions
        self.core_initialized = False
        self.intercept = InterceptState.NOT_INSTALLED
        self.gate = GateState.NOT_ARMED
        self.spytask = TaskState.NOT_CREATED
        self.kbd = TaskState.NOT_CREATED
        self.fault = None
        self.trace = []
        self._created = []

    # -- helpers ---------------------------------------------------------

    def _log(self, event, detail=""):
        self.trace.append((event, detail))

    def _require_no_fault(self, what):
        if self.fault is not None:
            self._log("refused", f"{what}: fault latched ({self.fault})")
            return False
        return True

    # -- core ------------------------------------------------------------

    def init_core(self):
        """Mark the CHDK core as initialized. Returns True only on first call."""
        if self.core_initialized:
            self._log("init_core_repeat")
            return False
        self.core_initialized = True
        self._log("core_initialized")
        return True

    def report_failure(self, component, reason):
        """Latch a fault. The first fault wins; downstream starts are refused."""
        if self.fault is None:
            self.fault = f"{component}: {reason}"
            self._log("fault", self.fault)
        if self.spytask is TaskState.WAITING_GATE:
            self.spytask = TaskState.FAILED
            self._log("spytask_failed", "fault while waiting on gate")

    # -- task-creation interception -------------------------------------

    def install_intercept(self):
        """Model installing the CreateTask interception. Idempotent.

        Refused unless the core is initialized, no fault is latched and the
        replayed firmware prologue is verified for this firmware.
        """
        if self.intercept is InterceptState.INSTALLED:
            self._log("install_intercept_repeat")
            return self.intercept
        if self.intercept is InterceptState.REFUSED:
            return self.intercept
        if not self.core_initialized:
            raise LifecycleError("install_intercept before init_core")
        if not self._require_no_fault("install_intercept"):
            return self.intercept
        if not self.preconditions.create_task_prologue_verified:
            self.intercept = InterceptState.REFUSED
            self._log("intercept_refused", "CreateTask prologue not verified")
            return self.intercept
        self.intercept = InterceptState.INSTALLED
        self._log("intercept_installed")
        return self.intercept

    def _entry_verified(self, task_name):
        if task_name == "InitFileModules":
            return self.preconditions.init_file_modules_entry_verified
        if task_name == "PhySw":
            return self.preconditions.physw_entry_verified
        return False

    def on_firmware_create_task(self, task_name):
        """Firmware asks to create `task_name`; decide which entry runs.

        Replaces only listed tasks, and only while the intercept is installed,
        the task's firmware entry is verified and no fault is latched.
        Everything else passes through to the stock entry.
        """
        replace = (
            self.intercept is InterceptState.INSTALLED
            and task_name in REPLACEMENTS
            and self._entry_verified(task_name)
            and self.fault is None
            and task_name not in self._created
        )
        self._created.append(task_name)
        if not replace:
            self._log("create_stock", task_name)
            return InterceptDecision(task_name, Action.PASS_THROUGH, "stock")
        entry = REPLACEMENTS[task_name]
        self._log("create_replaced", f"{task_name}->{entry}")
        if task_name == "InitFileModules":
            self.gate = GateState.ARMED
            self._log("gate_armed")
        elif task_name == "PhySw":
            self._start_kbd()
        return InterceptDecision(task_name, Action.REPLACE, entry)

    # -- InitFileModules gate -------------------------------------------

    def file_modules_finished(self, success):
        """The replacement InitFileModules task finished its stock work.

        Only an armed gate can become READY; success must be explicit.
        """
        if self.gate is not GateState.ARMED:
            self._log("gate_signal_ignored", self.gate.value)
            return self.gate
        if success and self.fault is None:
            self.gate = GateState.READY
            self._log("fs_ready")
            self._try_run_spytask()
        else:
            self.gate = GateState.FAILED
            self._log("fs_failed")
            self.report_failure("InitFileModules", "file modules not ready")
        return self.gate

    # -- SpyTask --------------------------------------------------------

    def create_spytask(self):
        """Create SpyTask. It waits on the gate and runs only once READY."""
        if self.spytask is not TaskState.NOT_CREATED:
            self._log("create_spytask_repeat", self.spytask.value)
            return self.spytask
        if not self.core_initialized:
            raise LifecycleError("create_spytask before init_core")
        if not self._require_no_fault("create_spytask"):
            return self.spytask
        self.spytask = TaskState.WAITING_GATE
        self._log("spytask_created")
        self._try_run_spytask()
        return self.spytask

    def spytask_gate_timeout(self):
        """SpyTask gave up waiting. Unlike upstream, it fails instead of running."""
        if self.spytask is TaskState.WAITING_GATE:
            self.spytask = TaskState.FAILED
            self._log("spytask_failed", "gate timeout")
            self.report_failure("SpyTask", "gate timeout")
        return self.spytask

    def _try_run_spytask(self):
        if (self.spytask is TaskState.WAITING_GATE
                and self.gate is GateState.READY
                and self.fault is None):
            self.spytask = TaskState.RUNNING
            self._log("spytask_running")

    # -- keyboard task --------------------------------------------------

    def _start_kbd(self):
        if self.kbd is TaskState.NOT_CREATED:
            self.kbd = TaskState.RUNNING
            self._log("kbd_running")

    @property
    def chdk_key_handling(self):
        """CHDK ALT-mode key handling needs both mykbd_task and a running SpyTask.

        Before that, mykbd_task must only pass keys through to Canon.
        """
        return (self.kbd is TaskState.RUNNING
                and self.spytask is TaskState.RUNNING
                and self.fault is None)


# -- trace invariants ---------------------------------------------------

def check_trace(trace):
    """Return a list of ordering violations in a trace (empty means valid)."""
    events = [e for e, _ in trace]
    errors = []

    def first(name):
        return events.index(name) if name in events else None

    core = first("core_initialized")
    fs_ready = first("fs_ready")
    spy = first("spytask_running")
    kbd = first("kbd_running")
    intercept = first("intercept_installed")
    fault = first("fault")

    if spy is not None and (fs_ready is None or fs_ready > spy):
        errors.append("spytask_running before fs_ready")
    if spy is not None and (core is None or core > spy):
        errors.append("spytask_running before core_initialized")
    if kbd is not None and (intercept is None or intercept > kbd):
        errors.append("kbd_running without intercept_installed")
    for name in ("spytask_running", "kbd_running", "fs_ready",
                 "intercept_installed", "create_replaced"):
        idx = first(name)
        if fault is not None and idx is not None and idx > fault:
            errors.append(f"{name} after fault")
    for name in ("core_initialized", "intercept_installed", "spytask_created",
                 "spytask_running", "kbd_running", "fs_ready", "gate_armed"):
        if events.count(name) > 1:
            errors.append(f"{name} occurs {events.count(name)} times")
    return errors
