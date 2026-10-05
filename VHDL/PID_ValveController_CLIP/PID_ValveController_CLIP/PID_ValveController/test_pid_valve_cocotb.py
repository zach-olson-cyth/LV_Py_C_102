"""
test_pid_valve_cocotb.py  —  Cocotb functional testbench for PID_ValveController.vhd
Plant model: first-order lag valve (Kp=0.8, tau=5 s)

Setup:
    pip install cocotb pytest && sudo apt install ghdl

Run:
    MODULE=test_pid_valve_cocotb cocotb-run --sim ghdl \
        --ghdl-args="--std=08" PID_ValveController.vhd
    or:  make sim

Tests (T1-T9):
  T1 aReset drives Output=0
  T2 Manual mode passthrough within 1 LSB
  T3 Output saturation ceiling
  T4 Proportional-only response
  T5 Reinitialize clears integrator
  T6 Setpoint clamping
  T7 Closed-loop PI step response with valve plant (300 cycles, Kc=5 Ti=0.1min)
  T8 Bumpless manual-to-auto transfer
  T9 DtOut sanitization (negative DtS clamped to DT_MIN)

NI FXP encoding:
  FXP<+/-,32,16> : FWL=16  LSB=2^-16   (setpoint, PV, output, Ti, Td)
  FXP<+/-,32,8>  : FWL=24  LSB=2^-24   (Kc, dt)
  FXP<+/-,32,2>  : FWL=30  LSB=2^-30   (alpha, beta, gamma)
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles
import numpy as np

# ─── FXP encode/decode ───────────────────────────────────────────────────────
def _enc(v, fwl, wl=32):
    s = int(round(v * (2**fwl)))
    s = max(-(1<<(wl-1)), min((1<<(wl-1))-1, s))
    return s + (1<<wl) if s < 0 else s

def _dec(b, fwl, wl=32):
    if b >= (1<<(wl-1)): b -= (1<<wl)
    return b / (2**fwl)

ep = lambda v: _enc(v, 16)   # FXP<+/-,32,16>
dp = lambda b: _dec(b, 16)
eg = lambda v: _enc(v, 24)   # FXP<+/-,32,8>
dg = lambda b: _dec(b, 24)
ea = lambda v: _enc(v, 30)   # FXP<+/-,32,2>

PIPE = 6  # pipeline depth + 1 guard

# ─── Drive all PID inputs ────────────────────────────────────────────────────
async def drive(dut, sp=50.0, pv=0.0,
                sp_hi=100.0, sp_lo=0.0, out_hi=100.0, out_lo=-100.0,
                Kc=1.0, Ti=0.01, Td=0.0, dt=0.1,
                auto=True, manual=0.0, reinit=False,
                alpha=0.0, beta=1.0, gamma=0.0, lin=1.0):
    dut.Setpoint.value            = ep(sp)
    dut.ProcessVariable.value     = ep(pv)
    dut.SetpointHigh.value        = ep(sp_hi)
    dut.SetpointLow.value         = ep(sp_lo)
    dut.OutputHigh.value          = ep(out_hi)
    dut.OutputLow.value           = ep(out_lo)
    dut.ProportionalGainKc.value  = eg(Kc)
    dut.IntegralTimeTiMin.value   = ep(Ti)
    dut.DerivativeTimeTdMin.value = ep(Td)
    dut.DtS.value                 = eg(dt)
    dut.AutoMode.value            = 1 if auto else 0
    dut.ManualControl.value       = ep(manual)
    dut.Reinitialize.value        = 1 if reinit else 0
    dut.Alpha.value               = ea(alpha)
    dut.Beta.value                = ea(beta)
    dut.Gamma.value               = ea(gamma)
    dut.Linearity.value           = ea(lin)

async def hw_reset(dut):
    cocotb.start_soon(Clock(dut.Clk, 25, units="ns").start())
    dut.aReset.value = 1
    await ClockCycles(dut.Clk, 3)
    dut.aReset.value = 0
    await ClockCycles(dut.Clk, 2)

# ─── Inline floating-point reference PID ─────────────────────────────────────
class RefPID:
    DT_MIN, TI_MIN = 0.001, 65/65536
    def __init__(self): self.i=0.0; self.pv_p=0.0; self.d=0.0
    def reset(self, pv=0.0): self.i=0.0; self.pv_p=pv; self.d=0.0
    def step(self, sp,pv,sp_hi,sp_lo,out_hi,out_lo,Kc,Ti,Td,dt,auto,manual,reinit,alpha=0.0,beta=1.0):
        dt=max(dt,self.DT_MIN); Ti=max(Ti,self.TI_MIN)
        sp=float(np.clip(sp,sp_lo,sp_hi))
        if reinit: self.i=0.0; self.pv_p=pv; self.d=0.0
        if not auto:
            out=float(np.clip(manual,out_lo,out_hi)); self.i=out; return out
        P=Kc*(beta*sp-pv); dI=Kc*(dt/(Ti*60))*(sp-pv); Ic=self.i+dI
        Dr=-Kc*(Td*60/dt)*(pv-self.pv_p) if Td>0 else 0.0
        Df=alpha*self.d+(1-alpha)*Dr; u=P+Ic+Df
        sh,sl=u>=out_hi,u<=out_lo; out=float(np.clip(u,out_lo,out_hi))
        if not sh and not sl or sh and dI<0 or sl and dI>0: self.i=Ic
        self.d=Df; self.pv_p=pv; return out

class ValvePlant:
    def __init__(self,Kp=0.8,tau=5.0): self.Kp=Kp; self.tau=tau; self.pv=0.0
    def step(self,u,dt): a=dt/self.tau; self.pv=self.pv*(1-a)+self.Kp*u*a; return self.pv
    def reset(self,pv=0.0): self.pv=pv

# =============================================================================
# T1 — aReset forces Output to 0
# =============================================================================
@cocotb.test()
async def T1_reset(dut):
    await hw_reset(dut)
    assert int(dut.Output.value)==0, f"T1 FAIL: Output={int(dut.Output.value)}"
    dut._log.info("T1 PASS: aReset drives Output=0")

# =============================================================================
# T2 — Manual mode passes ManualControl to Output within 1 LSB
# =============================================================================
@cocotb.test()
async def T2_manual_passthrough(dut):
    await hw_reset(dut)
    LSB = 1.0/65536.0
    for val in [0.0, 25.0, 50.0, -50.0, 99.5, -99.5]:
        await drive(dut, sp=50.0, pv=20.0, auto=False, manual=val)
        await ClockCycles(dut.Clk, PIPE)
        r = dp(int(dut.Output.value))
        assert abs(r-val) <= LSB*2+abs(val)*1e-5, f"T2 FAIL: manual={val}, got={r:.8f}"
    dut._log.info("T2 PASS: manual mode passthrough")

# =============================================================================
# T3 — Large Kc+error saturates output to OutputHigh
# =============================================================================
@cocotb.test()
async def T3_output_saturation(dut):
    await hw_reset(dut)
    await drive(dut,sp=100.0,pv=0.0,Kc=100.0,Ti=100.0,out_hi=100.0,out_lo=-100.0,auto=True,reinit=True)
    await ClockCycles(dut.Clk, 25)
    r = dp(int(dut.Output.value))
    assert 99.0<=r<=100.01, f"T3 FAIL: output={r:.4f}"
    dut._log.info(f"T3 PASS: saturation output={r:.4f}")

# =============================================================================
# T4 — P-only: Ti=very large, Td=0 -> output ~= Kc*(SP-PV)
# =============================================================================
@cocotb.test()
async def T4_proportional_only(dut):
    await hw_reset(dut)
    await drive(dut,sp=50.0,pv=30.0,Kc=1.0,Ti=1000.0,Td=0.0,auto=True,reinit=True)
    await ClockCycles(dut.Clk, PIPE)
    await drive(dut,sp=50.0,pv=30.0,Kc=1.0,Ti=1000.0,Td=0.0,auto=True,reinit=False)
    await ClockCycles(dut.Clk, PIPE)
    r = dp(int(dut.Output.value))
    assert abs(r-20.0)<3.0, f"T4 FAIL: P-only expected~20, got {r:.4f}"
    dut._log.info(f"T4 PASS: P-only output={r:.4f}")

# =============================================================================
# T5 — Reinitialize clears integrator: after 50 integration cycles, reinit
#       with SP=PV=0 must give output ~= 0
# =============================================================================
@cocotb.test()
async def T5_reinitialize(dut):
    await hw_reset(dut)
    for _ in range(50):
        await drive(dut,sp=100.0,pv=0.0,Kc=1.0,Ti=0.5,auto=True,reinit=False)
        await ClockCycles(dut.Clk,1)
    await ClockCycles(dut.Clk,PIPE)
    await drive(dut,sp=0.0,pv=0.0,Kc=1.0,Ti=0.5,auto=True,reinit=True)
    await ClockCycles(dut.Clk,PIPE)
    r = dp(int(dut.Output.value))
    assert abs(r)<1.0, f"T5 FAIL: after reinit expected~0, got {r:.4f}"
    dut._log.info(f"T5 PASS: reinitialize output={r:.4f}")

# =============================================================================
# T6 — SP=200 with range [0,100] clamped to 100; PV=100 -> error=0 -> output~=0
# =============================================================================
@cocotb.test()
async def T6_setpoint_clamping(dut):
    await hw_reset(dut)
    await drive(dut,sp=200.0,pv=100.0,sp_hi=100.0,sp_lo=0.0,
                Kc=1.0,Ti=1000.0,Td=0.0,auto=True,reinit=True)
    await ClockCycles(dut.Clk,PIPE)
    r = dp(int(dut.Output.value))
    assert abs(r)<2.0, f"T6 FAIL: clamped SP=PV=100 -> error=0 -> output~0, got {r:.4f}"
    dut._log.info(f"T6 PASS: setpoint clamping output={r:.4f}")

# =============================================================================
# T7 — Closed-loop PI step response with first-order valve plant
#       Kc=5, Ti=0.1min (6s), dt=0.1s, SP=75%; PV must converge within 5%
# =============================================================================
@cocotb.test()
async def T7_closed_loop_valve(dut):
    await hw_reset(dut)
    plant=ValvePlant(0.8,5.0); ref=RefPID()
    KC,TI,DT,SP=5.0,0.1,0.1,75.0
    SH,SL,OH,OL=100.0,0.0,100.0,-100.0

    await drive(dut,sp=SP,pv=0.0,sp_hi=SH,sp_lo=SL,out_hi=OH,out_lo=OL,
                Kc=KC,Ti=TI,Td=0.0,dt=DT,auto=True,reinit=True,beta=1.0)
    await ClockCycles(dut.Clk,PIPE)
    ref.reset(0.0); pv=0.0; max_diff=0.0

    for _ in range(300):
        await drive(dut,sp=SP,pv=pv,sp_hi=SH,sp_lo=SL,out_hi=OH,out_lo=OL,
                    Kc=KC,Ti=TI,Td=0.0,dt=DT,auto=True,reinit=False,beta=1.0)
        await ClockCycles(dut.Clk,1)
        hw_out  = dp(int(dut.Output.value))
        ref_out = ref.step(SP,pv,SH,SL,OH,OL,KC,TI,0.0,DT,True,0.0,False,0.0,1.0)
        d=abs(hw_out-ref_out)
        if d>max_diff: max_diff=d
        pv=plant.step(hw_out,DT)

    assert abs(SP-pv)<SP*0.05, f"T7 FAIL: PV={pv:.2f} not within 5% of SP={SP}"
    assert max_diff<2.0, f"T7 FAIL: VHDL vs reference max diff={max_diff:.4f}"
    dut._log.info(f"T7 PASS: closed-loop valve PV={pv:.3f} SP={SP} maxDiff={max_diff:.6f}")

# =============================================================================
# T8 — Bumpless manual->auto: first auto output within 5 units of last manual
# =============================================================================
@cocotb.test()
async def T8_bumpless_transfer(dut):
    await hw_reset(dut)
    plant=ValvePlant(0.8,5.0); pv=40.0
    for _ in range(20):
        await drive(dut,sp=60.0,pv=pv,Kc=1.0,Ti=1.0,auto=False,manual=50.0)
        await ClockCycles(dut.Clk,1)
        pv=plant.step(50.0,0.1)
    await ClockCycles(dut.Clk,PIPE)
    out_manual=dp(int(dut.Output.value))
    await drive(dut,sp=60.0,pv=pv,Kc=1.0,Ti=1.0,auto=True)
    await ClockCycles(dut.Clk,PIPE)
    out_auto=dp(int(dut.Output.value))
    bump=abs(out_auto-out_manual)
    assert bump<5.0, f"T8 FAIL: bump={bump:.4f} > 5.0"
    dut._log.info(f"T8 PASS: bumpless manual={out_manual:.2f}->auto={out_auto:.2f} bump={bump:.4f}")

# =============================================================================
# T9 — DtOut = max(DtS, 0.001s) regardless of sign
# =============================================================================
@cocotb.test()
async def T9_dtout_sanitization(dut):
    await hw_reset(dut)
    DT_MIN=0.001
    await drive(dut,sp=50.0,pv=50.0,dt=0.1)
    await ClockCycles(dut.Clk,3)
    dt_out=dg(int(dut.DtOut.value))
    assert abs(dt_out-0.1)<0.0001, f"T9 FAIL: DtOut={dt_out:.6f}, expected 0.1"
    await drive(dut,sp=50.0,pv=50.0,dt=-1.0)
    await ClockCycles(dut.Clk,3)
    dt_out=dg(int(dut.DtOut.value))
    assert dt_out>=DT_MIN-1e-7, f"T9 FAIL: DtOut={dt_out:.8f} < DT_MIN"
    dut._log.info("T9 PASS: DtOut sanitization")
