# Makefile — PID_ValveController GHDL Functional Simulation
# Requirements: pip install cocotb pytest  &&  sudo apt install ghdl
# Targets: make sim | make vectors | make compile | make clean

VHDL_FILE  = PID_ValveController.vhd
ENTITY     = PID_ValveController
TB_MODULE  = test_pid_valve_cocotb
REF_SCRIPT = pid_fxp_reference.py

.PHONY: all sim compile vectors clean
all: sim

sim:
	MODULE=$(TB_MODULE) cocotb-run --sim ghdl --ghdl-args="--std=08" $(VHDL_FILE)

compile:
	ghdl -a --std=08 $(VHDL_FILE)
	ghdl -e --std=08 $(ENTITY)
	@echo "Compilation OK."

vectors:
	python3 $(REF_SCRIPT)

clean:
	rm -f *.o *.cf work-obj*.cf $(ENTITY) pid_test_vectors.csv
	rm -rf __pycache__ .cocotb sim_build results.xml
