#include "lolevel.h"
#include "platform.h"
#include "core.h"

#define USE_STUBS_NRFLAG 1
#define NR_AUTO (-1)

#include "../../../generic/capt_seq.c"

// Task hooks intentionally unimplemented for CHDK-PORT-0
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
