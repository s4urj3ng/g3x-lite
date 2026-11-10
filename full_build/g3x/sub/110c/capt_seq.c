// PORT-41: capt_seq.c adapted from sibling g7x (sub/100d: capt_seq.c)
// Sibling citation: chdk-port/platform/g7x/sub/100d/capt_seq.c:1-25
// Task hook address task_CaptSeq cannot be confirmed from FINSIG (reference/finsig_gm110c/stubs_entry.S,
// funcs_by_name.csv) or existing VERIFIED records for GM1.10C.
// Hook remains disabled (task left stock). TODO: Establish GM1.10C task_CaptSeq entry.

#include "lolevel.h"
#include "platform.h"
#include "core.h"

#define USE_STUBS_NRFLAG 1
#define NR_AUTO (-1)

#include "../../../generic/capt_seq.c"

char *current_raw_addr = 0;

void captseq_raw_addr_init_my(int raw_index, char **ptr)
{
    (void)raw_index;
    (void)ptr;
}

void clear_current_raw_addr(void)
{
    current_raw_addr = 0;
}
