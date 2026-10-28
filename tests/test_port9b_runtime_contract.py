"""PORT-9B: tests for tools/port9b_runtime_contract.py.

Runs on any clean clone, with or without a bootstrapped chdk-port/: platform
sources are rebuilt in memory from vendor/ + patches (or bootstrapped into
temporary directories) and the tracked boot_prototype.c is verified against
its pinned SHA-256 digest.
Standard library only; no subprocess, ROM, binary, build or hardware access.

Run:
  python3 -B -m unittest discover -s tests -p 'test_port9b_*.py' -v
"""

import ast
from dataclasses import replace
import io
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "port9b_runtime_contract.py"
sys.path.insert(0, str(REPO_ROOT / "tools"))

import bootstrap_chdk_platform as boot  # noqa: E402
import port9a_runtime_lifecycle as rt  # noqa: E402
import port9b_runtime_contract as pc  # noqa: E402

KBD_C = "platform/g3x/kbd.c"
KBD_H = "platform/g3x/platform_kbd.h"
CAM_H = "platform/g3x/platform_camera.h"
SPYTASK_OFF = '// "    bl      CreateTask_spytask\\n"'
SPYTASK_ON = '"    bl      CreateTask_spytask\\n"'
PHYSW_CALL = '"    bl      sub_fc1283d2\\n"'


def in_memory():
    return pc.load_sources()[0]


def mutate(sources, rel, old, new):
    text = sources[rel]
    if text.count(old) != 1:
        raise AssertionError(f"mutation anchor {old!r} not unique in {rel}")
    changed = dict(sources)
    changed[rel] = text.replace(old, new)
    return changed


def failed(findings):
    return {f.check for f in pc.violations(findings)}


class Positive(unittest.TestCase):
    def test_in_memory_contract_holds(self):
        findings = pc.check_contract(in_memory())
        self.assertEqual(pc.violations(findings), [])
        self.assertTrue(any(f.check == "C4.defaults_inert" for f in findings))
        self.assertTrue(any(f.check == "C1.prototype_sha256" and f.ok for f in findings))

    def test_cli_in_memory_exit_zero(self):
        out = io.StringIO()
        self.assertEqual(pc.run(out=out), 0)
        text = out.getvalue()
        self.assertIn("SOURCES in-memory (vendor + patches) + tracked boot_prototype.c", text)
        self.assertIn("recognized activation markers absent", text)
        self.assertIn("RESULT ok", text)

    def test_runtime_facts_are_reported_unverified(self):
        findings = pc.check_contract(in_memory())
        runtime = [f for f in findings if f.check in
                   {f"C5.{fid}" for fid, _, _ in pc.UNVERIFIED_RUNTIME_FACTS}]
        self.assertEqual(len(runtime), len(pc.UNVERIFIED_RUNTIME_FACTS))
        for f in runtime:
            self.assertEqual(f.label, pc.UNVERIFIED_RUNTIME)
            self.assertIn("UNKNOWN", f.detail)
        # No interface status is claimed as verified at runtime.
        self.assertFalse(any(f.label == pc.VERIFIED_SOURCE and f.check.startswith("C5.U")
                             for f in findings))

    def test_source_facts_match_port9a_map(self):
        src = in_memory()
        proto = src[pc.PROTOTYPE]
        self.assertTrue(pc.defines_function(proto, "CreateTask_spytask"))
        self.assertFalse(pc.asm_calls(proto, "CreateTask_spytask"))
        self.assertFalse(pc.has_spytask_activation_marker(src))
        self.assertTrue(pc.asm_calls(proto, "sub_fc1283d2"))
        self.assertFalse(pc.defines_function(src[KBD_C], "mykbd_task"))
        self.assertTrue(pc.defines_function(src[KBD_C], "wrap_kbd_p1_f"))

    def test_comment_only_mentions_are_not_activations(self):
        src = mutate(in_memory(), KBD_C, "long kbd_new_state",
                     "// void mykbd_task() { } core_spytask_can_start(); CreateTask_my\n"
                     "/* bl.w CreateTask_spytask; _CreateTask(\"SpyTask\", 0, 0, spytask, 0); */\n"
                     "long kbd_new_state")
        self.assertEqual(pc.violations(pc.check_contract(src)), [])

    def test_hypothetical_requires_opt_in_and_is_labelled(self):
        findings = pc.check_contract(in_memory(), rt.HYPOTHETICAL_ALL_VERIFIED,
                                     allow_hypothetical=True)
        self.assertEqual(pc.violations(findings), [])
        by_check = {f.check: f for f in findings}
        self.assertEqual(by_check["C4.preconditions"].label, pc.HYPOTHETICAL)
        self.assertEqual(by_check["C4.model_trace"].label, pc.HYPOTHETICAL)
        self.assertNotIn("C4.defaults_inert", by_check)
        for fid, flag, _ in pc.UNVERIFIED_RUNTIME_FACTS:
            expected = pc.HYPOTHETICAL if flag else pc.UNVERIFIED_RUNTIME
            self.assertEqual(by_check[f"C5.{fid}"].label, expected)

    def test_hypothetical_allows_matching_source_activation(self):
        # Full hypothetical activation requires explicitly passing BOTH hypothetical
        # preconditions AND the synthetic static/hook contracts (PORT-11B B3).
        src = mutate(in_memory(), KBD_C, "int physw0_override;",
                     'int physw0_override;\nvoid f(void) { asm volatile("bl CreateTask_spytask\\n"); }')
        findings = pc.check_contract(
            src,
            rt.HYPOTHETICAL_ALL_VERIFIED,
            allow_hypothetical=True,
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        self.assertEqual(pc.violations(findings), [])
        by_check = {f.check: f for f in findings}
        self.assertEqual(by_check["C4.preconditions"].label, pc.HYPOTHETICAL)
        self.assertEqual(by_check["C4.model_trace"].label, pc.HYPOTHETICAL)
        self.assertEqual(by_check["C5.U4"].label, pc.HYPOTHETICAL)
        self.assertEqual(by_check["C6.hook_safety_contract"].label, pc.HYPOTHETICAL)
        self.assertEqual(by_check["C6.fs_readiness_contract"].label, pc.HYPOTHETICAL)

    def test_b3_hypothetical_never_substitutes_caller_supplied_unknown_contracts(self):
        # Independent Review Blocker B3:
        # Calling check_contract() with core_spytask() in sources,
        # preconditions=HYPOTHETICAL_ALL_VERIFIED, allow_hypothetical=True,
        # static_evidence=UNVERIFIED_STATIC_EVIDENCE, and hook_contract=GM110C_HOOK_CONTRACT
        # must NEVER silently replace the supplied contracts with synthetic ones,
        # and MUST reject the unjustified SpyTask activation (C3.spytask fails).
        src = mutate(
            in_memory(),
            KBD_C,
            "int physw0_override;",
            "int physw0_override;\nvoid f(void) { core_spytask(); }",
        )
        findings_unverified = pc.check_contract(
            src,
            preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
            allow_hypothetical=True,
            static_evidence=rt.UNVERIFIED_STATIC_EVIDENCE,
            hook_contract=rt.GM110C_HOOK_CONTRACT,
        )
        self.assertIn("C3.spytask", failed(findings_unverified))
        self.assertIn("C6.fs_readiness_contract", failed(findings_unverified))

        # Even with default GM110C_STATIC_EVIDENCE and GM110C_HOOK_CONTRACT,
        # allow_hypothetical=True must keep runtime prerequisites UNKNOWN and
        # reject core_spytask() activation.
        findings_gm110c = pc.check_contract(
            src,
            preconditions=rt.HYPOTHETICAL_ALL_VERIFIED,
            allow_hypothetical=True,
            static_evidence=rt.GM110C_STATIC_EVIDENCE,
            hook_contract=rt.GM110C_HOOK_CONTRACT,
        )
        self.assertEqual(failed(findings_gm110c), {"C3.spytask"})
        by_check = {f.check: f for f in findings_gm110c}
        self.assertIn("allows nothing", by_check["C4.model_trace"].detail)
        self.assertEqual(by_check["C5.U4"].label, pc.UNVERIFIED_RUNTIME)
        self.assertEqual(by_check["C6.hook_safety_contract"].label, pc.UNVERIFIED_RUNTIME)
        self.assertEqual(by_check["C6.fs_readiness_contract"].label, pc.UNVERIFIED_RUNTIME)


class PreconditionPolicy(unittest.TestCase):
    def test_default_preconditions_are_port9a_defaults(self):
        self.assertEqual(pc.check_contract.__defaults__[0], rt.GM110C_PRECONDITIONS)
        self.assertEqual(pc._active_preconditions(rt.GM110C_PRECONDITIONS), [])

    def test_all_verified_refused_by_default(self):
        findings = pc.check_contract(in_memory(), rt.HYPOTHETICAL_ALL_VERIFIED)
        self.assertEqual(failed(findings), {"C4.preconditions"})

    def test_refused_preconditions_preserve_effective_default_labels_and_inertness(self):
        findings = pc.check_contract(in_memory(), rt.HYPOTHETICAL_ALL_VERIFIED,
                                     allow_hypothetical=False)
        self.assertEqual(failed(findings), {"C4.preconditions"})
        by_check = {f.check: f for f in findings}
        self.assertEqual(by_check["C4.preconditions"].label, pc.VERIFIED_SOURCE)
        self.assertFalse(by_check["C4.preconditions"].ok)
        self.assertEqual(by_check["C4.model_trace"].label, pc.VERIFIED_SOURCE)
        self.assertTrue(by_check["C4.model_trace"].ok)
        self.assertIn("allows nothing", by_check["C4.model_trace"].detail)
        self.assertIn("C4.defaults_inert", by_check)
        self.assertTrue(by_check["C4.defaults_inert"].ok)
        self.assertEqual(by_check["C4.defaults_inert"].label, pc.VERIFIED_SOURCE)

    def test_single_flag_refused_by_default(self):
        for name in ("create_task_prologue_verified", "init_file_modules_entry_verified",
                     "physw_entry_verified"):
            with self.subTest(flag=name):
                pre = rt.Preconditions(**{name: True})
                findings = pc.check_contract(in_memory(), pre)
                self.assertEqual(failed(findings), {"C4.preconditions"})
                by_check = {f.check: f for f in findings}
                self.assertEqual(by_check["C4.model_trace"].label, pc.VERIFIED_SOURCE)
                self.assertIn("C4.defaults_inert", by_check)

    def test_refused_preconditions_do_not_relax_source_checks(self):
        src = mutate(in_memory(), KBD_C, "int physw0_override;",
                     'int physw0_override;\nvoid f(void) { asm volatile("bl CreateTask_spytask\\n"); }')
        findings = pc.check_contract(src, rt.HYPOTHETICAL_ALL_VERIFIED)
        self.assertEqual(failed(findings), {"C4.preconditions", "C3.spytask"})

    def test_partial_hypothesis_still_forbids_unrelated_interfaces(self):
        # PhySw entry alone cannot start mykbd_task: the intercept is still refused.
        src = mutate(in_memory(), KBD_C, "int physw0_override;",
                     "int physw0_override;\nvoid mykbd_task(void) { }")
        pre = rt.Preconditions(physw_entry_verified=True)
        findings = pc.check_contract(src, pre, allow_hypothetical=True)
        self.assertEqual(failed(findings), {"C3.kbd"})


class SourceViolations(unittest.TestCase):
    def assertOnlyViolation(self, src, check):
        self.assertEqual(failed(pc.check_contract(src)), {check})

    def assertViolations(self, src, expected_checks):
        self.assertEqual(failed(pc.check_contract(src)), set(expected_checks))

    def test_enabled_spytask_creation_in_prototype_fails_integrity_and_c3(self):
        self.assertViolations(
            mutate(in_memory(), pc.PROTOTYPE, SPYTASK_OFF, SPYTASK_ON),
            {"C1.prototype_sha256", "C3.spytask"},
        )

    def test_spytask_via_blx_in_prototype(self):
        self.assertViolations(
            mutate(in_memory(), pc.PROTOTYPE, SPYTASK_OFF, '"    blx     CreateTask_spytask\\n"'),
            {"C1.prototype_sha256", "C3.spytask"},
        )

    def test_spytask_counterexamples_rejected(self):
        counterexamples = [
            ("b_w", 'asm volatile("    b.w     CreateTask_spytask\\n");'),
            ("bl_w", 'asm volatile("    bl.w    CreateTask_spytask\\n");'),
            ("b_plain", 'asm volatile("    b       CreateTask_spytask\\n");'),
            ("bx_plain", 'asm volatile("    bx      CreateTask_spytask\\n");'),
            ("ldr_literal_blx", 'asm volatile("    ldr r3, =CreateTask_spytask; blx r3\\n");'),
            ("second_insn_in_string", 'asm volatile("    nop\\n    bl CreateTask_spytask\\n");'),
            ("semicolon_second_insn", 'asm volatile("    nop; bl CreateTask_spytask\\n");'),
            ("label_before_call", 'asm volatile("1:  bl      CreateTask_spytask\\n");'),
            ("asm_bl_core_spytask", 'asm volatile("    bl      core_spytask\\n");'),
            ("asm_bl_spytask", 'asm volatile("    bl      spytask\\n");'),
            ("c_call_create_task_spytask", "CreateTask_spytask();"),
            ("c_call_core_spytask", "core_spytask();"),
            ("c_call_spytask", "spytask(0, 0, 0, 0, 0, 0);"),
            ("c_call_underscore_createtask", '_CreateTask("SpyTask", 0x19, 0x2000, spytask, 0);'),
        ]
        for label, snippet in counterexamples:
            with self.subTest(case=label):
                src = mutate(
                    in_memory(),
                    KBD_C,
                    "int physw0_override;",
                    f"int physw0_override;\nvoid trigger_{label}(void) {{ {snippet} }}",
                )
                self.assertOnlyViolation(src, "C3.spytask")
                proto_src = mutate(in_memory(), pc.PROTOTYPE, SPYTASK_OFF, snippet)
                self.assertViolations(proto_src, {"C1.prototype_sha256", "C3.spytask"})

    def test_prototype_reintroducing_startdiskboot_rejected(self):
        src = mutate(
            in_memory(),
            pc.PROTOTYPE,
            '"    bl      sub_fc05bb94\\n"',
            '"    bl      sub_fc05bb94\\n"\n        "    bl      sub_fc05bbea\\n"',
        )
        self.assertOnlyViolation(src, "C1.prototype_sha256")

    def test_prototype_bss_bound_mutation_rejected(self):
        src = mutate(
            in_memory(),
            pc.PROTOTYPE,
            '"    ldr     r1, =0x003489b4\\n"',
            '"    ldr     r1, =0x00400000\\n"',
        )
        self.assertOnlyViolation(src, "C1.prototype_sha256")

    def test_mykbd_task_defined(self):
        self.assertOnlyViolation(
            mutate(in_memory(), KBD_C, "int physw0_override;",
                   "int physw0_override;\nvoid mykbd_task(void) { }"),
            "C3.kbd")

    def test_readiness_signal_added(self):
        self.assertOnlyViolation(
            mutate(in_memory(), KBD_C, "int physw0_override;",
                   "int physw0_override;\nvoid f(void) { core_spytask_can_start(); }"),
            "C3.gate")

    def test_create_task_hook_added(self):
        self.assertOnlyViolation(
            mutate(in_memory(), KBD_C, "int physw0_override;",
                   "int physw0_override;\nvoid CreateTask_my(void) { }"),
            "C3.intercept")

    def test_stock_physw_creator_removed(self):
        self.assertViolations(
            mutate(in_memory(), pc.PROTOTYPE, PHYSW_CALL, "// " + PHYSW_CALL),
            {"C1.prototype_sha256", "C3.stock_physw"},
        )

    def test_wrong_firmware_platformsub(self):
        self.assertOnlyViolation(mutate(in_memory(), CAM_H, '"110c"', '"110e"'), "C2.platform")

    def test_dryos_flag_cleared(self):
        self.assertOnlyViolation(
            mutate(in_memory(), CAM_H, "#define CAM_DRYOS                           1",
                   "#define CAM_DRYOS                           0"),
            "C2.dryos")

    def test_unpatched_mask_misses_playback(self):
        # PORT-7B preimage value: Playback (an ALT option) not overridable.
        self.assertOnlyViolation(mutate(in_memory(), KBD_H, "0x000533F9", "0x000433F9"),
                                 "C2.alt_in_mask0")

    def test_power_in_mask(self):
        self.assertOnlyViolation(mutate(in_memory(), KBD_H, "0x000533F9", "0x000733F9"),
                                 "C2.power_excluded")

    def test_nonzero_secondary_mask(self):
        self.assertOnlyViolation(
            mutate(in_memory(), KBD_H, "#define KEYS_MASK1 (0x00000000)",
                   "#define KEYS_MASK1 (0x00000001)"),
            "C2.mask12_zero")

    def test_alt_option_missing_from_keymap(self):
        self.assertOnlyViolation(
            mutate(in_memory(), KBD_C, "    { 0, KEY_PLAYBACK        ,0x00010000 },", ""),
            "C2.alt_in_keymap")

    def test_missing_source_fails_without_crashing(self):
        src = in_memory()
        del src[KBD_H]
        bad = failed(pc.check_contract(src))
        self.assertIn("C1.sources", bad)
        self.assertIn("C2.keys", bad)

    def test_duplicate_define_cannot_be_evaluated(self):
        src = mutate(in_memory(), KBD_H, "#define KEYS_MASK2 (0x00000000)",
                     "#define KEYS_MASK2 (0x00000000)\n#define KEYS_MASK0 (0x000533F9)")
        self.assertEqual(failed(pc.check_contract(src)), {"C2.keys"})


class RegistryViolations(unittest.TestCase):
    def test_registry_with_address_rejected(self):
        facts = pc.UNVERIFIED_RUNTIME_FACTS + (("U9", None, "PhySw entry 0xfc1283ad"),)
        self.assertEqual(failed(pc.check_contract(in_memory(), runtime_facts=facts)), {"C5.U9"})

    def test_registry_missing_precondition_rejected(self):
        facts = pc.UNVERIFIED_RUNTIME_FACTS[1:]
        self.assertEqual(failed(pc.check_contract(in_memory(), runtime_facts=facts)),
                         {"C5.coverage"})

    def test_registry_unknown_flag_rejected(self):
        facts = pc.UNVERIFIED_RUNTIME_FACTS + (("U9", "made_up_flag", "x"),)
        self.assertEqual(failed(pc.check_contract(in_memory(), runtime_facts=facts)),
                         {"C5.U9", "C5.coverage"})

    def test_port11b_static_vs_runtime_contract_checks_present(self):
        findings = pc.check_contract(in_memory())
        by_check = {f.check: f for f in findings}
        self.assertTrue(by_check["C4.static_vs_runtime_auth"].ok)
        self.assertEqual(by_check["C4.static_vs_runtime_auth"].label, pc.STATIC_VERIFIED)
        self.assertTrue(by_check["C6.hook_safety_contract"].ok)
        self.assertEqual(by_check["C6.hook_safety_contract"].label, pc.UNVERIFIED_RUNTIME)
        self.assertIn("does not prove hardware readiness", by_check["C6.hook_safety_contract"].detail)
        self.assertTrue(by_check["C6.fs_readiness_contract"].ok)
        self.assertEqual(by_check["C6.fs_readiness_contract"].label, pc.UNVERIFIED_RUNTIME)
        self.assertIn("does not prove hardware readiness", by_check["C6.fs_readiness_contract"].detail)

    def test_port11b_prematurely_claiming_hook_runtime_satisfied_fails_c6(self):
        findings = pc.check_contract(
            in_memory(),
            hook_contract=rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
        )
        self.assertEqual(failed(findings), {"C6.hook_safety_contract"})

    def test_n1_partial_promotion_of_hook_runtime_fields_fails_c6(self):
        # Independent Review N1: C6.hook_safety_contract must verify that EACH
        # of the four runtime safety fields in hook_contract remains UNKNOWN,
        # not merely that not all four are satisfied.
        self.assertTrue(rt.GM110C_HOOK_CONTRACT.runtime_prerequisites_all_unknown)
        runtime_fields = (
            "patch_execution_context_safe",
            "interrupt_masking_and_concurrency_safe",
            "icache_and_branch_predictor_coherent",
            "continuation_behavior_safe",
        )
        # Promoting any single runtime field (1 of 4) must fail C6.hook_safety_contract.
        for field_name in runtime_fields:
            with self.subTest(promoted_one=field_name):
                mutated = replace(
                    rt.GM110C_HOOK_CONTRACT,
                    **{field_name: rt.EvidenceStatus.STATIC_VERIFIED},
                )
                self.assertFalse(mutated.runtime_prerequisites_all_unknown)
                self.assertFalse(mutated.runtime_prerequisites_satisfied)
                findings = pc.check_contract(in_memory(), hook_contract=mutated)
                self.assertEqual(failed(findings), {"C6.hook_safety_contract"})

        # Promoting 3 of 4 runtime fields (leaving only 1 UNKNOWN) must also fail C6.hook_safety_contract.
        for omitted_field in runtime_fields:
            with self.subTest(promoted_three_except=omitted_field):
                mutated_three = replace(
                    rt.SYNTHETIC_HOOK_CONTRACT_SATISFIED,
                    **{omitted_field: rt.EvidenceStatus.UNKNOWN},
                )
                self.assertFalse(mutated_three.runtime_prerequisites_all_unknown)
                self.assertFalse(mutated_three.runtime_prerequisites_satisfied)
                findings = pc.check_contract(in_memory(), hook_contract=mutated_three)
                self.assertEqual(failed(findings), {"C6.hook_safety_contract"})

    def test_port11b_prematurely_claiming_u2_or_u4_verified_fails_c6(self):
        findings = pc.check_contract(
            in_memory(),
            static_evidence=rt.SYNTHETIC_ALL_STATIC_AND_DYNAMIC_VERIFIED,
        )
        self.assertEqual(failed(findings), {"C6.fs_readiness_contract"})



class TargetTree(unittest.TestCase):
    """Read-only validation of a PORT-8A bootstrapped tree in a temp dir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="port9b-")
        self.root = Path(self._tmp.name)
        self.target = self.root / "chdk-port"
        self.target.mkdir()
        self.assertEqual(boot.run(self.target, out=io.StringIO()), 0)
        proto = self.target / pc.PROTOTYPE
        proto.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / "chdk-port" / pc.PROTOTYPE, proto)

    def tearDown(self):
        self._tmp.cleanup()

    def run_tool(self, **kwargs):
        out = io.StringIO()
        return pc.run(self.target, out=out, **kwargs), out.getvalue()

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in sorted(self.root.rglob("*")) if p.is_file()}

    def test_bootstrapped_tree_holds_and_is_not_written(self):
        before = self.snapshot()
        code, out = self.run_tool()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.snapshot(), before)

    def test_tree_matches_in_memory_sources(self):
        self.assertEqual(pc.load_sources(self.target)[0], in_memory())

    def test_pending_patch_is_integrity_error(self):
        kbd_h = self.target / KBD_H
        kbd_h.write_bytes((boot.DEFAULT_MANIFEST.parent / KBD_H).read_bytes())
        code, out = self.run_tool()
        self.assertEqual(code, 3)
        self.assertIn("ADVANCE", out)

    def test_modified_source_is_integrity_error(self):
        (self.target / KBD_C).write_text("// edited\n")
        code, out = self.run_tool()
        self.assertEqual(code, 3)
        self.assertIn("CONFLICT", out)

    def test_missing_source_is_integrity_error(self):
        (self.target / "platform/g3x/lib.c").unlink()
        self.assertEqual(self.run_tool()[0], 3)

    def test_missing_prototype_is_integrity_error(self):
        (self.target / pc.PROTOTYPE).unlink()
        code, out = self.run_tool()
        self.assertEqual(code, 3)
        self.assertIn("prototype", out)

    def test_symlinked_prototype_is_integrity_error(self):
        proto = self.target / pc.PROTOTYPE
        proto.unlink()
        proto.symlink_to(REPO_ROOT / "chdk-port" / pc.PROTOTYPE)
        self.assertEqual(self.run_tool()[0], 3)

    def test_symlinked_prototype_parent_dir_is_integrity_error(self):
        sub_dir = self.target / "platform/g3x/sub"
        shutil.rmtree(sub_dir)
        sub_dir.symlink_to(REPO_ROOT / "chdk-port/platform/g3x/sub")
        code, out = self.run_tool()
        self.assertEqual(code, 3)
        self.assertIn("symlink", out)

    def test_modified_prototype_startdiskboot_in_tree_is_integrity_error(self):
        proto = self.target / pc.PROTOTYPE
        proto.write_text(
            proto.read_text().replace(
                '"    bl      sub_fc05bb94\\n"',
                '"    bl      sub_fc05bb94\\n"\n        "    bl      sub_fc05bbea\\n"',
            )
        )
        code, out = self.run_tool()
        self.assertEqual(code, 3)
        self.assertIn("sha256 mismatch", out)

    def test_modified_prototype_bss_bound_in_tree_is_integrity_error(self):
        proto = self.target / pc.PROTOTYPE
        proto.write_text(
            proto.read_text().replace(
                '"    ldr     r1, =0x003489b4\\n"',
                '"    ldr     r1, =0x00400000\\n"',
            )
        )
        code, out = self.run_tool()
        self.assertEqual(code, 3)
        self.assertIn("sha256 mismatch", out)

    def test_modified_prototype_in_default_repo_root_is_integrity_error(self):
        fake_repo = self.root / "fake_repo"
        (fake_repo / "chdk-port" / pc.PROTOTYPE).parent.mkdir(parents=True, exist_ok=True)
        proto = fake_repo / "chdk-port" / pc.PROTOTYPE
        proto.write_text(
            (REPO_ROOT / "chdk-port" / pc.PROTOTYPE).read_text().replace(
                '"    ldr     r1, =0x003489b4\\n"',
                '"    ldr     r1, =0x00400000\\n"',
            )
        )
        shutil.copytree(REPO_ROOT / "patches", fake_repo / "patches")
        with self.assertRaisesRegex(pc.ContractError, "sha256 mismatch"):
            pc.load_sources(target_root=None, repo_root=fake_repo)

    def test_enabled_spytask_in_tree_is_integrity_error(self):
        proto = self.target / pc.PROTOTYPE
        proto.write_text(proto.read_text().replace(SPYTASK_OFF, SPYTASK_ON))
        code, out = self.run_tool()
        self.assertEqual(code, 3)
        self.assertIn("sha256 mismatch", out)

    def test_tampered_vendor_is_integrity_error(self):
        vendor = self.root / "vendor"
        shutil.copytree(boot.DEFAULT_MANIFEST.parent, vendor)
        manifest = vendor / "MANIFEST.json"
        data = json.loads(manifest.read_text())
        data["files"][0]["final_sha256"] = "0" * 64
        data["files"][0]["baseline_sha256"] = "0" * 64
        manifest.write_text(json.dumps(data))
        code, out = self.run_tool(manifest_path=manifest)
        self.assertEqual(code, 3)
        self.assertIn("integrity", out)


class OfflineOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TOOL_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_imports_are_allowlisted(self):
        allowed = {"argparse", "dataclasses", "pathlib", "re", "sys",
                   "bootstrap_chdk_platform", "port9a_runtime_lifecycle"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module.split(".")[0]}
            else:
                continue
            self.assertLessEqual(names, allowed)

    def test_no_write_or_dynamic_execution_calls(self):
        banned = {"open", "exec", "eval", "compile", "__import__",
                  "write_text", "write_bytes", "unlink", "mkdir", "rename", "run"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if name == "run" and isinstance(fn, ast.Name):
                    continue  # main() -> local run()
                self.assertNotIn(name, banned)

    def test_firmware_symbols_come_from_tracked_prototype(self):
        # Any sub_XXXXXXXX the tool names must already be in tracked source;
        # no GM1.10E or new runtime address is introduced here.
        proto = (REPO_ROOT / "chdk-port" / pc.PROTOTYPE).read_text()
        for sym in set(re.findall(r"sub_[0-9a-fA-F]{8}", self.source)):
            self.assertIn(sym, proto)
        self.assertEqual(re.findall(r"0x[0-9a-fA-F]{5,}", self.source.replace(
            "0x00020000", "")), [])

    def test_pinned_prototype_sha256_matches_tracked_file(self):
        proto_bytes = (REPO_ROOT / "chdk-port" / pc.PROTOTYPE).read_bytes()
        self.assertEqual(boot.sha256(proto_bytes), pc.PROTOTYPE_SHA256)

    def test_port9a_model_is_unchanged_in_behaviour(self):
        m = rt.RuntimeLifecycle()
        m.init_core()
        self.assertIs(m.install_intercept(), rt.InterceptState.REFUSED)
        self.assertEqual(set(rt.REPLACEMENTS), {"InitFileModules", "PhySw"})


if __name__ == "__main__":
    unittest.main()
