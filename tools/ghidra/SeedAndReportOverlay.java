// Seed bounded GM1.10C display/VRAM procedures and report static references.
// @category G3X

import java.io.File;
import java.io.PrintWriter;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.SourceType;

public class SeedAndReportOverlay extends GhidraScript {
    private static final long ROM_START = 0xfc000000L;
    private static final long ROM_END = 0xfdffffffL;
    private static final Map<String, Long> SEEDS = new LinkedHashMap<>();
    static {
        // Corrected aligned EventProc entries (fixing 1-slot table pairing shift)
        SEEDS.put("GetVRAMHPixelsSize", 0xfc0d360aL);
        SEEDS.put("GetVRAMVPixelsSize", 0xfc0d3612L);
        SEEDS.put("GetMovieJpegVRAMHPixelsSize", 0xfc0d361aL);
        SEEDS.put("GetMovieJpegVRAMVPixelsSize", 0xfc0d3622L);
        SEEDS.put("DispCon_ShowBitmapColorBar", 0xfc37c9ccL);
        SEEDS.put("get_displaytype", 0xfc37b9c2L);
        SEEDS.put("SaveBmpVRAMData", 0xfc558348L);
        SEEDS.put("SavePaletteData", 0xfc5584e8L);
        SEEDS.put("GetSumYOfVRAMCenterLine", 0xfc612f58L);
        SEEDS.put("StopContinuousVRAMData", 0xfc612facL);
        SEEDS.put("GetContinuousVRAMData", 0xfc613000L);
        SEEDS.put("GetContinuousVRAMDataWithRingBuffer", 0xfc613506L);
        SEEDS.put("GetContinuousMovieJpegVRAMData", 0xfc6135baL);

        // Verified GM1.10C overlay & palette composition pipeline (VramTransferManager.c, SCM.c, MakeOsdVram.c, BmpDev.c, Ximr/Mzrm)
        SEEDS.put("MzrmGraphic_Init", 0xfc112ff6L);
        SEEDS.put("DispDev_ConvertPaletteToHwLut", 0xfc1425fcL);
        SEEDS.put("BmpDev_Refresh", 0xfc18347eL);
        SEEDS.put("BmpDev_GetVramInfo", 0xfc183608L);
        SEEDS.put("MakeOsdVram_Compose", 0xfc183824L);
        SEEDS.put("MakeOsdVram_Setup", 0xfc183a12L);
        SEEDS.put("PaletteClass_GetPayloadPtr", 0xfc19d800L);
        SEEDS.put("PaletteClass_SendToZico", 0xfc19d804L);
        SEEDS.put("PaletteClass_Create", 0xfc19d828L);
        SEEDS.put("PaletteClass_SetEntry", 0xfc19d854L);
        SEEDS.put("PaletteClass_GetEntry", 0xfc19d8caL);
        SEEDS.put("PaletteClass_Validate", 0xfc19d8f2L);
        SEEDS.put("Window_EmergencyRefresh_caller", 0xfc1f1562L);
        SEEDS.put("Mzrm_SendPaletteMsg_thunk", 0xfc20bf42L);
        SEEDS.put("XimrExe", 0xfc20c6d0L);
        SEEDS.put("SCM_MarkDirtyBit1", 0xfc33d10cL);
        SEEDS.put("SCM_GetActivePaletteObject", 0xfc33d12cL);
        SEEDS.put("SCM_ReapplyCustomColors", 0xfc33d1aeL);
        SEEDS.put("SCM_Init", 0xfc33d240L);
        SEEDS.put("SCM_SetActivePalette", 0xfc33d282L);
        SEEDS.put("SCM_IsDirtyBit0", 0xfc33d2b4L);
        SEEDS.put("SCM_ClearDirtyBit0", 0xfc33d2beL);
        SEEDS.put("SCM_GetActivePaletteId", 0xfc33d2caL);
        SEEDS.put("SCM_MarkDirtyBits01", 0xfc33d2d0L);
        SEEDS.put("SCM_PushPaletteUnconditional", 0xfc33d2dcL);
        SEEDS.put("SCM_PushPaletteIfDirty", 0xfc33d2f0L);
        SEEDS.put("SCM_SetMultipleColors", 0xfc33d4aaL);
        SEEDS.put("SCM_GetRomDefaultPalette", 0xfc33d5faL);
        SEEDS.put("transfer_src_overlay", 0xfc380634L);
        SEEDS.put("VTM_RefreshScreen", 0xfc3809aeL);
        SEEDS.put("VTM_UnLock", 0xfc380a78L);
        SEEDS.put("VTM_EmergencyRefreshPhysicalScreen", 0xfc38113eL);
        SEEDS.put("ZicoKick_Start", 0xfc3dfd3cL);
        SEEDS.put("Mzrm_SendPaletteMsg", 0xfc4c2abeL);
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        File output = new File(args.length > 0 ? args[0] : "/tmp/g3x-overlay-report.txt");
        Register tmode = currentProgram.getProgramContext().getRegister("TMode");
        if (tmode == null) throw new IllegalStateException("TMode register unavailable");

        // Only bounded, verified code windows are assigned Thumb context.
        setThumb(tmode, 0xfc0d360aL, 0xfc0d3629L);
        setThumb(tmode, 0xfc112ff6L, 0xfc11304fL);
        setThumb(tmode, 0xfc1425fcL, 0xfc1426dfL);
        setThumb(tmode, 0xfc18347eL, 0xfc1837e7L);
        setThumb(tmode, 0xfc183824L, 0xfc183b7bL);
        setThumb(tmode, 0xfc19d800L, 0xfc19d907L);
        setThumb(tmode, 0xfc1f1562L, 0xfc1f1605L);
        setThumb(tmode, 0xfc20bf42L, 0xfc20bf59L);
        setThumb(tmode, 0xfc20c6d0L, 0xfc20c763L);
        setThumb(tmode, 0xfc33d10cL, 0xfc33d30fL);
        setThumb(tmode, 0xfc33d4aaL, 0xfc33d4ffL);
        setThumb(tmode, 0xfc33d5faL, 0xfc33d617L);
        setThumb(tmode, 0xfc37b9c2L, 0xfc37b9cbL);
        setThumb(tmode, 0xfc37c990L, 0xfc37ca9fL);
        setThumb(tmode, 0xfc380602L, 0xfc380735L);
        setThumb(tmode, 0xfc3809aeL, 0xfc380a93L);
        setThumb(tmode, 0xfc38113eL, 0xfc3811e1L);
        setThumb(tmode, 0xfc3dfd3cL, 0xfc3dfdc5L);
        setThumb(tmode, 0xfc4c2abeL, 0xfc4c2b01L);
        setThumb(tmode, 0xfc558348L, 0xfc558577L);
        setThumb(tmode, 0xfc612f58L, 0xfc6137ffL);

        FunctionManager manager = currentProgram.getFunctionManager();
        for (Map.Entry<String, Long> seed : SEEDS.entrySet()) {
            Address entry = toAddr(seed.getValue());
            new DisassembleCommand(entry, null, true).applyTo(currentProgram, monitor);
            Function function = manager.getFunctionAt(entry);
            if (function == null) {
                new CreateFunctionCmd(seed.getKey(), entry, null, SourceType.USER_DEFINED)
                    .applyTo(currentProgram, monitor);
                function = manager.getFunctionAt(entry);
            }
            if (function != null && (function.getName().startsWith("FUN_") || !function.getName().equals(seed.getKey()))) {
                function.setName(seed.getKey(), SourceType.USER_DEFINED);
            }
        }
        analyzeChanges(currentProgram);

        try (PrintWriter writer = new PrintWriter(output, "UTF-8")) {
            writer.println("program=" + currentProgram.getName());
            writer.println("language=" + currentProgram.getLanguageID());
            writer.println("compiler=" + currentProgram.getCompilerSpec().getCompilerSpecID());
            writer.println();
            for (Map.Entry<String, Long> seed : SEEDS.entrySet()) {
                reportFunction(writer, manager.getFunctionAt(toAddr(seed.getValue())));
            }
        }
        println("Wrote overlay report to " + output.getAbsolutePath());
    }

    private void setThumb(Register tmode, long start, long end) throws Exception {
        for (long a = start; a <= end; a += 2) {
            Address addr = toAddr(a);
            if (currentProgram.getListing().getInstructionContaining(addr) == null) {
                currentProgram.getProgramContext().setValue(tmode, addr, addr, java.math.BigInteger.ONE);
            }
        }
    }

    private void reportFunction(PrintWriter writer, Function function) {
        if (function == null) {
            writer.println("FUNCTION <missing>");
            return;
        }
        writer.println("FUNCTION " + function.getName() + " entry=" + function.getEntryPoint() +
            " body=" + function.getBody());
        Set<String> refs = new LinkedHashSet<>();
        InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            writer.println("  INS " + instruction.getAddress() + " " + instruction);
            for (Reference reference : instruction.getReferencesFrom()) {
                Address target = reference.getToAddress();
                long offset = target.getOffset();
                Function targetFunction = manager().getFunctionAt(target);
                String name = targetFunction == null ? "<unnamed>" : targetFunction.getName();
                if (reference.getReferenceType().isCall() || reference.getReferenceType().isJump()) {
                    refs.add("  FLOW " + reference.getReferenceType() + " " + instruction.getAddress() +
                        " -> " + target + " " + name);
                } else if (offset < ROM_START || offset > ROM_END) {
                    refs.add("  EXTREF " + reference.getReferenceType() + " " + instruction.getAddress() +
                        " -> " + target);
                }
            }
        }
        for (String ref : refs) writer.println(ref);
        writer.println();
    }

    private FunctionManager manager() {
        return currentProgram.getFunctionManager();
    }
}
