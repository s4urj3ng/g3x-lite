#ifndef BOOT_WITNESS_H
#define BOOT_WITNESS_H

typedef unsigned int   uint32_t;
typedef unsigned short uint16_t;
typedef unsigned char  uint8_t;

#define BOOT_WITNESS_MAGIC      0x5749544E  // "WITN"
#define BOOT_WITNESS_VERSION    0x00010001  // Version 1.1

// Precise Boot Stage States (PORT-1F.2)
#define STAGE_EMPTY             0x00
#define STAGE_LOADER            0x01  // LOADER_REACHED
#define STAGE_CORE              0x02  // CORE_REACHED
#define STAGE_CONTINUATION      0x04  // CONTINUATION_ATTEMPTED
#define STAGE_ALL_MASK          (STAGE_LOADER | STAGE_CORE | STAGE_CONTINUATION) // 0x07

// Note: CONTINUATION_CONFIRMED is an inspector classification requiring
// independent post-continuation evidence outside the boot witness.

typedef struct {
    uint32_t magic;          // 0x5749544E ("WITN")
    uint32_t version;        // 0x00010001
    uint32_t session_nonce;  // Per-attempt challenge/nonce (formerly fixed boot_id)
    uint32_t stage_state;    // Bitmask: LOADER (0x01) -> CORE (0x03) -> CONTINUATION (0x07)
    uint32_t loader_sp;      // Stack pointer at loader handoff
    uint32_t core_entry_pc;  // Core entry address (0x003489B5)
    uint32_t cont_tick;      // Hardware tick count / sentinel at continuation
    uint32_t checksum;       // Polynomial error-detection checksum (NOT cryptographic authentication)
} __attribute__((packed, aligned(16))) boot_witness_t;

// Non-cryptographic error-detection code over first 7 words
static inline uint32_t compute_witness_checksum(const boot_witness_t *w) {
    uint32_t c = 0x55AA55AA;
    c = (c * 31) ^ w->magic;
    c = (c * 31) ^ w->version;
    c = (c * 31) ^ w->session_nonce;
    c = (c * 31) ^ w->stage_state;
    c = (c * 31) ^ w->loader_sp;
    c = (c * 31) ^ w->core_entry_pc;
    c = (c * 31) ^ w->cont_tick;
    return c;
}

#endif // BOOT_WITNESS_H
