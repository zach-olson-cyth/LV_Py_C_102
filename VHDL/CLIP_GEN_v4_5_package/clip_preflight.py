#!/usr/bin/env python3
"""
clip_preflight.py — CLIP_GEN v4.5 Preflight Checker
Checks a generated VHDL + XML pair against all Phase 8 rules.
Usage: python clip_preflight.py EntityName.vhd EntityName.xml
"""

import sys
import re
import xml.etree.ElementTree as ET

PASS = "✅"
FAIL = "❌"

results = []

def check(label, condition):
    status = PASS if condition else FAIL
    results.append((label, status))
    return condition

def report():
    width = max(len(r[0]) for r in results) + 2
    print(f"\n{'Check':<{width}} {'Status'}")
    print("-" * (width + 8))
    for label, status in results:
        print(f"{label:<{width}} {status}")
    fails = [r for r in results if r[1] == FAIL]
    print(f"\n{len(results) - len(fails)}/{len(results)} checks passed.")
    if fails:
        print("FAILED checks:")
        for label, _ in fails:
            print(f"  • {label}")
    return len(fails) == 0

# ── Load files ───────────────────────────────────────────────────────────────

if len(sys.argv) != 3:
    print("Usage: python clip_preflight.py EntityName.vhd EntityName.xml")
    sys.exit(1)

vhd_path, xml_path = sys.argv[1], sys.argv[2]

try:
    vhd = open(vhd_path, encoding="utf-8").read()
except FileNotFoundError:
    print(f"ERROR: VHDL file not found: {vhd_path}")
    sys.exit(1)

try:
    xml_text = open(xml_path, encoding="utf-8").read()
    root = ET.fromstring(xml_text)
except FileNotFoundError:
    print(f"ERROR: XML file not found: {xml_path}")
    sys.exit(1)
except ET.ParseError as e:
    print(f"ERROR: XML parse error: {e}")
    sys.exit(1)

# ── Derive entity name from VHDL file ────────────────────────────────────────

entity_match = re.search(r'\bentity\s+(\w+)\s+is\b', vhd, re.IGNORECASE)
entity_name = entity_match.group(1) if entity_match else ""

print(f"\nCLIP Preflight — {entity_name or '(entity not found)'}")
print("=" * 50)

# ══════════════════════════════════════════════════════════════════════════════
# VHDL CHECKS
# ══════════════════════════════════════════════════════════════════════════════

print("\n── VHDL ──")

check("ieee libs present",
      bool(re.search(r'ieee\.std_logic_1164\.all', vhd, re.IGNORECASE)) and
      bool(re.search(r'ieee\.numeric_std\.all', vhd, re.IGNORECASE)))

check("Entity name found",
      bool(entity_name))

check("Architecture name is RTL",
      bool(re.search(r'\barchitecture\s+RTL\s+of\b', vhd, re.IGNORECASE)))

# Port type check: extract entity port block only and normalize whitespace
# so that 'in  std_logic' (double space) does not cause a false positive.
def ports_ok(vhd_text):
    port_block = re.search(r'\bport\s*\((.*?)\)\s*;', vhd_text, re.DOTALL | re.IGNORECASE)
    if not port_block:
        return False
    ports_norm = re.sub(r'\s+', ' ', port_block.group(1))
    bad = re.search(r':\s*(?:in|out|inout)\s+(?!std_logic\b|std_logic_vector\b)',
                    ports_norm, re.IGNORECASE)
    return bad is None

check("Every entity port is std_logic or std_logic_vector",
      ports_ok(vhd))

check("No real, float, or vendor types",
      not bool(re.search(r'\b(real|float|ufixed|sfixed|UNISIM|VITAL)\b', vhd)))

check("No scientific notation in to_signed/to_unsigned",
      not bool(re.search(r'to_(signed|unsigned)\s*\([^)]*\d+[eE][+-]?\d+', vhd)))

check("Clocked process sensitivity list is (Clk) only",
      bool(re.search(r'process\s*\(\s*Clk\s*\)', vhd, re.IGNORECASE)))

check("aReset handled inside rising_edge",
      bool(re.search(r'rising_edge\s*\(.*?\).*?aReset', vhd, re.DOTALL | re.IGNORECASE)) and
      not bool(re.search(r'process\s*\([^)]*aReset', vhd, re.IGNORECASE)))

check("Ce gates the update correctly",
      bool(re.search(r"elsif\s+Ce\s*=\s*'1'", vhd, re.IGNORECASE)))

check("sat32 applied to all outputs",
      bool(re.search(r'\bsat32\b', vhd)))

check("All state registers assigned in aReset branch",
      bool(re.search(r"aReset\s*=\s*'1'", vhd, re.IGNORECASE)))

check("No output left undriven in any code path",
      bool(re.search(r"(others\s*=>\s*'0'|DataOut\s*<=|Output\s*<=)", vhd)))

# Division check: look for actual runtime '/' operator in the Ce block.
# Exclude lines that are comments and the 'sra' shift operator.
# Extract the Ce-gated block and strip comments before checking.
def no_runtime_div(vhd_text):
    ce_block = re.search(r"elsif\s+Ce\s*=\s*'1'\s+then(.*?)end\s+if",
                         vhd_text, re.DOTALL | re.IGNORECASE)
    if not ce_block:
        return True
    block = ce_block.group(1)
    # Strip single-line comments
    block_no_comments = re.sub(r'--[^\n]*', '', block)
    # Check for word/word division (excluding -- already removed)
    return not bool(re.search(r'\w\s*/\s*\w', block_no_comments))

check("No divisions in Ce-gated path",
      no_runtime_div(vhd))

check("Every multiply has shift-math comment",
      bool(re.search(r'--.*shift right \d+', vhd, re.IGNORECASE)) or
      bool(re.search(r'--.*Q\d+\.\d+\s+x\s+Q\d+\.\d+', vhd, re.IGNORECASE)))

# ══════════════════════════════════════════════════════════════════════════════
# XML CHECKS
# ══════════════════════════════════════════════════════════════════════════════

print("\n── XML ──")

# Root element
check("Root element is CLIPDeclaration with no xmlns",
      root.tag == "CLIPDeclaration" and "xmlns" not in root.attrib)

# FormatVersion must be first child and value 4.2
first_child = list(root)[0] if len(root) else None
check("FormatVersion 4.2 is first child of root",
      first_child is not None and
      first_child.tag == "FormatVersion" and
      (first_child.text or "").strip() == "4.2")

# InterfaceType is child of Interface
iface = root.find(".//Interface[@Name='LabVIEW']")
check("InterfaceType is child of Interface",
      iface is not None and iface.find("InterfaceType") is not None)

# Entity name in XML matches VHDL
xml_entity = root.findtext(".//SynthesisModel/Entity", "").strip()
check("Entity name matches VHDL and CLIPDeclaration Name",
      entity_name != "" and
      xml_entity == entity_name and
      root.attrib.get("Name", "") == entity_name)

# Entity name <= 31 chars
check(f"Entity name is 31 characters or fewer ({len(entity_name)} chars)",
      len(entity_name) <= 31)

# Collect all signals
signals = root.findall(".//SignalList/Signal")

# Every Signal has HDLName and HDLType
all_have_hdlname = all(s.find("HDLName") is not None for s in signals)
all_have_hdltype = all(s.find("HDLType") is not None for s in signals)
check("Every VHDL port has matching Signal with correct HDLName and HDLType",
      all_have_hdlname and all_have_hdltype)

# HDLType exact form for vectors
def hdltype_ok(s):
    ht = s.findtext("HDLType", "").strip()
    if ht == "std_logic":
        return True
    m = re.fullmatch(r'std_logic_vector\(\d+ downto \d+\)', ht)
    return bool(m)

check("HDLType is exactly std_logic[_vector(N downto 0)]",
      all(hdltype_ok(s) for s in signals))

# Every Signal has DataType with a child element (not text content)
def has_valid_datatype(s):
    dt = s.find("DataType")
    if dt is None:
        return False
    children = list(dt)
    if not children:
        return False
    # Must NOT have bare text as primary content
    text = (dt.text or "").strip()
    if text:
        return False
    return True

check("Every Signal has DataType containing a child element",
      all(has_valid_datatype(s) for s in signals))

# Every FXP DataType has Signed=true, WordLength, IntegerWordLength
def fxp_complete(s):
    dt = s.find("DataType")
    if dt is None:
        return True
    fxp = dt.find("FXP")
    if fxp is None:
        return True
    has_signed = fxp.find("Signed") is not None
    has_wl = fxp.find("WordLength") is not None
    has_iwl = fxp.find("IntegerWordLength") is not None
    signed_true = (fxp.findtext("Signed", "").strip().lower() == "true")
    return has_signed and has_wl and has_iwl and signed_true

check("Every FXP DataType contains Signed/WordLength/IntegerWordLength",
      all(fxp_complete(s) for s in signals))

# Clock signal checks
clk_signal = next((s for s in signals
                   if s.findtext("SignalType", "").strip() == "clock"), None)

check("Clock uses SignalType clock with FreqInHertz Max/Min",
      clk_signal is not None and
      clk_signal.find("FreqInHertz") is not None and
      clk_signal.find("FreqInHertz/Max") is not None and
      clk_signal.find("FreqInHertz/Min") is not None)

check("Clock has DataType containing Boolean/",
      clk_signal is not None and
      clk_signal.find("DataType") is not None and
      clk_signal.find("DataType/Boolean") is not None)

# No SignalType reset
check("No SignalType reset",
      not any(s.findtext("SignalType", "").strip() == "reset" for s in signals))

# All data signals have UseInLabVIEWSingleCycleTimedLoop
data_signals = [s for s in signals
                if s.findtext("SignalType", "").strip() == "data"]
check("All data signals have UseInLabVIEWSingleCycleTimedLoop Allowed",
      all(s.findtext("UseInLabVIEWSingleCycleTimedLoop", "").strip() == "Allowed"
          for s in data_signals))

# Directions are ToCLIP or FromCLIP only
valid_dirs = {"ToCLIP", "FromCLIP"}
check("Directions are ToCLIP or FromCLIP only",
      all(s.findtext("Direction", "").strip() in valid_dirs for s in signals))

# ImplementationList uses Path with TopLevel child element
impl_list = root.find("ImplementationList")
path_el = impl_list.find("Path") if impl_list is not None else None
top_level_child = path_el.find("TopLevel") if path_el is not None else None

check("ImplementationList uses Path with TopLevel child element",
      path_el is not None and
      top_level_child is not None and
      (top_level_child.text or "").strip().lower() == "true")

# No absolute path or dot-slash in Path Name
path_name = path_el.attrib.get("Name", "") if path_el is not None else ""
check("No absolute paths or dot-slash in Path Name",
      not path_name.startswith("/") and
      not path_name.startswith("./") and
      not path_name.startswith("\\") and
      "/" not in path_name and
      "\\" not in path_name)

# ── Final report ──────────────────────────────────────────────────────────────

ok = report()
sys.exit(0 if ok else 1)
