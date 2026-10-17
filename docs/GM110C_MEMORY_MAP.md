# GM1.10C evidence-bounded ROM map

Updated: 2026-10-17  
Image base: `0xFC000000`  
Image end: `0xFDFFFFFF`  
Input SHA-256: `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578`

## Reading this map

This is a **file-content map**, not a final CPU memory-permission map. “Populated” means only “not part of a long uniform `0xFF` run.” Code/data labels are used only where bytes, strings, or pointers support them. Exact segment boundaries, execute permissions, decompression, and RAM destinations remain unknown.

| ROM range | File offsets | Evidence | Status |
|---|---|---|---|
| `0xFC000000`–`0xFC004DD3` | `0x00000000`–`0x00004DD3` | header pointers; executable ARM/Thumb bytes; diagnostic strings; ARM trampoline at `0xFC004510` | confirmed populated boot/initialization material; exact entry chain unknown |
| `0xFC004DD4`–`0xFC01FFFF` | `0x00004DD4`–`0x0001FFFF` | one uniform `0xFF` run (`0x1B22C` bytes) | confirmed erased-looking/fill gap |
| `0xFC020000`–`0xFCEF63E7` | `0x00020000`–`0x00EF63E7` | `gaonisoy` at `+4`; dense pointers/instructions; firmware, DryOS, Canon, and toolchain strings; zero-heavy subregions | confirmed major populated component; internal code/data boundaries unresolved |
| `0xFCEF63E8`–`0xFD2FFFFF` | `0x00EF63E8`–`0x012FFFFF` | uniform `0xFF`, length `0x409C18` | confirmed largest fill gap |
| `0xFD300000`–`0xFD362DA7` | `0x01300000`–`0x01362DA7` | sparse populated islands separated by `0xFF` runs at `FD3033FE`–`FD31FFFF` and `FD320120`–`FD32205F` | confirmed sparse content; purpose unknown |
| `0xFD362DA8`–`0xFD4ED61F` | `0x01362DA8`–`0x014ED61F` | uniform `0xFF`, length `0x18A878` | confirmed fill gap |
| `0xFD4ED620`–`0xFD5121D7` | `0x014ED620`–`0x015121D7` | small populated islands separated by two `0xFF` runs over `0x5000` bytes each | confirmed sparse content; purpose unknown |
| `0xFD5121D8`–`0xFD61FFFF` | `0x015121D8`–`0x0161FFFF` | uniform `0xFF`, length `0x10DE28` | confirmed fill gap |
| `0xFD620000`–`0xFDAC63B3` | `0x01620000`–`0x01AC63B3` | mixed entropy; several very high-entropy 64 KiB blocks around `0xFD7A0000`–`0xFD7FFFFF`; many resource/model strings later | confirmed populated; likely mixed resources/components, exact formats unknown |
| `0xFDAC63B4`–`0xFDCBFFFF` | `0x01AC63B4`–`0x01CBFFFF` | uniform `0xFF`, length `0x1F9C4C` | confirmed fill gap |
| `0xFDCC0000`–`0xFDDFFFFF` | `0x01CC0000`–`0x01DFFFFF` | sparse islands; long `0xFF` and `0x00` runs; `G3X-831_Canon0B` at `0xFDDC2E70` | confirmed model/resource content and fill; execution unknown |
| `0xFDE00000`–`0xFDEFFFFF` | `0x01E00000`–`0x01EFFFFF` | high-entropy populated blocks interspersed with `0xFF` runs | confirmed populated data; compression/encoding hypothesis only |
| `0xFDF00000`–`0xFDFDFFFF` | `0x01F00000`–`0x01FDFFFF` | localized `Canon PowerShot G3 X` strings and multiple sparse islands separated by `0xFF` | confirmed localized model/resource region |
| `0xFDFE0000`–`0xFDFFFFFF` | `0x01FE0000`–`0x01FFFFFF` | uniform `0xFF`, length `0x20000` | confirmed terminal fill |

## Boot-header observations

| Address | Raw value / bytes | Evidence-supported interpretation |
|---:|---|---|
| `0xFC000000` | word `0xFC004510` | pointer to ARM-state trampoline; role in boot header not yet named |
| `0xFC000004` | word `0xFC00467C` | pointer into a numeric table; not established as code |
| `0xFC000008` | Thumb/Thumb-2-looking bytes | executable-looking, but not a confirmed reset entry |
| `0xFC004510` | `E28F0004 E3800001 E12FFF10` | ARM `ADD` / `ORR #1` / `BX` trampoline switching to Thumb state |
| `0xFC020004` | ASCII `gaonisoy` | main-component signature used by the CHDK universal dumper |

No conventional exception-vector layout has been positively identified. Do not label these words “reset vector” or “stack pointer” without cross-reference evidence.

## Notable exact uniform runs

These are the largest or diagnostically useful runs from `tools/analyze_rom.py --minimum-run 0x1000`:

| Byte | ROM start | ROM end | Length |
|---|---:|---:|---:|
| `FF` | `0xFCEF63E8` | `0xFD2FFFFF` | `0x409C18` |
| `FF` | `0xFDAC63B4` | `0xFDCBFFFF` | `0x1F9C4C` |
| `FF` | `0xFD362DA8` | `0xFD4ED61F` | `0x18A878` |
| `FF` | `0xFD5121D8` | `0xFD61FFFF` | `0x10DE28` |
| `FF` | `0xFDD00DE0` | `0xFDDBFFFF` | `0x0BF220` |
| `FF` | `0xFDDD1D80` | `0xFDDFFFFF` | `0x02E280` |
| `FF` | `0xFDF39140` | `0xFDF5FFFF` | `0x026EC0` |
| `FF` | `0xFDFE0000` | `0xFDFFFFFF` | `0x020000` |
| `00` | `0xFC94B93C` | `0xFC95D4D4` | `0x011B99` |
| `00` | `0xFCDE2922` | `0xFCDF36CF` | `0x010DAE` |
| `00` | `0xFC8F0618` | `0xFC8FFCD8` | `0x00F6C1` |
| `00` | `0xFDDC4CA6` | `0xFDDD1B83` | `0x00CEDE` |

All end addresses are inclusive. Uniform runs can be reproduced from the JSON output; no ranges were removed or rewritten in the source image.

## Ghidra block plan

For the first import, create one read-only raw block at `0xFC000000`, then split or remove execute permission from proven `0xFF` runs. Keep all other ranges “unknown data/code” until references establish them. In particular:

- set ARM context only at the proven trampoline `0xFC004510`;
- follow the trampoline's `BX` into Thumb state;
- do not force disassembly through the second header pointer or long fills;
- do not mark high-entropy areas compressed without identifying a format or decompressor;
- do not infer RAM addresses from runs of zero in the ROM file.

The map should be revised after cross references, CHDK signature results, and Ghidra block/file-format analysis provide stronger boundaries.
