#ifndef G3X_TRACE_H
#define G3X_TRACE_H

// =============================================================================
// G3X Lite (GM1.10C) - Compile-Time Runtime Trace Core
//
// Platform: Canon PowerShot G3 X (GM1.10C / Platform ID 0x32A8 = 12968 decimal)
// Subsystem: Early-boot & post-continuation telemetry ring buffer and stage markers
// Safety Scope: Phase 0 host static analysis / offline build (docs/SAFETY.md)
// Evidence Base: docs/PORT17_TRACE_EVIDENCE.md
// Scope Note: This module is NOT yet wired into the build or called by boot code.
// Build wiring (tools/build_candidate_port2a.py, platform Makefile) and marker call
// sites (boot_prototype.c) belong to the separate task p17-trace-integration and
// are out of scope here.
//
// Byte Layout & Endianness Specification:
// ---------------------------------------
// Architecture: 32-bit ARM Cortex-A9 (Little-Endian EABI).
// All scalar multi-byte integers (uint32_t) are stored in Little-Endian byte
// order (least significant byte at lowest address).
//
// 1. Trace Header (g3x_trace_header_t, 32 bytes = 0x20):
//    Offset  Field          Type      Size  Description
//    0x00    magic          uint32_t  4 B   0x43415254 (ASCII "TRAC", in memory order: 'T','R','A','C')
//    0x04    version        uint32_t  4 B   0x00010000 (Format v1.0, Major 16b / Minor 16b)
//    0x08    capacity       uint32_t  4 B   Ring capacity (G3X_TRACE_CAPACITY = 64 records)
//    0x0C    write_idx      uint32_t  4 B   Cumulative write counter (slot = write_idx % capacity)
//    0x10    dropped_count  uint32_t  4 B   Count of overwritten records: (write_idx - capacity) once the ring wraps (write_idx > capacity), 0 otherwise
//    0x14    record_size    uint32_t  4 B   Byte size of each record (sizeof(g3x_trace_record_t) = 32)
//    0x18    reserved[0]    uint32_t  4 B   Reserved padding for 32-byte alignment (0x00000000)
//    0x1C    reserved[1]    uint32_t  4 B   Reserved padding for 32-byte alignment (0x00000000)
//
// 2. Trace Record (g3x_trace_record_t, 32 bytes = 0x20):
//    Offset  Field          Type      Size  Description
//    0x00    stage_id       uint32_t  4 B   Stage identifier (G3X_STAGE_*)
//    0x04    tick           uint32_t  4 B   Hardware tick count / monotonic sequence counter
//    0x08    pc_lr_val      uint32_t  4 B   PC, LR, or caller-supplied telemetry value
//    0x0C    text           char[20]  20 B  Short fixed-length ASCII label (null-padded)
//
// 3. Trace Ring Buffer (g3x_trace_ring_t, 2080 bytes = 0x820, 16-byte aligned):
//    Offset         Component                  Size
//    0x0000         g3x_trace_header_t header  32 bytes
//    0x0020..0x081F g3x_trace_record_t records 64 * 32 = 2048 bytes
// =============================================================================

#ifndef BOOT_WITNESS_H
#include "boot_witness.h"
#endif

// -----------------------------------------------------------------------------
// Format Constants & Signatures
// -----------------------------------------------------------------------------
#define G3X_TRACE_MAGIC             0x43415254U  // ASCII "TRAC" in memory order ('T','R','A','C'), Little-Endian word 0x43415254
#define G3X_TRACE_VERSION           0x00010000U  // Version 1.0 (Major: 1, Minor: 0)

#define G3X_TRACE_RECORD_TEXT_LEN   20           // Fixed length of record text
#define G3X_TRACE_CAPACITY          64           // Ring buffer capacity (records)
#define G3X_TRACE_RECORD_SIZE       32           // sizeof(g3x_trace_record_t)
#define G3X_TRACE_HEADER_SIZE       32           // sizeof(g3x_trace_header_t)
#define G3X_TRACE_RING_SIZE         (G3X_TRACE_HEADER_SIZE + (G3X_TRACE_CAPACITY * G3X_TRACE_RECORD_SIZE)) // 2080 B

// -----------------------------------------------------------------------------
// Stage Identifiers
// -----------------------------------------------------------------------------
#define G3X_STAGE_NONE              0x00000000U  // Empty / uninitialized record
#define G3X_STAGE_ENTRY             0x00000001U  // Stage 1: Core entry
#define G3X_STAGE_RELOC             0x00000002U  // Stage 2: Relocation / BSS zero completed
#define G3X_STAGE_TASK_HOOK         0x00000003U  // Stage 3: Task startup / task hooks registered
#define G3X_STAGE_KBD               0x00000004U  // Stage 4: Keyboard / PhySw initialized
#define G3X_STAGE_DISPLAY           0x00000005U  // Stage 5: Display / framebuffer initialized
#define G3X_STAGE_ASSERT            0x000000FEU  // Assertion failure witness
#define G3X_STAGE_FLUSH             0x000000FFU  // Explicit flush marker

// -----------------------------------------------------------------------------
// Compile-Time Configuration Flags (All Default OFF)
// -----------------------------------------------------------------------------

// Main compile-time trace enable flag (default OFF = 0)
// With G3X_TRACE == 0:
// - Zero memory overhead: ring buffer is completely omitted from .bss.
// - Zero runtime overhead: marker macros expand to ((void)0).
// - g3x_trace.c compiles to an empty object with no symbols.
// - Preserves PORT-16 layout invariant: _start=0x003489B4, boot_witness=0x0035F7A0, _end=0x00366CB0.
#ifndef G3X_TRACE
#define G3X_TRACE 0
#endif

// Flush routine to A/CHDK/LOGS/TRACE.LOG (default OFF = 0)
// Enabling this flag hits a compile-time #error because file-stub entry addresses,
// file wrapper register calling conventions, and filesystem readiness gates
// remain unresolved in GM1.10C.
//
// Citations from docs/PORT17_TRACE_EVIDENCE.md:
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
#ifndef G3X_TRACE_FLUSH
#define G3X_TRACE_FLUSH 0
#endif

#if G3X_TRACE_FLUSH
#error "G3X_TRACE_FLUSH cannot be enabled: file-stub addresses and filesystem readiness are unresolved (Q-P17-04, Q-P17-05, Q-P17-07, Q-P17-11)"
#endif

// Diagnostic blink codes for pre-filesystem failures (default OFF = 0)
// Enabling this flag hits a compile-time #error because the LED control route
// and pre-kernel safety remain unresolved in GM1.10C.
//
// Citations from docs/PORT17_TRACE_EVIDENCE.md:
// - TODO (Q-P17-03): LEDDrive calling contract, integer LED IDs ({0, 4}),
//   active polarity, and pre-kernel safety are UNKNOWN.
// - TODO (Q-P17-06): Direct MMIO GPIO register route.
//   0xD20B0000 range drives motor coils and power rails; blind register writes
//   risk permanent camera hardware damage.
// - TODO (Q-P17-08): LEDDrive ROM entry address is UNKNOWN in GM1.10C.
// - TODO (Q-P17-09): Stock LEDDrv.c (0xFC12D724) panics pre-kernel
//   because *0x00009BA4 == 0.
#ifndef G3X_TRACE_LED
#define G3X_TRACE_LED 0
#endif

#if G3X_TRACE_LED
#error "G3X_TRACE_LED cannot be enabled: LED control route and pre-kernel safety are unresolved (Q-P17-03, Q-P17-06, Q-P17-08, Q-P17-09)"
#endif

// File I/O destination and cap constants
#define G3X_TRACE_LOG_PATH          "A/CHDK/LOGS/TRACE.LOG"
#define G3X_TRACE_LOG_MAX_SIZE      (64 * 1024)  // 64 KiB maximum log size

// -----------------------------------------------------------------------------
// Structure Definitions
// -----------------------------------------------------------------------------

// Ring buffer header (32 bytes, aligned to 4 bytes)
typedef struct {
    uint32_t magic;          // 0x43415254 (ASCII "TRAC", LE memory order)
    uint32_t version;        // 0x00010000
    uint32_t capacity;       // 64 records
    uint32_t write_idx;      // Monotonic write counter
    uint32_t dropped_count;  // Overwritten records: (write_idx - capacity) once ring wraps (write_idx > capacity), 0 otherwise
    uint32_t record_size;    // 32 bytes
    uint32_t reserved[2];    // Reserved padding (0x00000000, 0x00000000)
} __attribute__((packed, aligned(4))) g3x_trace_header_t;

// Single trace record (32 bytes, aligned to 4 bytes)
typedef struct {
    uint32_t stage_id;       // Stage identifier (G3X_STAGE_*)
    uint32_t tick;           // Timestamp / hardware tick count
    uint32_t pc_lr_val;      // PC, LR, or caller-supplied telemetry value
    char     text[G3X_TRACE_RECORD_TEXT_LEN]; // ASCII label, null-padded
} __attribute__((packed, aligned(4))) g3x_trace_record_t;

// Complete trace ring buffer (2080 bytes, aligned to 16 bytes)
typedef struct {
    g3x_trace_header_t header;
    g3x_trace_record_t records[G3X_TRACE_CAPACITY];
} __attribute__((packed, aligned(16))) g3x_trace_ring_t;

// Static compile-time size and offset assertions enforcing documented layout
#define G3X_TRACE_STATIC_ASSERT(cond, name) \
    typedef char g3x_trace_static_assert_##name[(cond) ? 1 : -1] __attribute__((unused))

G3X_TRACE_STATIC_ASSERT(sizeof(g3x_trace_header_t) == 32, header_size_32);
G3X_TRACE_STATIC_ASSERT(sizeof(g3x_trace_record_t) == 32, record_size_32);
G3X_TRACE_STATIC_ASSERT(sizeof(g3x_trace_ring_t) == 2080, ring_size_2080);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_header_t, magic) == 0x00, header_magic_offset_0x00);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_header_t, version) == 0x04, header_version_offset_0x04);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_header_t, capacity) == 0x08, header_capacity_offset_0x08);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_header_t, write_idx) == 0x0C, header_write_idx_offset_0x0C);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_header_t, dropped_count) == 0x10, header_dropped_count_offset_0x10);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_header_t, record_size) == 0x14, header_record_size_offset_0x14);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_header_t, reserved) == 0x18, header_reserved_offset_0x18);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_record_t, stage_id) == 0x00, record_stage_id_offset_0x00);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_record_t, tick) == 0x04, record_tick_offset_0x04);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_record_t, pc_lr_val) == 0x08, record_pc_lr_val_offset_0x08);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_record_t, text) == 0x0C, record_text_offset_0x0C);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_ring_t, header) == 0x00, ring_header_offset_0x00);
G3X_TRACE_STATIC_ASSERT(__builtin_offsetof(g3x_trace_ring_t, records) == 0x20, ring_records_offset_0x20);

// -----------------------------------------------------------------------------
// API Prototypes & Stage-Marker Macros
// -----------------------------------------------------------------------------

#if G3X_TRACE

extern volatile g3x_trace_ring_t g3x_trace_ring;

// The recorder and all markers are active whenever G3X_TRACE is 1, including
// the LOW_LEVEL candidate configuration. They use only RAM stores into the
// ring and call no firmware routine.
void g3x_trace_init(void);
void g3x_trace_record(uint32_t stage_id, uint32_t tick, uint32_t pc_lr_val, const char *text);
int  g3x_trace_flush(void);
void g3x_trace_led_blink(int code);

void g3x_trace_mark_entry(void);
void g3x_trace_mark_reloc(void);
void g3x_trace_mark_task_hook(void);
void g3x_trace_mark_kbd(void);
void g3x_trace_mark_display(void);

// Pure, firmware-independent testable logic
int  g3x_trace_check_log_cap(uint32_t current_size, uint32_t bytes_to_write);
int  g3x_trace_serialize_record(const g3x_trace_record_t *rec, char *out_buf, uint32_t max_len);
int  g3x_trace_get_blink_pattern(int code);

#define G3X_TRACE_MARKER_EX(stage, tick, val, text) \
    g3x_trace_record((stage), (tick), (uint32_t)(val), (text))

#define G3X_TRACE_MARKER(stage, val, text) \
    g3x_trace_record((stage), 0, (uint32_t)(val), (text))

#define G3X_TRACE_ENTRY(val, text) \
    G3X_TRACE_MARKER(G3X_STAGE_ENTRY, (val), (text))

#define G3X_TRACE_RELOC(val, text) \
    G3X_TRACE_MARKER(G3X_STAGE_RELOC, (val), (text))

#define G3X_TRACE_TASK_HOOK(val, text) \
    G3X_TRACE_MARKER(G3X_STAGE_TASK_HOOK, (val), (text))

#define G3X_TRACE_KBD(val, text) \
    G3X_TRACE_MARKER(G3X_STAGE_KBD, (val), (text))

#define G3X_TRACE_DISPLAY(val, text) \
    G3X_TRACE_MARKER(G3X_STAGE_DISPLAY, (val), (text))

#define G3X_TRACE_ASSERT(val, text) \
    do { \
        G3X_TRACE_MARKER(G3X_STAGE_ASSERT, (val), (text)); \
        g3x_trace_flush(); \
        g3x_trace_led_blink(1); \
    } while (0)

#else // !G3X_TRACE

// When G3X_TRACE is OFF (0), all marker macros expand to nothing ((void)0)
#define G3X_TRACE_MARKER_EX(stage, tick, val, text) ((void)0)
#define G3X_TRACE_MARKER(stage, val, text)          ((void)0)
#define G3X_TRACE_ENTRY(val, text)                  ((void)0)
#define G3X_TRACE_RELOC(val, text)                  ((void)0)
#define G3X_TRACE_TASK_HOOK(val, text)              ((void)0)
#define G3X_TRACE_KBD(val, text)                    ((void)0)
#define G3X_TRACE_DISPLAY(val, text)                ((void)0)
#define G3X_TRACE_ASSERT(val, text)                 ((void)0)

#define g3x_trace_flush()                           ((void)0)
#define g3x_trace_led_blink(code)                   ((void)0)

#endif // G3X_TRACE

#endif // G3X_TRACE_H
