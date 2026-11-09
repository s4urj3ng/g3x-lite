/* =============================================================================
 * PORT-35 Part B: G3X_GUI=1 RAM-only module stubs
 * Replaces core/modules.c and core/module_load.c so no module is ever loaded
 * from the SD card while keeping all lib* pointers valid in RAM.
 * ============================================================================= */

static int stub_ret0(void) { return 0; }
static void stub_void(void) {}

typedef struct {
    const void *lib;
    void *h;
    unsigned int flags;
    const char *name;
} module_handler_t;

typedef struct {
    void *hdr;
    void *f1;
    void *f2;
    void *f3;
    void *f4;
    void *f5;
    void *f6;
    void *f7;
    void *f8;
    void *f9;
    void *f10;
} stub_lib_t;

static const stub_lib_t g3x_stub_lib = {
    0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
    (void *)stub_ret0,
};

const stub_lib_t *libscriptapi = &g3x_stub_lib;
const stub_lib_t *libtextbox = &g3x_stub_lib;
const stub_lib_t *libgrids = &g3x_stub_lib;
const stub_lib_t *librawop = &g3x_stub_lib;
const stub_lib_t *libmotiondetect = &g3x_stub_lib;
const stub_lib_t *libcurves = &g3x_stub_lib;
const stub_lib_t *libdng = &g3x_stub_lib;
const stub_lib_t *libfselect = &g3x_stub_lib;
const stub_lib_t *libmpopup = &g3x_stub_lib;
const stub_lib_t *libtxtread = &g3x_stub_lib;
const stub_lib_t *libeyefi = &g3x_stub_lib;
const stub_lib_t *libhisto = &g3x_stub_lib;
const stub_lib_t *libshothisto = &g3x_stub_lib;
const stub_lib_t *libzebra = &g3x_stub_lib;
const stub_lib_t *libedgeovr = &g3x_stub_lib;
const stub_lib_t *libhexbox = &g3x_stub_lib;
const stub_lib_t *libpalette = &g3x_stub_lib;

int module_load(module_handler_t *hMod)
{
    if (hMod && !hMod->lib) {
        hMod->lib = &g3x_stub_lib;
    }
    return 0;
}

void module_unload(const char *name) { (void)name; }
int module_run(char *module, void *callback, int count, int *params, int unload)
{
    (void)module;
    (void)callback;
    (void)count;
    (void)params;
    (void)unload;
    return -1;
}
void module_preload(const char *path, const char *name, int flags) { (void)path; (void)name; (void)flags; }
void module_exit_alt(void) {}
void module_tick_unloader(void) {}
void module_log_clear(void) {}
void *module_get_adr(unsigned int idx) { (void)idx; return (void *)stub_void; }
int get_module_info(int idx, const char **name, int *size, unsigned int *base, int *flags)
{
    (void)idx;
    (void)name;
    (void)size;
    (void)base;
    (void)flags;
    return 0;
}
void module_restore_edge(void *buf, int state) { (void)buf; (void)state; }
void module_save_edge(const char *fn) { (void)fn; }
void module_set_script_lang(const char *fn) { (void)fn; }
