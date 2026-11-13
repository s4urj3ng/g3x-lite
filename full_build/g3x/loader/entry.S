// =============================================================================
// Loader Entry Point for Canon PowerShot G3 X (GM1.10C) Full Build
// Adapted from chdk-port/loader/g7x/entry.S:1-7
// =============================================================================

.section .entry
// ordinary startup...
.code 16
.align 2
.syntax unified
    LDR     SP, =MEMBASEADDR
    B       my_restart
