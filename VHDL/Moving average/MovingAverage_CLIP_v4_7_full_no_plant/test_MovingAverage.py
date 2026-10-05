"""cocotb testbench skeleton for MovingAverage.
Not runnable in this environment but serves as a template.
"""

import cocotb
from cocotb.triggers import RisingEdge
from MovingAverage_reference_model import MovingAverageRef

N = 16

@cocotb.test()
async def test_step_response(dut):
    ref = MovingAverageRef(N)

    # Reset sequence
    dut.aReset.value = 1
    dut.Ce.value = 0
    dut.DataIn.value = 0
    for _ in range(5):
        await RisingEdge(dut.Clk)
    dut.aReset.value = 0
    dut.Ce.value = 1

    # Apply step from 0 to 100
    for k in range(40):
        x = 100.0 if k >= 4 else 0.0
        # Q16.16 encode
        fxp = int(x * (1 << 16)) & 0xFFFFFFFF
        dut.DataIn.value = fxp
        await RisingEdge(dut.Clk)
        y_ref = ref.step(x)
        y_fxp = dut.DataOut.value.signed_integer
        y = y_fxp / float(1 << 16)
        dut._log.info(f"k={k} x={x} y_ref={y_ref} y={y}")
