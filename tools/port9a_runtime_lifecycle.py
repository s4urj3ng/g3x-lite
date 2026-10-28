"""PORT-9A / PORT-11B: offline lifecycle and safety model for CHDK runtime integration.

This is a pure-Python state model of four CHDK runtime interfaces:

  * task-creation interception (the CreateTask_my pattern),
  * the InitFileModules readiness gate (core_spytask_can_start),
  * SpyTask startup ordering,
  * the keyboard task (mykbd_task replacing PhySw) lifecycle.

PORT-11B refines the model using static evidence from PORT-11A:
  * static ROM evidence (STATIC_VERIFIED vs UNKNOWN) is modelled separately
    from runtime activation authorization (GM110C_PRECONDITIONS remains all
    False; STATIC_VERIFIED never implies runtime authorization);
  * the filesystem readiness contract distinguishes six explicit offline stages
    (created, started, init returned normally, mount observed, filesystem I/O
    ready, warm-restart storage safety) with boot-generation binding and
    rejection of constant-zero return codes or UI event 0x5006 as readiness proof;
  * the runtime hook safety contract models static vs runtime hook prerequisites,
    synthetic witness assertions for creator predecessor-call/guard preservation,
    and mandatory CreateTaskStrictly forwarding for PhySw.

It models ordering and safety rules only. It contains no firmware addresses,
reads no ROM or binary, starts no process and touches no hardware. Nothing here
installs, emulates or activates a firmware hook.
"""

from dataclasses import dataclass
from enum import Enum


class EvidenceStatus(Enum):
    STATIC_VERIFIED = "STATIC_VERIFIED"
    UNKNOWN = "UNKNOWN"


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
    READY = "READY"           # all 6 filesystem readiness stages established (latched)
    FAILED = "FAILED"         # file modules or readiness check failed (latched)


class Action(Enum):
    PASS_THROUGH = "PASS_THROUGH"   # stock firmware task created unmodified
    REPLACE = "REPLACE"             # routed to CHDK replacement task
    REJECT_DUPLICATE = "REJECT_DUPLICATE"  # duplicate creation blocked; no second task created


class CreationMechanism(Enum):
    CREATE_TASK = "CREATE_TASK"
    CREATE_TASK_STRICTLY = "CREATE_TASK_STRICTLY"


class FilesystemStage(Enum):
    NOT_CREATED = "NOT_CREATED"
    TASK_CREATED = "TASK_CREATED"
    TASK_STARTED = "TASK_STARTED"
    INIT_RETURNED_NORMALLY = "INIT_RETURNED_NORMALLY"
    MOUNT_OBSERVED = "MOUNT_OBSERVED"
    FS_IO_READY = "FS_IO_READY"
    WARM_RESTART_SAFE = "WARM_RESTART_SAFE"
    FAILED = "FAILED"


# Firmware task name -> CHDK replacement entry, as in the reference ports.
# Matching by name is a model simplification: the real hook compares the
# entry pointer passed in r3 (CHDK r5491 platform/g5x/sub/100c/boot.c).
REPLACEMENTS = {
    "InitFileModules": "init_file_modules_task",
    "PhySw": "mykbd_task",
}

EXPECTED_CREATION_MECHANISMS = {
    "InitFileModules": CreationMechanism.CREATE_TASK,
    "PhySw": CreationMechanism.CREATE_TASK_STRICTLY,
}


@dataclass(frozen=True)
class Preconditions:
    """Runtime authorization flags required before an interface may be modelled as usable.

    These represent full runtime activation authorization, NOT merely static ROM
    verification. All three remain False in GM110C_PRECONDITIONS.
    """
    create_task_prologue_verified: bool = False
    init_file_modules_entry_verified: bool = False
    physw_entry_verified: bool = False


# Current GM1.10C runtime authorization status: all three flags remain False.
GM110C_PRECONDITIONS = Preconditions()

# Only for exercising the model's happy path in tests. Not a claim about GM1.10C.
HYPOTHETICAL_ALL_VERIFIED = Preconditions(True, True, True)


@dataclass(frozen=True)
class StaticEvidenceProfile:
    """PORT-11A static ROM evidence vs unresolved runtime/readiness status (U1-U4).

    STATIC_VERIFIED applies strictly to static ROM bytes/instructions/call chains
    and NEVER implies runtime activation authorization.
    """
    u1_create_task_prologue_and_continuation: EvidenceStatus = EvidenceStatus.STATIC_VERIFIED
    u2_init_file_modules_entry: EvidenceStatus = EvidenceStatus.STATIC_VERIFIED
    u2_sd_fat_mount_readiness: EvidenceStatus = EvidenceStatus.UNKNOWN
    u3_physw_creator_entry_and_strictly_chain: EvidenceStatus = EvidenceStatus.STATIC_VERIFIED
    u4_spytask_creation_priority_and_dependencies: EvidenceStatus = EvidenceStatus.UNKNOWN

    @property
    def static_targets_verified(self):
        return (
            self.u1_create_task_prologue_and_continuation is EvidenceStatus.STATIC_VERIFIED
            and self.u2_init_file_modules_entry is EvidenceStatus.STATIC_VERIFIED
            and self.u3_physw_creator_entry_and_strictly_chain is EvidenceStatus.STATIC_VERIFIED
        )

    @property
    def authorizes_runtime_activation(self):
        """Static evidence NEVER authorizes runtime activation or hardware execution."""
        return False


GM110C_STATIC_EVIDENCE = StaticEvidenceProfile()
UNVERIFIED_STATIC_EVIDENCE = StaticEvidenceProfile(
    u1_create_task_prologue_and_continuation=EvidenceStatus.UNKNOWN,
    u2_init_file_modules_entry=EvidenceStatus.UNKNOWN,
    u2_sd_fat_mount_readiness=EvidenceStatus.UNKNOWN,
    u3_physw_creator_entry_and_strictly_chain=EvidenceStatus.UNKNOWN,
    u4_spytask_creation_priority_and_dependencies=EvidenceStatus.UNKNOWN,
)


@dataclass(frozen=True)
class HookSafetyContract:
    """Prerequisites for a future CreateTask runtime hook (PORT-11B Phase 4).

    Static instruction/call-chain properties established in PORT-11A are
    STATIC_VERIFIED in GM110C_HOOK_CONTRACT; all runtime-execution properties
    remain UNKNOWN unless established by repository evidence.
    """
    static_prologue_and_boundaries: EvidenceStatus = EvidenceStatus.STATIC_VERIFIED
    replay_semantics: EvidenceStatus = EvidenceStatus.STATIC_VERIFIED
    patch_execution_context_safe: EvidenceStatus = EvidenceStatus.UNKNOWN
    interrupt_masking_and_concurrency_safe: EvidenceStatus = EvidenceStatus.UNKNOWN
    icache_and_branch_predictor_coherent: EvidenceStatus = EvidenceStatus.UNKNOWN
    continuation_behavior_safe: EvidenceStatus = EvidenceStatus.UNKNOWN
    no_duplicate_task_creation_verified: EvidenceStatus = EvidenceStatus.STATIC_VERIFIED
    creator_predecessors_and_guards_preserved: EvidenceStatus = EvidenceStatus.STATIC_VERIFIED
    create_task_strictly_forwarding_safe: EvidenceStatus = EvidenceStatus.STATIC_VERIFIED

    @property
    def static_prerequisites_satisfied(self):
        return all(
            s is EvidenceStatus.STATIC_VERIFIED
            for s in (
                self.static_prologue_and_boundaries,
                self.replay_semantics,
                self.no_duplicate_task_creation_verified,
                self.creator_predecessors_and_guards_preserved,
                self.create_task_strictly_forwarding_safe,
            )
        )

    @property
    def runtime_prerequisites_satisfied(self):
        return all(
            s is EvidenceStatus.STATIC_VERIFIED
            for s in (
                self.patch_execution_context_safe,
                self.interrupt_masking_and_concurrency_safe,
                self.icache_and_branch_predictor_coherent,
                self.continuation_behavior_safe,
            )
        )

    @property
    def runtime_prerequisites_all_unknown(self):
        return all(
            s is EvidenceStatus.UNKNOWN
            for s in (
                self.patch_execution_context_safe,
                self.interrupt_masking_and_concurrency_safe,
                self.icache_and_branch_predictor_coherent,
                self.continuation_behavior_safe,
            )
        )

    @property
    def all_satisfied(self):
        return self.static_prerequisites_satisfied and self.runtime_prerequisites_satisfied


GM110C_HOOK_CONTRACT = HookSafetyContract()

SYNTHETIC_HOOK_CONTRACT_SATISFIED = HookSafetyContract(
    patch_execution_context_safe=EvidenceStatus.STATIC_VERIFIED,
    interrupt_masking_and_concurrency_safe=EvidenceStatus.STATIC_VERIFIED,
    icache_and_branch_predictor_coherent=EvidenceStatus.STATIC_VERIFIED,
    continuation_behavior_safe=EvidenceStatus.STATIC_VERIFIED,
)


@dataclass(frozen=True)
class CreatorCallContext:
    """Synthetic witness assertions for creator call context (NOT physical runtime proof).

    Used in offline scenario modelling to assert whether a candidate wrapper or
    call path preserved predecessor calls, checked the singleton guard, stored
    the returned task handle, and used the expected creation mechanism
    (CREATE_TASK for InitFileModules, CREATE_TASK_STRICTLY for PhySw).
    """
    mechanism: CreationMechanism = CreationMechanism.CREATE_TASK
    predecessor_calls_preserved: bool = True
    singleton_guard_checked: bool = True
    singleton_guard_clear: bool = True
    handle_stored_on_return: bool = True

    @property
    def is_synthetic_witness_only(self):
        return True


DEFAULT_INIT_FILE_MODULES_CONTEXT = CreatorCallContext(
    mechanism=CreationMechanism.CREATE_TASK,
)

DEFAULT_PHYSW_CONTEXT = CreatorCallContext(
    mechanism=CreationMechanism.CREATE_TASK_STRICTLY,
)


@dataclass(frozen=True)
class FilesystemReadinessState:
    """Explicit 6-stage offline filesystem readiness state for a single boot generation."""
    boot_generation: int = 1
    task_created: bool = False
    task_started: bool = False
    init_returned_normally: bool = False
    mount_observed: bool = False
    fs_io_ready: bool = False
    warm_restart_safe: bool = False
    failed: bool = False
    failure_reason: str = ""

    @property
    def stage(self):
        if self.failed:
            return FilesystemStage.FAILED
        if not self.task_created:
            return FilesystemStage.NOT_CREATED
        if not self.task_started:
            return FilesystemStage.TASK_CREATED
        if not self.init_returned_normally:
            return FilesystemStage.TASK_STARTED
        if not self.mount_observed:
            return FilesystemStage.INIT_RETURNED_NORMALLY
        if not self.fs_io_ready:
            return FilesystemStage.MOUNT_OBSERVED
        if not self.warm_restart_safe:
            return FilesystemStage.FS_IO_READY
        return FilesystemStage.WARM_RESTART_SAFE

    @property
    def is_ready(self):
        return (
            not self.failed
            and self.task_created
            and self.task_started
            and self.init_returned_normally
            and self.mount_observed
            and self.fs_io_ready
            and self.warm_restart_safe
        )


# Evidence required to promote each filesystem condition in a later milestone
# (offline specification only; no camera-side probes implemented).
FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS = (
    ("task_created",
     "Static creator call-chain proof + runtime observation that CreateTask was invoked for InitFileModules in current boot generation"),
    ("task_started",
     "Execution witness confirming task_InitFileModules entry ran in current boot generation after scheduler dispatch"),
    ("init_returned_normally",
     "Completion witness after sub_fc0d9ccc and sub_fc0d9cf6 return in current boot generation (note: sub_fc0d9ccc r0==0 is constant on normal return and does NOT prove mount)"),
    ("mount_observed",
     "Independent kernel/storage state proof that FAT volume mount succeeded (event 0x5006 alone is insufficient)"),
    ("fs_io_ready",
     "Verified non-destructive file open/read capability on mounted volume without contention or timeout"),
    ("warm_restart_safe",
     "Resolution of warm-restart SD host/card state preconditions (P11 SD1stInit predicate, P12 controller reset, P13 card state, P15 IRQ state) for current boot generation"),
)


@dataclass(frozen=True)
class InterceptDecision:
    task_name: str
    action: Action
    entry: str
    mechanism: CreationMechanism = CreationMechanism.CREATE_TASK


class LifecycleError(Exception):
    """An operation was requested out of order."""


class RuntimeLifecycle:
    def __init__(self, preconditions=GM110C_PRECONDITIONS,
                 static_evidence=GM110C_STATIC_EVIDENCE,
                 hook_contract=GM110C_HOOK_CONTRACT,
                 boot_generation=1):
        if boot_generation < 1:
            raise ValueError("boot_generation must be >= 1")
        self.preconditions = preconditions
        self.static_evidence = static_evidence
        self.hook_contract = hook_contract
        self.boot_generation = boot_generation
        self.core_initialized = False
        self.intercept = InterceptState.NOT_INSTALLED
        self.gate = GateState.NOT_ARMED
        self.spytask = TaskState.NOT_CREATED
        self.kbd = TaskState.NOT_CREATED
        self.fs = FilesystemReadinessState(boot_generation=boot_generation)
        self.fault = None
        self.trace = []
        self._stock_observed = []
        self._replaced = []

    @property
    def hardware_execution_authorized(self):
        """Offline model validation NEVER authorizes physical hardware execution."""
        return False

    @property
    def stock_owned_singletons(self):
        """Listed singleton tasks already created as stock tasks in this boot generation."""
        return frozenset(t for t in self._stock_observed if t in REPLACEMENTS)

    @property
    def replaced_singletons(self):
        """Listed singleton tasks already replaced by CHDK in this boot generation."""
        return frozenset(self._replaced)

    # -- helpers ---------------------------------------------------------

    def _log(self, event, detail=""):
        self.trace.append((event, detail))

    def _require_no_fault(self, what):
        if self.fault is not None:
            self._log("refused", f"{what}: fault latched ({self.fault})")
            return False
        return True

    def _check_generation(self, generation, what):
        eff_gen = self.boot_generation if generation is None else generation
        if eff_gen != self.boot_generation:
            reason = f"stale or mismatched boot generation {eff_gen} != {self.boot_generation} in {what}"
            self._fail_filesystem(reason)
            return False
        return True

    def _fail_filesystem(self, reason):
        if not self.fs.failed:
            self.fs = FilesystemReadinessState(
                boot_generation=self.boot_generation,
                task_created=self.fs.task_created,
                task_started=self.fs.task_started,
                init_returned_normally=self.fs.init_returned_normally,
                mount_observed=self.fs.mount_observed,
                fs_io_ready=self.fs.fs_io_ready,
                warm_restart_safe=self.fs.warm_restart_safe,
                failed=True,
                failure_reason=reason,
            )
        if self.gate is not GateState.FAILED:
            self.gate = GateState.FAILED
            self._log("fs_failed", reason)
        if self.spytask is TaskState.RUNNING:
            self.spytask = TaskState.FAILED
            self._log("spytask_failed", "filesystem readiness invalidated after READY")
        self.report_failure("InitFileModules", reason)

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

        Refused fail-closed unless the core is initialized, no fault is latched,
        the runtime authorization precondition is True, static U1 evidence is
        STATIC_VERIFIED, and a non-None HookSafetyContract with all static and
        runtime hook safety prerequisites satisfied is present.
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
            self._log("intercept_refused", "CreateTask runtime authorization not granted")
            return self.intercept
        if self.static_evidence is None or self.static_evidence.u1_create_task_prologue_and_continuation is not EvidenceStatus.STATIC_VERIFIED:
            self.intercept = InterceptState.REFUSED
            self._log("intercept_refused", "U1 static prologue/continuation not verified")
            return self.intercept
        if self.hook_contract is None or not self.hook_contract.all_satisfied:
            self.intercept = InterceptState.REFUSED
            self._log("intercept_refused", "hook safety contract prerequisites not satisfied")
            return self.intercept
        self.intercept = InterceptState.INSTALLED
        self._log("intercept_installed")
        return self.intercept

    def _entry_verified(self, task_name):
        if self.static_evidence is None:
            return False
        if task_name == "InitFileModules":
            return (
                self.preconditions.init_file_modules_entry_verified
                and self.static_evidence.u2_init_file_modules_entry is EvidenceStatus.STATIC_VERIFIED
            )
        if task_name == "PhySw":
            return (
                self.preconditions.physw_entry_verified
                and self.static_evidence.u3_physw_creator_entry_and_strictly_chain is EvidenceStatus.STATIC_VERIFIED
            )
        return False

    def _default_creator_context(self, task_name):
        if task_name == "InitFileModules":
            return DEFAULT_INIT_FILE_MODULES_CONTEXT
        if task_name == "PhySw":
            return DEFAULT_PHYSW_CONTEXT
        return CreatorCallContext()

    def _validate_creator_context(self, task_name, eff_context):
        """Validate synthetic creator-context witness assertions for a candidate replacement."""
        if not isinstance(eff_context, CreatorCallContext):
            self.report_failure(task_name, "invalid CreatorCallContext type")
            return False
        expected_mech = EXPECTED_CREATION_MECHANISMS.get(task_name)
        if expected_mech is not None and eff_context.mechanism is not expected_mech:
            self.report_failure(
                task_name,
                f"invalid creation mechanism {eff_context.mechanism.value}; expected {expected_mech.value}",
            )
            return False
        if not eff_context.predecessor_calls_preserved:
            self.report_failure(task_name, "creator predecessor calls bypassed")
            return False
        if not eff_context.singleton_guard_checked or not eff_context.singleton_guard_clear:
            self.report_failure(task_name, "creator singleton guard missing or already set")
            return False
        if task_name == "PhySw" and not eff_context.handle_stored_on_return:
            self.report_failure(task_name, "PhySw task handle store omitted")
            return False
        if (eff_context.mechanism is CreationMechanism.CREATE_TASK_STRICTLY
                and (self.hook_contract is None
                     or self.hook_contract.create_task_strictly_forwarding_safe is not EvidenceStatus.STATIC_VERIFIED)):
            self.report_failure(task_name, "CreateTaskStrictly forwarding not verified")
            return False
        return True

    def on_firmware_create_task(self, task_name, context=None):
        """Firmware asks to create `task_name`; decide which entry runs.

        Distinguishes observed stock creation (`self._stock_observed`) from
        intercepted CHDK singleton replacement creation (`self._replaced`):

          * `Action.PASS_THROUGH` (`entry="stock"`): stock Canon firmware task
            creation executes unmodified (`create_stock`). Returned for:
              - unlisted tasks;
              - any task when `intercept` is `NOT_INSTALLED` or `REFUSED`, or
                when the task's firmware entry is not verified (including
                repeated stock calls — an offline model without active
                interception control never claims to block Canon firmware);
              - a listed task whose stock singleton was already created before
                `install_intercept()` in the same `boot_generation`
                (`task_name in self._stock_observed`): because no runtime
                task-exit evidence exists for Canon's stock task, the model
                refuses to spawn a parallel CHDK replacement (`Action.REPLACE`
                forbidden), latches a fault, logs `stock_singleton_conflict` and
                `create_stock`, and passes through without claiming to block
                Canon's existing stock task;
              - a non-replaced listed task when a fault is already latched;
              - a candidate replacement call whose `CreatorCallContext` witness
                validation failed (which latches a fault and falls back to stock
                `create_stock` rather than claiming the task was blocked).
          * `Action.REPLACE` (`entry=REPLACEMENTS[task_name]`): first creation
            of a listed task under an installed intercept, with no prior stock
            singleton in `self._stock_observed`, no fault, and valid
            `CreatorCallContext`, is routed to the CHDK replacement task and
            recorded in `self._replaced`.
          * `Action.REJECT_DUPLICATE` (`entry="duplicate_blocked"`): returned
            ONLY when `self.intercept is InterceptState.INSTALLED`, target entry
            is verified, and `task_name` was already replaced once
            (`task_name in self._replaced`). Precedence rule (N2): duplicate
            rejection for an already-replaced singleton (`task_name in
            self._replaced`) is evaluated BEFORE post-fault `PASS_THROUGH`
            fallback so an active intercept hook never spawns a second instance
            of a task that CHDK already replaced, even if a fault was latched
            after that replacement.
        """
        eff_context = self._default_creator_context(task_name) if context is None else context
        mechanism = (
            eff_context.mechanism
            if isinstance(eff_context, CreatorCallContext)
            else CreationMechanism.CREATE_TASK
        )

        # Unlisted tasks always pass through to stock without creator-hook validation.
        if task_name not in REPLACEMENTS:
            self._stock_observed.append(task_name)
            self._log("create_stock", task_name)
            return InterceptDecision(task_name, Action.PASS_THROUGH, "stock", mechanism)

        # When intercept is not installed, is refused, or target entry is not
        # verified, the model has no interception control over this task and
        # merely observes stock creation (including repeated stock calls).
        if (self.intercept is not InterceptState.INSTALLED
                or not self._entry_verified(task_name)):
            self._stock_observed.append(task_name)
            self._log("create_stock", task_name)
            return InterceptDecision(task_name, Action.PASS_THROUGH, "stock", mechanism)

        # Precedence 1 (N2): Duplicate rejection applies when the intercept is
        # installed and this listed singleton task was already intercepted and
        # replaced (checked before post-fault PASS_THROUGH fallback).
        if task_name in self._replaced:
            self._log("duplicate_task_creation_blocked", task_name)
            return InterceptDecision(task_name, Action.REJECT_DUPLICATE, "duplicate_blocked", mechanism)

        # Precedence 2 (B2): If a stock singleton of this listed task was already
        # created before intercept installation in this boot generation, refuse
        # to create a parallel CHDK replacement (no stock task-exit evidence)
        # and do not claim the offline model can retroactively block stock Canon
        # firmware. Latch a fault and pass through.
        if task_name in self._stock_observed:
            self.report_failure(
                task_name,
                f"stock {task_name} singleton already created before intercept in "
                f"boot_generation={self.boot_generation}; replacement refused without "
                "stock task exit evidence",
            )
            self._stock_observed.append(task_name)
            self._log("stock_singleton_conflict", task_name)
            self._log("create_stock", task_name)
            return InterceptDecision(task_name, Action.PASS_THROUGH, "stock", mechanism)

        # Precedence 3: If a fault was latched (e.g., from an earlier creator-context
        # failure), interception falls back to stock pass-through rather than claiming
        # to block Canon firmware creation.
        if self.fault is not None:
            self._stock_observed.append(task_name)
            self._log("create_stock", task_name)
            return InterceptDecision(task_name, Action.PASS_THROUGH, "stock", mechanism)

        # Intercept is installed and target is eligible for replacement: validate
        # the synthetic creator-context witness assertions and forwarding mechanism.
        # On failure, _validate_creator_context latches a fault and falls back to
        # stock creation (never recorded in self._replaced).
        if not self._validate_creator_context(task_name, eff_context):
            self._stock_observed.append(task_name)
            self._log("create_stock", task_name)
            return InterceptDecision(task_name, Action.PASS_THROUGH, "stock", mechanism)

        if eff_context.mechanism is CreationMechanism.CREATE_TASK_STRICTLY:
            self._log("create_task_strictly_forwarded", task_name)

        self._replaced.append(task_name)
        entry = REPLACEMENTS[task_name]
        self._log("create_replaced", f"{task_name}->{entry}")
        if task_name == "InitFileModules":
            self.gate = GateState.ARMED
            self.fs = FilesystemReadinessState(
                boot_generation=self.boot_generation,
                task_created=True,
            )
            self._log("gate_armed")
            self._log("fs_task_created")
        elif task_name == "PhySw":
            self._start_kbd()
        return InterceptDecision(task_name, Action.REPLACE, entry, eff_context.mechanism)

    # -- InitFileModules 6-stage readiness contract ----------------------

    def init_file_modules_started(self, boot_generation=None):
        """Stage 2: InitFileModules task body began executing."""
        if self.gate not in (GateState.ARMED, GateState.READY) or not self.fs.task_created or self.fs.failed:
            self._log("gate_stage_ignored", "init_file_modules_started")
            return self.fs.stage
        if not self._check_generation(boot_generation, "init_file_modules_started"):
            return self.fs.stage
        if not self._require_no_fault("init_file_modules_started"):
            self._fail_filesystem("fault latched during init_file_modules_started")
            return self.fs.stage
        if not self.fs.task_started:
            self.fs = FilesystemReadinessState(
                boot_generation=self.boot_generation,
                task_created=True,
                task_started=True,
            )
            self._log("fs_task_started")
        return self.fs.stage

    def init_file_modules_returned(self, return_code=0, event_5006_posted=False,
                                   boot_generation=None, status="ok"):
        """Stage 3: InitFileModules initialization routines returned.

        Per PORT-11A S2B evidence:
          * sub_fc0d9ccc has zero conditional branches of its own and always
            returns r0 = 0 on normal return; return_code == 0 is NOT proof of
            FAT mount success.
          * Posting UI event 0x5006 is NOT independently sufficient to establish
            filesystem readiness.
        """
        if self.gate not in (GateState.ARMED, GateState.READY) or self.fs.failed:
            self._log("gate_stage_ignored", "init_file_modules_returned")
            return self.fs.stage
        if not self._check_generation(boot_generation, "init_file_modules_returned"):
            return self.fs.stage
        if not self.fs.task_started:
            self._fail_filesystem("init_file_modules_returned before task_started")
            return self.fs.stage
        if status != "ok" or return_code is None or return_code != 0:
            self._fail_filesystem(f"init return status={status!r} return_code={return_code!r}")
            return self.fs.stage
        if not self._require_no_fault("init_file_modules_returned"):
            self._fail_filesystem("fault latched during init_file_modules_returned")
            return self.fs.stage
        if not self.fs.init_returned_normally:
            self.fs = FilesystemReadinessState(
                boot_generation=self.boot_generation,
                task_created=True,
                task_started=True,
                init_returned_normally=True,
            )
            detail = "r0=0_constant_not_mount_proof"
            if event_5006_posted:
                detail += ";event_5006_not_sufficient"
            self._log("fs_init_returned_normally", detail)
        return self.fs.stage

    def record_mount_observation(self, observed, boot_generation=None, status="ok"):
        """Stage 4: Explicit, independent observation of SD/FAT mount completion."""
        if self.gate not in (GateState.ARMED, GateState.READY) or self.fs.failed:
            self._log("gate_stage_ignored", "record_mount_observation")
            return self.fs.stage
        if not self._check_generation(boot_generation, "record_mount_observation"):
            return self.fs.stage
        if not self.fs.init_returned_normally:
            self._fail_filesystem("mount observation before init_returned_normally")
            return self.fs.stage
        if status != "ok" or observed is not True:
            self._fail_filesystem(f"mount not established (observed={observed!r}, status={status!r})")
            return self.fs.stage
        if (self.static_evidence is None
                or self.static_evidence.u2_sd_fat_mount_readiness is not EvidenceStatus.STATIC_VERIFIED):
            self._fail_filesystem("U2 SD/FAT mount readiness evidence is UNKNOWN")
            return self.fs.stage
        if not self._require_no_fault("record_mount_observation"):
            self._fail_filesystem("fault latched during record_mount_observation")
            return self.fs.stage
        if not self.fs.mount_observed:
            self.fs = FilesystemReadinessState(
                boot_generation=self.boot_generation,
                task_created=True,
                task_started=True,
                init_returned_normally=True,
                mount_observed=True,
            )
            self._log("fs_mount_observed")
        return self.fs.stage

    def record_filesystem_io_readiness(self, ready, boot_generation=None, status="ok"):
        """Stage 5: Independent proof of filesystem I/O readiness."""
        if self.gate not in (GateState.ARMED, GateState.READY) or self.fs.failed:
            self._log("gate_stage_ignored", "record_filesystem_io_readiness")
            return self.fs.stage
        if not self._check_generation(boot_generation, "record_filesystem_io_readiness"):
            return self.fs.stage
        if not self.fs.mount_observed:
            self._fail_filesystem("fs_io_ready before mount_observed")
            return self.fs.stage
        if status != "ok" or ready is not True:
            self._fail_filesystem(f"filesystem I/O not ready (ready={ready!r}, status={status!r})")
            return self.fs.stage
        if not self._require_no_fault("record_filesystem_io_readiness"):
            self._fail_filesystem("fault latched during record_filesystem_io_readiness")
            return self.fs.stage
        if not self.fs.fs_io_ready:
            self.fs = FilesystemReadinessState(
                boot_generation=self.boot_generation,
                task_created=True,
                task_started=True,
                init_returned_normally=True,
                mount_observed=True,
                fs_io_ready=True,
            )
            self._log("fs_io_ready")
        return self.fs.stage

    def record_warm_restart_storage_safety(self, safe, boot_generation=None, status="ok"):
        """Stage 6: Warm-restart storage safety established; latches gate READY.

        Post-READY fail-closed rule: any subsequent call with a stale/mismatched
        `boot_generation`, `safe is not True`, `status != "ok"`, or a latched
        fault invalidates readiness (`GateState.FAILED`, `FilesystemStage.FAILED`).
        Valid same-generation repeat calls (`safe is True`, `status == "ok"`)
        remain idempotent.
        """
        if self.gate not in (GateState.ARMED, GateState.READY) or self.fs.failed:
            self._log("gate_stage_ignored", "record_warm_restart_storage_safety")
            return self.gate
        if not self._check_generation(boot_generation, "record_warm_restart_storage_safety"):
            return self.gate
        if not self.fs.fs_io_ready:
            self._fail_filesystem("warm_restart_safe before fs_io_ready")
            return self.gate
        if status != "ok" or safe is not True:
            self._fail_filesystem(f"warm-restart storage safety not established (safe={safe!r}, status={status!r})")
            return self.gate
        if not self._require_no_fault("record_warm_restart_storage_safety"):
            self._fail_filesystem("fault latched during record_warm_restart_storage_safety")
            return self.gate
        if not self.fs.warm_restart_safe:
            self.fs = FilesystemReadinessState(
                boot_generation=self.boot_generation,
                task_created=True,
                task_started=True,
                init_returned_normally=True,
                mount_observed=True,
                fs_io_ready=True,
                warm_restart_safe=True,
            )
            self.gate = GateState.READY
            self._log("fs_warm_restart_safe")
            self._log("fs_ready")
            self._try_run_spytask()
        return self.gate

    def file_modules_finished(self, success, boot_generation=None):
        """Evaluate final gate readiness after InitFileModules stock work finishes.

        Fail-closed contract (PORT-11B B1 fix):
          * A single `success=True` boolean NEVER synthesizes or auto-promotes
            Stages 2-6 (`task_started`, `init_returned_normally`, `mount_observed`,
            `fs_io_ready`, `warm_restart_safe`).
          * If `success` is not `True`, `boot_generation` mismatches, or a fault
            is latched — even after `GateState.READY` was previously reached —
            the gate transitions fail-closed to `GateState.FAILED` and
            `FilesystemStage.FAILED`.
          * If `success=True` is called before all 6 stages have been explicitly
            established for `boot_generation`, the gate fails closed because
            InitFileModules returning cannot by itself prove mount, I/O, or
            warm-restart safety.
        """
        if self.gate not in (GateState.ARMED, GateState.READY) or self.fs.failed:
            self._log("gate_signal_ignored", self.gate.value)
            return self.gate
        if not self._check_generation(boot_generation, "file_modules_finished"):
            return self.gate
        if success is not True or self.fault is not None:
            self._fail_filesystem("file modules not ready")
            return self.gate
        if not self.fs.is_ready:
            self._fail_filesystem(
                f"file_modules_finished(True) called at stage {self.fs.stage.value} "
                "without explicit 6-stage readiness proof"
            )
            return self.gate
        return self.gate

    # -- SpyTask --------------------------------------------------------

    def create_spytask(self):
        """Create SpyTask. It waits on the gate and runs only once READY and U4 is verified."""
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

    def _u4_permitted(self):
        """Fail-closed check for U4: UNKNOWN always blocks SpyTask (no legacy bypass)."""
        return (
            self.static_evidence is not None
            and self.static_evidence.u4_spytask_creation_priority_and_dependencies is EvidenceStatus.STATIC_VERIFIED
        )

    def _try_run_spytask(self):
        if (self.spytask is TaskState.WAITING_GATE
                and self.gate is GateState.READY
                and self.fs.is_ready
                and self.fault is None):
            if not self._u4_permitted():
                self._log("spytask_blocked_u4", "U4 SpyTask creation/priority/dependencies UNKNOWN")
                return
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


SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED = StaticEvidenceProfile(
    u1_create_task_prologue_and_continuation=EvidenceStatus.STATIC_VERIFIED,
    u2_init_file_modules_entry=EvidenceStatus.STATIC_VERIFIED,
    u2_sd_fat_mount_readiness=EvidenceStatus.STATIC_VERIFIED,
    u3_physw_creator_entry_and_strictly_chain=EvidenceStatus.STATIC_VERIFIED,
    u4_spytask_creation_priority_and_dependencies=EvidenceStatus.STATIC_VERIFIED,
)


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

    stage_order = (
        "fs_task_created",
        "fs_task_started",
        "fs_init_returned_normally",
        "fs_mount_observed",
        "fs_io_ready",
        "fs_warm_restart_safe",
        "fs_ready",
    )
    for earlier, later in zip(stage_order, stage_order[1:]):
        idx_e = first(earlier)
        idx_l = first(later)
        if idx_l is not None and (idx_e is None or idx_e > idx_l):
            errors.append(f"{later} before {earlier}")

    if spy is not None and (fs_ready is None or fs_ready > spy):
        errors.append("spytask_running before fs_ready")
    if spy is not None and (core is None or core > spy):
        errors.append("spytask_running before core_initialized")
    if kbd is not None and (intercept is None or intercept > kbd):
        errors.append("kbd_running without intercept_installed")
    for name in ("spytask_running", "kbd_running", "fs_ready",
                 "intercept_installed", "create_replaced",
                 "fs_mount_observed", "fs_io_ready", "fs_warm_restart_safe"):
        idx = first(name)
        if fault is not None and idx is not None and idx > fault:
            errors.append(f"{name} after fault")
    for name in ("core_initialized", "intercept_installed", "spytask_created",
                 "spytask_running", "kbd_running", "fs_ready", "gate_armed",
                 "fs_task_created", "fs_task_started", "fs_init_returned_normally",
                 "fs_mount_observed", "fs_io_ready", "fs_warm_restart_safe"):
        if events.count(name) > 1:
            errors.append(f"{name} occurs {events.count(name)} times")
    return errors
