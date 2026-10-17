// Seed evidence-backed GM1.10C HDMI Thumb functions and report local call graphs.
// @category G3X

import java.io.File;
import java.io.PrintWriter;
import java.math.BigInteger;
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
import ghidra.program.model.symbol.RefType;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.SourceType;

public class SeedAndReportHdmi extends GhidraScript {
    private static final long ROM_START = 0xfc000000L;
    private static final long ROM_END = 0xfdffffffL;

    private static final Map<String, Long> SEEDS = new LinkedHashMap<>();
    static {
        SEEDS.put("StartDisplayHDMIForFAMode", 0xfc5720d9L);
        SEEDS.put("StopDisplayHDMIForFAMode", 0xfc57226fL);
        SEEDS.put("TurnOnVideoOutMode", 0xfc613abdL);
        SEEDS.put("TurnOffVideoOutMode", 0xfc2b4fe9L);
        SEEDS.put("SetVideoOutType", 0xfc612c39L);
        SEEDS.put("GetVideoOutType", 0xfc612979L);
        SEEDS.put("DispCon_SetDisplayType", 0xfc37cbffL);
        SEEDS.put("DispCon_TurnOnDisplay", 0xfc37caa5L);
        SEEDS.put("DispCon_TurnOffDisplay", 0xfc37cd09L);
        SEEDS.put("SwitchOnDisplay", 0xfc61294bL);
        SEEDS.put("SwitchOffDisplay", 0xfc612941L);
    }

    @Override
    protected void run() throws Exception {
        if (!"ARM:LE:32:v7".equals(currentProgram.getLanguageID().getIdAsString())) {
            throw new IllegalStateException("Unexpected language: " + currentProgram.getLanguageID());
        }
        if (!"default".equals(currentProgram.getCompilerSpec().getCompilerSpecID().getIdAsString())) {
            throw new IllegalStateException("Unexpected compiler spec: " + currentProgram.getCompilerSpec());
        }

        String[] args = getScriptArgs();
        File output = new File(args.length > 0 ? args[0] : "/tmp/g3x-hdmi-callgraph.txt");
        Register tmode = currentProgram.getProgramContext().getRegister("TMode");
        if (tmode == null) {
            throw new IllegalStateException("ARM TMode context register is unavailable");
        }

        // Context must be established before any instructions are created because
        // Ghidra prevents context changes across existing code units.
        for (Map.Entry<String, Long> seed : SEEDS.entrySet()) {
            long pointer = seed.getValue();
            if ((pointer & 1) == 0 || pointer < ROM_START || pointer > ROM_END) {
                throw new IllegalStateException("Invalid Thumb ROM pointer: " + Long.toHexString(pointer));
            }
            Address entry = toAddr(pointer & ~1L);
            // Establish Thumb context for a bounded local analysis window. This does
            // not create instructions or imply that the entire window is code.
            currentProgram.getProgramContext().setValue(tmode, entry, entry.add(0x7ff), BigInteger.ONE);
        }

        for (Map.Entry<String, Long> seed : SEEDS.entrySet()) {
            long pointer = seed.getValue();
            Address entry = toAddr(pointer & ~1L);
            DisassembleCommand disassemble = new DisassembleCommand(entry, null, true);
            if (!disassemble.applyTo(currentProgram, monitor)) {
                throw new IllegalStateException("Disassembly failed at " + entry + ": " + disassemble.getStatusMsg());
            }
            Function function = getFunctionAt(entry);
            if (function == null) {
                CreateFunctionCmd create = new CreateFunctionCmd(
                    seed.getKey(), entry, null, SourceType.USER_DEFINED);
                if (!create.applyTo(currentProgram, monitor)) {
                    throw new IllegalStateException("Function creation failed at " + entry + ": " + create.getStatusMsg());
                }
                function = getFunctionAt(entry);
            }
            if (function == null) {
                throw new IllegalStateException("No function at " + entry);
            }
            function.setName(seed.getKey(), SourceType.USER_DEFINED);
        }

        analyzeChanges(currentProgram);

        try (PrintWriter writer = new PrintWriter(output, "UTF-8")) {
            writer.println("program=" + currentProgram.getName());
            writer.println("language=" + currentProgram.getLanguageID());
            writer.println("compiler=" + currentProgram.getCompilerSpec().getCompilerSpecID());
            writer.println("image_min=" + currentProgram.getMemory().getMinAddress());
            writer.println("image_max=" + currentProgram.getMemory().getMaxAddress());
            writer.println();

            FunctionManager functions = currentProgram.getFunctionManager();
            for (Map.Entry<String, Long> seed : SEEDS.entrySet()) {
                Address entry = toAddr(seed.getValue() & ~1L);
                Function function = functions.getFunctionAt(entry);
                writer.println("FUNCTION " + seed.getKey() + " entry=" + entry +
                    " body=" + function.getBody() + " params=" + function.getParameterCount());

                Set<String> calls = new LinkedHashSet<>();
                InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
                while (instructions.hasNext()) {
                    Instruction instruction = instructions.next();
                    for (Reference reference : instruction.getReferencesFrom()) {
                        RefType type = reference.getReferenceType();
                        if (!type.isCall()) {
                            continue;
                        }
                        Address target = reference.getToAddress();
                        Function targetFunction = functions.getFunctionAt(target);
                        String targetName = targetFunction == null ? "<unnamed>" : targetFunction.getName();
                        calls.add(instruction.getAddress() + " -> " + target + " " + targetName);
                    }
                }
                if (calls.isEmpty()) {
                    writer.println("  CALLEE none-resolved");
                } else {
                    for (String call : calls) {
                        writer.println("  CALLEE " + call);
                    }
                }

                int callerCount = 0;
                for (Reference reference : currentProgram.getReferenceManager().getReferencesTo(entry)) {
                    if (!reference.getReferenceType().isCall()) {
                        continue;
                    }
                    Function caller = functions.getFunctionContaining(reference.getFromAddress());
                    writer.println("  CALLER " + reference.getFromAddress() + " " +
                        (caller == null ? "<unknown>" : caller.getName()));
                    callerCount++;
                }
                if (callerCount == 0) {
                    writer.println("  CALLER none-resolved-in-seeded-analysis");
                }
                writer.println();
            }
        }
        println("Wrote HDMI call graph to " + output.getAbsolutePath());
    }
}
