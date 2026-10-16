# Research safety and data handling

Phase 0: documentation and read-only public-source investigation only.
- Do not execute unknown camera boot payloads, flash firmware, or connect camera for invasive tests.
- Do not upload Canon firmware binaries to public repositories or AI services without checking rights and privacy.
- Keep raw dumps, proprietary files, Ghidra databases, logs containing device identifiers and credentials in ignored local directories.
- Before any hardware test in a later phase: verify model/revision, reliable power, reversible loading, known recovery path, owner approval, test plan and rollback conditions.
- A successful compile or emulator run does not establish physical-device safety.
