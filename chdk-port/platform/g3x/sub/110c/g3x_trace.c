// =============================================================================
// G3X Lite (GM1.10C) - Compile-Time Runtime Trace Core Implementation
//
// Platform: Canon PowerShot G3 X (GM1.10C / Platform ID 0x32A8 = 12968 decimal)
// Safety Scope: Phase 0 host static analysis / offline build (docs/SAFETY.md)
// Evidence Base: docs/PORT17_TRACE_EVIDENCE.md
// =============================================================================

#include "g3x_trace.h"

#if G3X_TRACE

// -----------------------------------------------------------------------------
// Section (a) Trace Ring Placement
// -----------------------------------------------------------------------------
// Dedicated trace ring buffer placed in prototype's own .bss via a zero-initialized
// global (no initializer and no explicit section attribute, avoiding section-type
// conflict).
//
// Per docs/PORT17_TRACE_EVIDENCE.md:205-251 section (a.3):
// - Relies on default zero-init .bss placement without explicit section attribute
//   to avoid section type conflicts and ensure placement in .bss rather than .data.
// - Placed in .bss, downstream of boot_witness (.data) (docs/PORT16_WITNESS_ADDRESS.md:15;
//   docs/PORT17_TRACE_EVIDENCE.md:218-219, 287). With G3X_TRACE OFF this file is
//   empty and boot_witness stays at 0x0035F7A0. With it ON, the candidate trace
//   link script (tools/build_candidate_port2a.py) puts this file's .text/.rodata
//   in a loaded .g3x_trace_text section after .data, so boot_witness keeps
//   0x0035F7A0 and the ring is the last .bss object (Q-P17-01).
// - Expands _end = link_bss_end by the trace text size plus
//   ALIGN_UP(sizeof(g3x_trace_ring_t), 16) (docs/PORT17_TRACE_EVIDENCE.md:222, 239).
// - new_sa = &_end shifts the DryOS heap base forward, preventing heap clobber
//   (chdk-port/platform/g3x/sub/110c/boot_prototype.c:24, 210-215; docs/PORT17_TRACE_EVIDENCE.md:225).
// - Size S = 2080 B (0x820) is well within headroom ceiling 0x002B5364 B (~2,772 KiB)
//   (docs/PORT17_TRACE_EVIDENCE.md:248).
// - Citations: chdk-port/platform/g3x/sub/110c/boot_prototype.c:24, 184-188;
//   docs/PORT16_WITNESS_ADDRESS.md:15, 218; docs/PORT17_TRACE_EVIDENCE.md:205-251.
// - Open Question: Q-P17-01 (Trace Ring Linker Placement & Section Mechanics).
// -----------------------------------------------------------------------------
volatile g3x_trace_ring_t g3x_trace_ring __attribute__((aligned(16)));


void g3x_trace_init(void)
{
    uint32_t i;
    g3x_trace_ring.header.magic = G3X_TRACE_MAGIC;
    g3x_trace_ring.header.version = G3X_TRACE_VERSION;
    g3x_trace_ring.header.capacity = G3X_TRACE_CAPACITY;
    g3x_trace_ring.header.write_idx = 0;
    g3x_trace_ring.header.dropped_count = 0;
    g3x_trace_ring.header.record_size = G3X_TRACE_RECORD_SIZE;
    g3x_trace_ring.header.reserved[0] = 0;
    g3x_trace_ring.header.reserved[1] = 0;

    for (i = 0; i < G3X_TRACE_CAPACITY; i++) {
        g3x_trace_ring.records[i].stage_id = G3X_STAGE_NONE;
        g3x_trace_ring.records[i].tick = 0;
        g3x_trace_ring.records[i].pc_lr_val = 0;
        g3x_trace_ring.records[i].text[0] = '\0';
    }
}

void g3x_trace_record(uint32_t stage_id, uint32_t tick, uint32_t pc_lr_val, const char *text)
{
    uint32_t idx;
    uint32_t slot;
    volatile g3x_trace_record_t *rec;
    int i;

    // Lazy initialization of trace ring header on first write
    if (g3x_trace_ring.header.magic != G3X_TRACE_MAGIC ||
        g3x_trace_ring.header.version != G3X_TRACE_VERSION) {
        g3x_trace_init();
    }

    idx = g3x_trace_ring.header.write_idx;

    if (tick == 0) {
        // Fallback monotonic tick uses write_idx + 1 to avoid an extra BSS sequence variable.
        tick = idx + 1;
    }

    slot = idx % G3X_TRACE_CAPACITY;
    rec = &g3x_trace_ring.records[slot];

    rec->stage_id = stage_id;
    rec->tick = tick;
    rec->pc_lr_val = pc_lr_val;

    if (text) {
        for (i = 0; i < G3X_TRACE_RECORD_TEXT_LEN - 1 && text[i] != '\0'; i++) {
            rec->text[i] = text[i];
        }
        for (; i < G3X_TRACE_RECORD_TEXT_LEN; i++) {
            rec->text[i] = '\0';
        }
    } else {
        for (i = 0; i < G3X_TRACE_RECORD_TEXT_LEN; i++) {
            rec->text[i] = '\0';
        }
    }

    g3x_trace_ring.header.write_idx = idx + 1;
    if (g3x_trace_ring.header.write_idx > G3X_TRACE_CAPACITY) {
        g3x_trace_ring.header.dropped_count = g3x_trace_ring.header.write_idx - G3X_TRACE_CAPACITY;
    } else {
        g3x_trace_ring.header.dropped_count = 0;
    }

    // Call flush at stage changes and assertions
    g3x_trace_flush();
}

// -----------------------------------------------------------------------------
// Section (b) Firmware File Stubs & Filesystem-Ready Gate Flush Routine
// -----------------------------------------------------------------------------
// Writes append-only, size-capped records to A/CHDK/LOGS/TRACE.LOG.
//
// Gated behind G3X_TRACE_FLUSH (default OFF = 0).
//
// Open Questions cited from docs/PORT17_TRACE_EVIDENCE.md:
// - TODO (Q-P17-04): Filesystem mount verification point.
//   Neither sub_fc0d9ccc nor event 0x5006 proves SD card mount readiness.
//   Writing to TRACE.LOG prior to verified Stage 4/5 causes storage corruption.
// - TODO (Q-P17-05): Telemetry file API selection.
//   Stream wrappers (Fopen_Fut @ 0xFC37EFA7, Fwrite_Fut @ 0xFC37F077,
//   Fclose_Fut @ 0xFC37EFCF) entry addresses are verified in docs/HANDOFF.md:1025,
//   but direct C register calling ABI is UNKNOWN.
// - TODO (Q-P17-07): Low-level DryOS file descriptor routines (Open, Close, Write)
//   and fileio_semaphore RAM addresses are completely UNKNOWN.
// - TODO (Q-P17-11): File wrapper register ABI, return values, and error codes
//   remain uninspected in GM1.10C ROM (Range R-P17-02 proposed).
// -----------------------------------------------------------------------------
int g3x_trace_flush(void)
{
#if G3X_TRACE_FLUSH
#error "G3X_TRACE_FLUSH cannot be enabled: file-stub addresses and filesystem readiness are unresolved (Q-P17-04, Q-P17-05, Q-P17-07, Q-P17-11)"
    return 0;
#else
    return -1; // Disabled by default
#endif
}

// -----------------------------------------------------------------------------
// Section (c) LED Control Route Blink-Code Fallback
// -----------------------------------------------------------------------------
// Diagnostic blink codes for pre-filesystem failures.
//
// Gated behind G3X_TRACE_LED (default OFF = 0).
//
// Open Questions cited from docs/PORT17_TRACE_EVIDENCE.md:
// - TODO (Q-P17-03): LEDDrive calling contract, integer LED IDs ({0, 4}),
//   active polarity, and pre-kernel safety are UNKNOWN.
// - TODO (Q-P17-06): Direct MMIO GPIO register route.
//   0xD20B0000 range drives motor coils and power rails; blind register writes
//   risk permanent camera hardware damage.
// - TODO (Q-P17-08): LEDDrive ROM entry address is UNKNOWN in GM1.10C.
// - TODO (Q-P17-09): Stock LEDDrv.c (0xFC12D724) panics pre-kernel
//   because *0x00009BA4 == 0.
// -----------------------------------------------------------------------------
void g3x_trace_led_blink(int code)
{
    (void)code;
#if G3X_TRACE_LED
#error "G3X_TRACE_LED cannot be enabled: LED control route and pre-kernel safety are unresolved (Q-P17-03, Q-P17-06, Q-P17-08, Q-P17-09)"
#endif
}

// -----------------------------------------------------------------------------
// Pure, Firmware-Independent Testable Logic
// -----------------------------------------------------------------------------
int g3x_trace_check_log_cap(uint32_t current_size, uint32_t bytes_to_write)
{
    if (current_size > G3X_TRACE_LOG_MAX_SIZE) {
        return 0; // Exceeds 64 KiB cap
    }
    return (bytes_to_write <= (G3X_TRACE_LOG_MAX_SIZE - current_size)) ? 1 : 0;
}

int g3x_trace_serialize_record(const g3x_trace_record_t *rec, char *out_buf, uint32_t max_len)
{
    uint32_t i;
    if (!rec || !out_buf || max_len < G3X_TRACE_RECORD_SIZE) {
        return 0;
    }
    const char *src = (const char *)rec;
    for (i = 0; i < G3X_TRACE_RECORD_SIZE; i++) {
        out_buf[i] = src[i];
    }
    return G3X_TRACE_RECORD_SIZE;
}

int g3x_trace_get_blink_pattern(int code)
{
    if (code <= 0) return 0;
    if (code > 10) return 10;
    return code;
}

// -----------------------------------------------------------------------------
// Stage-Marker Helper Functions
// -----------------------------------------------------------------------------
void g3x_trace_mark_entry(void)
{
    // Use toolchain-provided return address (__builtin_return_address(0))
    // rather than inferring an unverified CPU mode / entry address.
    G3X_TRACE_ENTRY((uint32_t)(unsigned long)__builtin_return_address(0), "CORE_ENTRY");
}

void g3x_trace_mark_reloc(void)
{
    G3X_TRACE_RELOC(0, "RELOC_DONE");
}

void g3x_trace_mark_task_hook(void)
{
    G3X_TRACE_TASK_HOOK(0, "TASK_STARTUP");
}

void g3x_trace_mark_kbd(void)
{
    G3X_TRACE_KBD(0, "KBD_INIT");
}

void g3x_trace_mark_display(void)
{
    G3X_TRACE_DISPLAY(0, "DISP_INIT");
}

#endif // G3X_TRACE
