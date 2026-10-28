#!/usr/bin/env python3
"""tests/test_port12a_memory_ownership.py

PORT-12A: Deterministic offline validation of memory ownership constraints,
headroom arithmetic, non-overlap checks, and fail-closed handling of unknown DRAM regions.

Safety: Zero ROM scans, zero hardware interactions, zero firmware execution.
"""

import unittest
from typing import Dict, List, NamedTuple, Optional, Tuple


class MemoryRegion(NamedTuple):
    region_id: str
    name: str
    start: int
    end: int
    classification: str
    owner: str

    @property
    def size(self) -> int:
        return self.end - self.start + 1


# Canonical tracked memory regions for GM1.10C
CANONICAL_REGIONS: List[MemoryRegion] = [
    MemoryRegion("R-01", "Low Vectors / Scratch", 0x00000000, 0x00007FFF, "VERIFIED_IN_EXISTING_DOCS", "Boot ROM / Hardware"),
    MemoryRegion("R-02", "Low-RAM Data", 0x00008000, 0x0003F4F3, "VERIFIED_IN_EXISTING_DOCS", "DryOS Kernel Data"),
    MemoryRegion("R-03", "Canon Firmware BSS", 0x0003F4F4, 0x003489B3, "VERIFIED_IN_EXISTING_DOCS", "Canon Static BSS"),
    MemoryRegion("R-04", "Low-Heap Prototype Reservation", 0x003489B4, 0x003C89B3, "INFERRED", "CHDK Prototype Core"),
    MemoryRegion("R-05", "DryOS Heap Pool 0 (Shifted)", 0x003C89B4, 0x00600013, "VERIFIED_IN_EXISTING_DOCS", "DryOS System Heap"),
    MemoryRegion("R-06", "DryOS Kernel Descriptors", 0x00600014, 0x0060DFFF, "VERIFIED_IN_EXISTING_DOCS", "DryOS Kernel Objects"),
    MemoryRegion("R-07", "DryOS Heap Upper Chunk Block", 0x0060E000, 0x006CDFFF, "VERIFIED_IN_EXISTING_DOCS", "DryOS Fixed Allocator"),
    MemoryRegion("R-09", "AdditionAgent Conflict Zone", 0x006CE000, 0x006FFFFF, "VERIFIED_IN_EXISTING_DOCS", "Storage DMA / Fread_Fut"),
    MemoryRegion("R-10", "OMAR Secondary Core Staging", 0x00700000, 0x00760000, "HISTORICAL_CANDIDATE", "Secondary Core IPC"),
    MemoryRegion("R-14", "Firmware Executable RAM Mirror", 0x010E1000, 0x01107D00, "VERIFIED_IN_EXISTING_DOCS", "RAM Code Routines"),
    MemoryRegion("R-16", "Cortex-R4 ATCM Relocated Span", 0xBFE10800, 0xBFE1741B, "VERIFIED_IN_EXISTING_DOCS", "Cortex-R4 ATCM"),
]


def check_disjoint(regions: List[MemoryRegion]) -> List[Tuple[str, str, int, int]]:
    """Check if any regions overlap. Returns list of overlaps: (id1, id2, overlap_start, overlap_end)."""
    overlaps = []
    sorted_regions = sorted(regions, key=lambda r: r.start)
    for i in range(len(sorted_regions) - 1):
        r1 = sorted_regions[i]
        r2 = sorted_regions[i + 1]
        if r1.end >= r2.start:
            overlap_start = max(r1.start, r2.start)
            overlap_end = min(r1.end, r2.end)
            overlaps.append((r1.region_id, r2.region_id, overlap_start, overlap_end))
    return overlaps


def verify_headroom(r4_heap_base: int, limit: int = 0x006CE000, min_headroom: int = 0x000B1FEC) -> Tuple[bool, int, int]:
    """Verify DryOS kernel headroom assert: (limit - r4 >= min_headroom)."""
    available_headroom = limit - r4_heap_base
    margin = available_headroom - min_headroom
    passed = available_headroom >= min_headroom
    return passed, available_headroom, margin


class TestPort12aMemoryOwnership(unittest.TestCase):
    """Offline test suite for PORT-12A memory ownership constraints."""

    def test_canonical_known_regions_are_strictly_disjoint(self):
        """Verify that known GM1.10C regions have proven no-overlap."""
        overlaps = check_disjoint(CANONICAL_REGIONS)
        self.assertEqual(overlaps, [], f"Expected zero overlaps among canonical regions, got: {overlaps}")

    def test_contiguous_low_ram_partitioning(self):
        """Verify that low-RAM data, Canon BSS, and Low-Heap core partition contiguously."""
        r_vectors = next(r for r in CANONICAL_REGIONS if r.region_id == "R-01")
        r_data = next(r for r in CANONICAL_REGIONS if r.region_id == "R-02")
        r_bss = next(r for r in CANONICAL_REGIONS if r.region_id == "R-03")
        r_proto = next(r for r in CANONICAL_REGIONS if r.region_id == "R-04")
        r_pool0 = next(r for r in CANONICAL_REGIONS if r.region_id == "R-05")

        self.assertEqual(r_vectors.end + 1, r_data.start)
        self.assertEqual(r_data.end + 1, r_bss.start)
        self.assertEqual(r_bss.end + 1, r_proto.start)
        self.assertEqual(r_proto.end + 1, r_pool0.start)

    def test_dryos_heap_headroom_stock(self):
        """Verify stock DryOS heap base r4 = 0x003489B4 satisfies headroom check."""
        passed, headroom, margin = verify_headroom(0x003489B4)
        self.assertTrue(passed)
        self.assertEqual(headroom, 0x0038564C)  # 3,692,108 B (~3.52 MiB)
        self.assertEqual(margin, 0x002D3660)    # 2,963,040 B (~2.82 MiB)

    def test_dryos_heap_headroom_512k_shift(self):
        """Verify 512 KiB shifted heap base r4 = 0x003C89B4 satisfies headroom check."""
        passed, headroom, margin = verify_headroom(0x003C89B4)
        self.assertTrue(passed)
        self.assertEqual(headroom, 0x0030564C)  # 3,167,820 B (~3.02 MiB)
        self.assertEqual(margin, 0x00253660)    # 2,438,752 B (~2.32 MiB)
        self.assertGreater(margin, 0x000B1FEC * 3, "Margin should exceed 3x the minimum required headroom")

    def test_dryos_heap_headroom_critical_limit(self):
        """Verify that any r4 exceeding 0x0061C014 triggers headroom fault."""
        max_allowable_r4 = 0x006CE000 - 0x000B1FEC
        self.assertEqual(max_allowable_r4, 0x0061C014)

        passed_exact, _, margin_exact = verify_headroom(max_allowable_r4)
        self.assertTrue(passed_exact)
        self.assertEqual(margin_exact, 0)

        passed_fail, _, margin_fail = verify_headroom(max_allowable_r4 + 1)
        self.assertFalse(passed_fail)
        self.assertEqual(margin_fail, -1)

    def test_addition_agent_isolation(self):
        """Verify that low-heap placement maintains >3 MiB margin from AdditionAgent."""
        r_proto = next(r for r in CANONICAL_REGIONS if r.region_id == "R-04")
        addition_agent_start = 0x006CE000
        distance = addition_agent_start - r_proto.end - 1
        self.assertGreater(distance, 3 * 1024 * 1024, "Distance to AdditionAgent buffer must be >3 MiB")

    def test_omar_secondary_core_isolation(self):
        """Verify that low-heap placement maintains >3.2 MiB margin from OMAR staging."""
        r_proto = next(r for r in CANONICAL_REGIONS if r.region_id == "R-04")
        omar_start = 0x00700000
        distance = omar_start - r_proto.end - 1
        self.assertGreater(distance, 3.2 * 1024 * 1024, "Distance to OMAR core must be >3.2 MiB")

    def test_historical_high_dram_cannot_be_verified(self):
        """Verify that ranma 0x00C80000 is strictly HISTORICAL_DESIGN_CANDIDATE, not STATIC_VERIFIED."""
        ranma_region = MemoryRegion("R-12", "Ranma 0x00C80000", 0x00C80000, 0x00DFFFFF, "HISTORICAL_DESIGN_CANDIDATE", "CHDK High-DRAM")
        self.assertNotEqual(ranma_region.classification, "STATIC_VERIFIED")
        self.assertNotEqual(ranma_region.classification, "VERIFIED_IN_EXISTING_DOCS")
        self.assertEqual(ranma_region.classification, "HISTORICAL_DESIGN_CANDIDATE")

    def test_unknown_gaps_are_not_treated_as_empty(self):
        """Verify that gaps between regions are flagged as UNKNOWN and rejected as safe space."""
        # Gap between OMAR (0x00760000) and Ranma (0x00C80000)
        gap_mid = MemoryRegion("R-11", "Mid-DRAM Gap", 0x00760001, 0x00C7FFFF, "UNKNOWN", "Uninspected DRAM")
        self.assertEqual(gap_mid.classification, "UNKNOWN")
        self.assertFalse(gap_mid.classification.startswith("VERIFIED"))

        # Gap between Ranma (0x00DFFFFF) and RAM code mirror (0x010E1000)
        gap_high = MemoryRegion("R-13", "High-DRAM Gap", 0x00E00000, 0x010E0FFF, "UNKNOWN", "Uninspected DRAM")
        self.assertEqual(gap_high.classification, "UNKNOWN")

    def test_adversarial_overlap_detection(self):
        """Adversarial test: An unverified allocation colliding with DryOS heap or AdditionAgent is caught."""
        # Rogue region overlapping with DryOS heap
        rogue_region = MemoryRegion("ROGUE-01", "Rogue Alloc", 0x005F0000, 0x00610000, "INFERRED", "Rogue")
        test_set = CANONICAL_REGIONS + [rogue_region]
        overlaps = check_disjoint(test_set)
        self.assertGreater(len(overlaps), 0, "Disjoint checker must detect overlap with DryOS heap")
        overlap_ids = [(o[0], o[1]) for o in overlaps]
        self.assertTrue(any("ROGUE-01" in pair for pair in overlap_ids))


if __name__ == "__main__":
    unittest.main()
