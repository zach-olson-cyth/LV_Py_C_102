"""
pid_fxp_reference.py
====================
Python FXP reference model + test vector generator for PID_ValveController.vhd

Usage:  python pid_fxp_reference.py
Output: pid_test_vectors.csv  (401 rows covering step response, manual, reinit)
"""

import numpy as np, csv, os
from dataclasses import dataclass


@dataclass
class FXPFormat:
    """NI LabVIEW FXP<+/-,W,IWL>   LSB = 2^(-(W-IWL))"""
    signed: bool
    word_length: int
    integer_word_length: int

    @property
    def fwl(self): return self.word_length - self.integer_word_length
    @property
    def lsb(self): return 2.0**(-self.fwl)
    @property
    def rmax(self): return (2**(self.integer_word_length-1)-self.lsb) if self.signed else (2**self.integer_word_length-self.lsb)
    @property
    def rmin(self): return -(2**(self.integer_word_length-1)) if self.signed else 0.0
    def to_bits(self,v):
        s=int(round(v/self.lsb)); hi=(1<<(self.word_length-1))-1; lo=-(1<<(self.word_length-1))
        s=max(lo,min(hi,s)); return s+(1<<self.word_length) if s<0 else s
    def from_bits(self,b):
        if b>=(1<<(self.word_length-1)): b-=(1<<self.word_length)
        return b*self.lsb
    def quantize(self,v): return self.from_bits(self.to_bits(v))
    def __str__(self):
        return (f"FXP<{'+/-' if self.signed else '+'},"
                f"{self.word_length},{self.integer_word_length}>"
                f"  LSB={self.lsb:.2e}  range=[{self.rmin:.1f},{self.rmax:.4f}]")


FMT_PROCESS = FXPFormat(signed=True, word_length=32, integer_word_length=16)
FMT_GAIN    = FXPFormat(signed=True, word_length=32, integer_word_length=8)
FMT_ALPHA   = FXPFormat(signed=True, word_length=32, integer_word_length=2)


def validate_fxp_formats():
    print("\n" + "="*64)
    print("NI FXP PORT FORMAT VALIDATION")
    print("="*64)
    for name, fmt in [
        ("setpoint, PV, output, Ti(min), Td(min)", FMT_PROCESS),
        ("proportional gain (Kc), dt(s)",           FMT_GAIN),
        ("alpha, beta, gamma, linearity",            FMT_ALPHA),
    ]:
        print(f"\n  {name}\n  {fmt}")
    print()
    print("  Encode/decode round-trip:")
    for fmt,v,label in [(FMT_PROCESS,75.0,"FXP<+/-,32,16> 75.0"),
                        (FMT_GAIN,1.0,"FXP<+/-,32,8>  1.0"),
                        (FMT_GAIN,0.1,"FXP<+/-,32,8>  0.1s"),
                        (FMT_ALPHA,1.0,"FXP<+/-,32,2>  beta=1.0"),
                        (FMT_ALPHA,0.0,"FXP<+/-,32,2>  alpha=0.0 (NaN)")]:
        b=fmt.to_bits(v); d=fmt.from_bits(b)
        print(f"    {label:<28} bits={b:>11d}  back={d:>12.8f}  err={abs(d-v):.1e}")
    print()
    print("  Key bit patterns (hex):")
    for label,fmt,v in [("setpoint=75.0",FMT_PROCESS,75.0),
                         ("output_high=100.0",FMT_PROCESS,100.0),
                         ("output_low=-100.0",FMT_PROCESS,-100.0),
                         ("Kc=1.0",FMT_GAIN,1.0),("Kc=5.0",FMT_GAIN,5.0),
                         ("dt=0.1s",FMT_GAIN,0.1),("Ti=0.1min",FMT_PROCESS,0.1),
                         ("beta=1.0",FMT_ALPHA,1.0),("alpha=0.0",FMT_ALPHA,0.0)]:
        b=fmt.to_bits(v)
        print(f"    {label:<22}  0x{b:08X}  ({b})")
    print("="*64+"\n")


class ReferencePID:
    DT_MIN, TI_MIN = 0.001, 65/65536
    def __init__(self): self.i=0.0; self.pv_p=0.0; self.d=0.0
    def reset(self,pv=0.0): self.i=0.0; self.pv_p=pv; self.d=0.0
    def step(self,sp,pv,sp_hi,sp_lo,out_hi,out_lo,Kc,Ti,Td,dt,auto,manual,reinit,alpha=0.0,beta=1.0):
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


class FXPQuantizedPID(ReferencePID):
    def step(self,sp,pv,sp_hi,sp_lo,out_hi,out_lo,Kc,Ti,Td,dt,auto,manual,reinit,alpha=0.0,beta=1.0):
        sp=FMT_PROCESS.quantize(sp); pv=FMT_PROCESS.quantize(pv)
        sp_hi=FMT_PROCESS.quantize(sp_hi); sp_lo=FMT_PROCESS.quantize(sp_lo)
        out_hi=FMT_PROCESS.quantize(out_hi); out_lo=FMT_PROCESS.quantize(out_lo)
        Kc=FMT_GAIN.quantize(Kc); Ti=FMT_PROCESS.quantize(Ti); Td=FMT_PROCESS.quantize(Td)
        dt=FMT_GAIN.quantize(dt); manual=FMT_PROCESS.quantize(manual)
        alpha=FMT_ALPHA.quantize(alpha); beta=FMT_ALPHA.quantize(beta)
        r=super().step(sp,pv,sp_hi,sp_lo,out_hi,out_lo,Kc,Ti,Td,dt,auto,manual,reinit,alpha,beta)
        return FMT_PROCESS.quantize(r)


class ValvePlant:
    """First-order lag: PV[k+1] = PV[k]*(1-dt/tau) + Kp*u[k]*(dt/tau)"""
    def __init__(self,Kp=0.8,tau=5.0): self.Kp=Kp; self.tau=tau; self.pv=0.0
    def step(self,u,dt): a=dt/self.tau; self.pv=self.pv*(1-a)+self.Kp*u*a; return self.pv
    def reset(self,pv=0.0): self.pv=pv


def run_self_test():
    P,F="PASS","FAIL"
    pid=FXPQuantizedPID(); plant=ValvePlant()
    print("Self-Test"); print("-"*50)
    pid.reset()
    pid.step(50.0,30.0,100.0,0.0,100.0,-100.0,1.0,1000.0,0.0,0.1,True,0.0,True)
    out=pid.step(50.0,30.0,100.0,0.0,100.0,-100.0,1.0,1000.0,0.0,0.1,True,0.0,False)
    print(f"  P-only (Kc=1 err=20): {out:.4f}  {P if abs(out-20.0)<1.5 else F}")
    pid.reset()
    out=pid.step(100.0,0.0,100.0,0.0,100.0,-100.0,100.0,0.1,0.0,0.1,True,0.0,True)
    print(f"  Saturation->100: {out:.4f}  {P if abs(out-100.0)<0.01 else F}")
    pid.reset()
    out=pid.step(75.0,20.0,100.0,0.0,100.0,-100.0,1.0,1.0,0.0,0.1,False,42.5,False)
    print(f"  Manual 42.5: {out:.6f}  {P if abs(out-42.5)<FMT_PROCESS.lsb*2 else F}")
    pid.reset()
    for _ in range(50): pid.step(100.0,0.0,100.0,0.0,100.0,-100.0,1.0,0.5,0.0,0.1,True,0.0,False)
    out=pid.step(0.0,0.0,100.0,0.0,100.0,-100.0,1.0,0.5,0.0,0.1,True,0.0,True)
    print(f"  Reinit (SP=PV=0): {out:.4f}  {P if abs(out)<1.0 else F}")
    pid.reset(); pv=0.0; plant.reset()
    for _ in range(300):
        out=pid.step(75.0,pv,100.0,0.0,100.0,-100.0,5.0,0.1,0.0,0.1,True,0.0,False)
        pv=plant.step(out,0.1)
    print(f"  Closed-loop (Kc=5,Ti=0.1min) PV={pv:.3f}  {P if abs(pv-75.0)<3.75 else F}")
    print()


def generate_test_vectors(filename="pid_test_vectors.csv"):
    pid=FXPQuantizedPID(); plant=ValvePlant()
    SH,SL,OH,OL=100.0,0.0,100.0,-100.0
    KC,TI,DT=5.0,0.1,0.1
    rows=[]; cycle=0; pv=0.0

    def add(sp,manual=0.0,auto=True,reinit=False,alpha=0.0,beta=1.0,Kc_=KC,Ti_=TI,Td_=0.0,dt_=DT):
        nonlocal cycle,pv
        out=pid.step(sp,pv,SH,SL,OH,OL,Kc_,Ti_,Td_,dt_,auto,manual,reinit,alpha,beta)
        rows.append({"cycle":cycle,"setpoint":round(sp,6),"pv":round(pv,6),
            "Kc":Kc_,"Ti_min":Ti_,"Td_min":Td_,"dt_s":dt_,"auto_mode":int(auto),
            "manual_ctrl":round(manual,6),"reinitialize":int(reinit),
            "alpha":alpha,"beta":beta,"sp_hi":SH,"sp_lo":SL,"out_hi":OH,"out_lo":OL,
            "expected_output":round(out,6),"expected_bits":FMT_PROCESS.to_bits(out),
            "setpoint_bits":FMT_PROCESS.to_bits(sp),"pv_bits":FMT_PROCESS.to_bits(pv),
            "Kc_bits":FMT_GAIN.to_bits(Kc_),"dt_bits":FMT_GAIN.to_bits(dt_)})
        cycle+=1; return out

    add(75.0,reinit=True)
    for _ in range(200): out=add(75.0); pv=plant.step(out,DT)
    for _ in range(25):  add(75.0,manual=50.0,auto=False); pv=plant.step(50.0,DT)
    for _ in range(100): out=add(30.0); pv=plant.step(out,DT)
    add(75.0,reinit=True); pv=0.0; plant.reset()
    for _ in range(75):  out=add(75.0); pv=plant.step(out,DT)

    fields=["cycle","setpoint","pv","Kc","Ti_min","Td_min","dt_s","auto_mode","manual_ctrl",
            "reinitialize","alpha","beta","sp_hi","sp_lo","out_hi","out_lo",
            "expected_output","expected_bits","setpoint_bits","pv_bits","Kc_bits","dt_bits"]
    with open(filename,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(f"Generated {len(rows)} test vectors -> {filename}")
    return rows


if __name__=="__main__":
    validate_fxp_formats()
    run_self_test()
    vectors=generate_test_vectors("pid_test_vectors.csv")
    print(f"\nSample vectors (first 3 / last 3):")
    print(f"  {'Cycle':>5} {'SP':>7} {'PV':>7} {'Auto':>4} {'ExpOut':>9} {'ExpBits':>12}")
    for v in vectors[:3]+vectors[-3:]:
        print(f"  {v['cycle']:>5} {v['setpoint']:>7.2f} {v['pv']:>7.3f}  "
              f"  {v['auto_mode']:>2}  {v['expected_output']:>9.4f} {v['expected_bits']:>12d}")
