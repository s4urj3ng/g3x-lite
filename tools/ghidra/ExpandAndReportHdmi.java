// Resolve direct tail branches from seeded GM1.10C HDMI procedures and report graphs.
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
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.SourceType;

public class ExpandAndReportHdmi extends GhidraScript {
    private static final long ROM_START = 0xfc000000L;
    private static final long ROM_END = 0xfdffffffL;
    private static final Map<String, Long> SEEDS = new LinkedHashMap<>();
    static {
        SEEDS.put("StartDisplayHDMIForFAMode", 0xfc5720d8L);
        SEEDS.put("StopDisplayHDMIForFAMode", 0xfc57226eL);
        SEEDS.put("TurnOnVideoOutMode", 0xfc613abcL);
        SEEDS.put("TurnOffVideoOutMode", 0xfc2b4fe8L);
        SEEDS.put("SetVideoOutType", 0xfc612c38L);
        SEEDS.put("GetVideoOutType", 0xfc612978L);
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        File output = new File(args.length > 0 ? args[0] : "/tmp/g3x-hdmi-expanded-callgraph.txt");
        FunctionManager manager = currentProgram.getFunctionManager();
        Map<String, Address> tails = new LinkedHashMap<>();

        for (Map.Entry<String, Long> seed : SEEDS.entrySet()) {
            Function function = manager.getFunctionAt(toAddr(seed.getValue()));
            if (function == null) {
                throw new IllegalStateException("Missing seeded function " + seed.getKey());
            }
            InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
            while (instructions.hasNext()) {
                Instruction instruction = instructions.next();
                for (Reference reference : instruction.getReferencesFrom()) {
                    if (!reference.getReferenceType().isJump()) {
                        continue;
                    }
                    Address target = reference.getToAddress();
                    long offset = target.getOffset();
                    if (function.getBody().contains(target) || offset < ROM_START || offset > ROM_END) {
                        continue;
                    }
                    tails.put(seed.getKey() + "_tail", target);
                }
            }
        }

        for (Map.Entry<String, Address> tail : tails.entrySet()) {
            Address entry = tail.getValue();
            DisassembleCommand disassemble = new DisassembleCommand(entry, null, true);
            disassemble.applyTo(currentProgram, monitor);
            Function function = manager.getFunctionAt(entry);
            if (function == null) {
                CreateFunctionCmd create = new CreateFunctionCmd(
                    tail.getKey(), entry, null, SourceType.USER_DEFINED);
                create.applyTo(currentProgram, monitor);
                function = manager.getFunctionAt(entry);
            }
            if (function != null && function.getName().startsWith("FUN_")) {
                function.setName(tail.getKey(), SourceType.USER_DEFINED);
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
            for (Map.Entry<String, Address> tail : tails.entrySet()) {
                writer.println("TAIL_BINDING " + tail.getKey() + "=" + tail.getValue());
                reportFunction(writer, manager.getFunctionAt(tail.getValue()));
            }
        }
        println("Wrote expanded HDMI call graph to " + output.getAbsolutePath());
    }

    private void reportFunction(PrintWriter writer, Function function) {
        if (function == null) {
            writer.println("FUNCTION <missing>");
            return;
        }
        writer.println("FUNCTION " + function.getName() + " entry=" + function.getEntryPoint() +
            " body=" + function.getBody());
        Set<String> flows = new LinkedHashSet<>();
        InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            for (Reference reference : instruction.getReferencesFrom()) {
                if (!reference.getReferenceType().isCall() && !reference.getReferenceType().isJump()) {
                    continue;
                }
                Address target = reference.getToAddress();
                Function targetFunction = currentProgram.getFunctionManager().getFunctionAt(target);
                String kind = reference.getReferenceType().isCall() ? "CALL" : "JUMP";
                flows.add("  " + kind + " " + instruction.getAddress() + " -> " + target + " " +
                    (targetFunction == null ? "<unnamed>" : targetFunction.getName()));
            }
        }
        if (flows.isEmpty()) {
            writer.println("  FLOW none-resolved");
        } else {
            for (String flow : flows) {
                writer.println(flow);
            }
        }
        writer.println();
    }
}
