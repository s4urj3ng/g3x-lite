// Report static references to selected GM1.10C display/compositor strings.
// @category G3X

import java.io.File;
import java.io.PrintWriter;
import java.util.LinkedHashMap;
import java.util.Map;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class ReportDisplayStringRefs extends GhidraScript {
    private static final Map<String, Long> TARGETS = new LinkedHashMap<>();
    static {
        TARGETS.put("MzrmGraphic", 0xfc113078L);
        TARGETS.put("BmpDev.c", 0xfc1837f0L);
        TARGETS.put("MakeOsdVram.c", 0xfc183b7cL);
        TARGETS.put("Window_EmergencyRefreshPhysicalScreen", 0xfc1f1624L);
        TARGETS.put("SCM.c", 0xfc33d510L);
        TARGETS.put("VramTransferManager.c", 0xfc380828L);
        TARGETS.put("GrVramInfo.c", 0xfc388fb0L);
        TARGETS.put("ZicoKick Start", 0xfc3dfdccL);
        TARGETS.put("Palette Class.", 0xfc77b62cL);
        TARGETS.put("GVDN_MallocVGPalette", 0xfcc9cdd0L);
        TARGETS.put("InitializeGrypForNormal", 0xfccb5ec0L);
        TARGETS.put("GrypSetSrcVramHandle", 0xfccb5fd4L);
        TARGETS.put("GrypSetDstVramHandle", 0xfccb5fecL);
        TARGETS.put("GrypSetColorTableBuffer", 0xfccb6318L);
        TARGETS.put("GrypSetDcSpecialPalette", 0xfccb6334L);
        TARGETS.put("InitializeXimr", 0xfccb69d0L);
        TARGETS.put("XimrExe", 0xfccb69f0L);
        TARGETS.put("XIMR offset diagnostic", 0xfccb7c50L);
        TARGETS.put("GRYP src diagnostic", 0xfccb8b04L);
        TARGETS.put("hasGapLayer", 0xfccb9464L);
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        File output = new File(args.length > 0 ? args[0] : "/tmp/g3x-display-string-refs.txt");
        try (PrintWriter writer = new PrintWriter(output, "UTF-8")) {
            for (Map.Entry<String, Long> target : TARGETS.entrySet()) {
                Address address = toAddr(target.getValue());
                writer.println("TARGET " + target.getKey() + " " + address);
                ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(address);
                boolean found = false;
                while (refs.hasNext()) {
                    found = true;
                    Reference ref = refs.next();
                    Function f = currentProgram.getFunctionManager().getFunctionContaining(ref.getFromAddress());
                    writer.println("  " + ref.getReferenceType() + " from=" + ref.getFromAddress() +
                        " function=" + (f == null ? "<none>" : f.getName() + "@" + f.getEntryPoint()));
                }
                if (!found) writer.println("  no-resolved-references");
            }
        }
        println("Wrote display string references to " + output.getAbsolutePath());
    }
}
