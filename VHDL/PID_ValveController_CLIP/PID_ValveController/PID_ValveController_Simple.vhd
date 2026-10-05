-- =============================================================================
-- PID_ValveController.vhd   v4.2
-- LabVIEW FPGA CLIP Node - Fixed-Point 2-DOF PID Controller
-- Target: Kintex-7 xc7k70tfbg676-1  |  Tool: Vivado 2021.1
-- Clock:  40 MHz  |  Pipeline: 5 stages  |  Latency: 5 cycles
-- =============================================================================
-- COMPILE-SAFETY RULES (v4.2 - learned from Synth 8-5809 failures):
--
--  R1  NO integer division (/) in synthesisable RTL. All PID coefficient
--      division is pre-computed on the RT host and passed as Ki_Coeff/Kd_Coeff.
--      Synth 8-5809 "Error generated from encrypted envelope" is triggered when
--      Vivado cannot elaborate a signal driven by unsupported constructs such as
--      VHDL integer division inside a TIMED LOOP CLIP context.
--
--  R2  No scientific-notation float literals in numeric_std calls (e.g. 1.0e-3).
--      Use only integer literals: to_signed(16777, 32), not to_signed(1.0e-3*2**24, 32).
--
--  R3  All ports are std_logic / std_logic_vector ONLY. Vivado cannot elaborate
--      vendor-neutral VHDL FXP types at entity boundaries.
--
--  R4  aReset is asynchronous active-high - matches NI Fabric CLIP convention.
--      Do NOT use SignalType>reset in the XML for Fabric CLIPs; declare as data.
--
--  R5  Only ONE clocked process. No signal assigned from multiple processes
--      (multi-driver = Synth 8-3236).
--
--  R6  All registers cleared in aReset branch. No 'others => X' unknowns.
--
--  R7  shift_right applied only after promoting operand to 64-bit signed.
--
--  R8  Entity name must exactly match the <Entity> XML tag (case-sensitive
--      on Linux compile servers). File name must match entity name.
--
--  R9  FormatVersion in XML must be present as first child of CLIPDeclaration
--      (required tag - see "A required XML tag is missing" error).
--
-- R10  ImplementationList <Path> filename must be relative to the XML file
--      location. Absolute Windows paths break on the NI Linux compile server.
--
-- =============================================================================
-- PRE-SCALED COEFFICIENT ARCHITECTURE (eliminates FPGA division):
--
--   RT host computes (C pseudo-code - see pid_rt_prescale.c):
--     Ki_Coeff = Kc * dt_s / max(Ti_min * 60, 1e-6)
--     Kd_Coeff = Kc * max(Td_min, 0) * 60 / max(dt_s, 0.001)
--     Ki_bits  = (int32_t)round(Ki_Coeff * pow(2, 24))  // FXP<+/-,32,8>
--     Kd_bits  = (int32_t)round(Kd_Coeff * pow(2, 24))  // FXP<+/-,32,8>
--
--   The CLIP only multiplies - never divides - eliminating the synthesis error.
--
-- =============================================================================
-- NI FXP FORMAT MAP:
--   FXP<+/-,32,16>  FWL=16  range +/-32767   LSB=1.526e-5  process/output vals
--   FXP<+/-,32,8>   FWL=24  range +/-127     LSB=5.96e-8   gains/coefficients
--   FXP<+/-,32,2>   FWL=30  range +/-1.999   LSB=9.31e-10  alpha/beta/gamma
-- =============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity PID_ValveController is
    port (
        Clk                : in  std_logic;
        aReset             : in  std_logic;
        Setpoint           : in  std_logic_vector(31 downto 0);
        ProcessVariable    : in  std_logic_vector(31 downto 0);
        SetpointHigh       : in  std_logic_vector(31 downto 0);
        SetpointLow        : in  std_logic_vector(31 downto 0);
        OutputHigh         : in  std_logic_vector(31 downto 0);
        OutputLow          : in  std_logic_vector(31 downto 0);
        ProportionalGainKc : in  std_logic_vector(31 downto 0);
        Ki_Coeff           : in  std_logic_vector(31 downto 0);
        Kd_Coeff           : in  std_logic_vector(31 downto 0);
        DtS                : in  std_logic_vector(31 downto 0);
        AutoMode           : in  std_logic;
        ManualControl      : in  std_logic_vector(31 downto 0);
        Reinitialize       : in  std_logic;
        Alpha              : in  std_logic_vector(31 downto 0);
        Beta               : in  std_logic_vector(31 downto 0);
        Gamma              : in  std_logic_vector(31 downto 0);
        Linearity          : in  std_logic_vector(31 downto 0);
        Output             : out std_logic_vector(31 downto 0);
        DtOut              : out std_logic_vector(31 downto 0)
    );
end entity PID_ValveController;

architecture RTL of PID_ValveController is

    constant FWL_Q1616  : integer := 16;
    constant FWL_Q824   : integer := 24;
    constant FWL_Q230   : integer := 30;
    constant ONE_Q1616  : signed(31 downto 0) := to_signed(65536, 32);
    constant DT_MIN_Q824: signed(31 downto 0) := to_signed(16777, 32);

    function sat32(v : signed(63 downto 0)) return signed is
    begin
        if    v > to_signed( 2147483647, 64) then return to_signed( 2147483647, 32);
        elsif v < to_signed(-2147483648, 64) then return to_signed(-2147483648, 32);
        else                                      return v(31 downto 0);
        end if;
    end function;

    function mul_q824_q1616(a,b: signed(31 downto 0)) return signed is
        variable p: signed(63 downto 0);
    begin p := a*b; p := shift_right(p, FWL_Q824); return sat32(p); end function;

    function mul_q230_q1616(a,b: signed(31 downto 0)) return signed is
        variable p: signed(63 downto 0);
    begin p := a*b; p := shift_right(p, FWL_Q230); return sat32(p); end function;

    function mul_q1616_q1616(a,b: signed(31 downto 0)) return signed is
        variable p: signed(63 downto 0);
    begin p := a*b; p := shift_right(p, FWL_Q1616); return sat32(p); end function;

    -- State registers
    signal i_accum  : signed(31 downto 0) := (others => '0');
    signal pv_prev  : signed(31 downto 0) := (others => '0');
    signal d_state  : signed(31 downto 0) := (others => '0');
    signal dt_reg   : signed(31 downto 0) := (others => '0');
    signal out_reg  : signed(31 downto 0) := (others => '0');

    -- Stage 1 pipeline regs
    signal s1_ep,s1_ei,s1_pv,s1_kc,s1_ki,s1_kd  : signed(31 downto 0) := (others => '0');
    signal s1_outhi,s1_outlo,s1_man,s1_alpha      : signed(31 downto 0) := (others => '0');
    signal s1_auto,s1_reinit                       : std_logic            := '0';

    -- Stage 2
    signal s2_P,s2_ei,s2_pv,s2_ki,s2_kd          : signed(31 downto 0) := (others => '0');
    signal s2_outhi,s2_outlo,s2_man,s2_alpha       : signed(31 downto 0) := (others => '0');
    signal s2_auto,s2_reinit                        : std_logic            := '0';

    -- Stage 3
    signal s3_P,s3_dI,s3_Dbase                    : signed(31 downto 0) := (others => '0');
    signal s3_outhi,s3_outlo,s3_man,s3_alpha       : signed(31 downto 0) := (others => '0');
    signal s3_auto,s3_reinit                        : std_logic            := '0';

    -- Stage 4
    signal s4_u_raw,s4_dI,s4_outhi,s4_outlo,s4_man: signed(31 downto 0) := (others => '0');
    signal s4_auto,s4_reinit                        : std_logic            := '0';

begin
    Output <= std_logic_vector(out_reg);
    DtOut  <= std_logic_vector(dt_reg);

    pid_pipeline: process(Clk, aReset)
        variable v_dt    : signed(31 downto 0);
        variable v_sp    : signed(31 downto 0);
        variable v_spb   : signed(31 downto 0);
        variable v_ep    : signed(31 downto 0);
        variable v_ei    : signed(31 downto 0);
        variable v_P     : signed(31 downto 0);
        variable v_dI    : signed(31 downto 0);
        variable v_dpv   : signed(31 downto 0);
        variable v_Db    : signed(31 downto 0);
        variable v_alq16 : signed(31 downto 0);
        variable v_Df    : signed(31 downto 0);
        variable v_sum64 : signed(63 downto 0);
        variable v_uraw  : signed(31 downto 0);
        variable v_usat  : signed(31 downto 0);
        variable v_out   : signed(31 downto 0);
        variable v_shi   : boolean;
        variable v_slo   : boolean;
        variable v_inew  : signed(31 downto 0);
    begin
        if aReset = '1' then
            s1_ep<=(others=>'0'); s1_ei<=(others=>'0'); s1_pv<=(others=>'0');
            s1_kc<=(others=>'0'); s1_ki<=(others=>'0'); s1_kd<=(others=>'0');
            s1_outhi<=(others=>'0'); s1_outlo<=(others=>'0');
            s1_man<=(others=>'0'); s1_alpha<=(others=>'0');
            s1_auto<='0'; s1_reinit<='0';
            s2_P<=(others=>'0'); s2_ei<=(others=>'0'); s2_pv<=(others=>'0');
            s2_ki<=(others=>'0'); s2_kd<=(others=>'0');
            s2_outhi<=(others=>'0'); s2_outlo<=(others=>'0');
            s2_man<=(others=>'0'); s2_alpha<=(others=>'0');
            s2_auto<='0'; s2_reinit<='0';
            s3_P<=(others=>'0'); s3_dI<=(others=>'0'); s3_Dbase<=(others=>'0');
            s3_outhi<=(others=>'0'); s3_outlo<=(others=>'0');
            s3_man<=(others=>'0'); s3_alpha<=(others=>'0');
            s3_auto<='0'; s3_reinit<='0';
            s4_u_raw<=(others=>'0'); s4_dI<=(others=>'0');
            s4_outhi<=(others=>'0'); s4_outlo<=(others=>'0');
            s4_man<=(others=>'0'); s4_auto<='0'; s4_reinit<='0';
            i_accum<=(others=>'0'); pv_prev<=(others=>'0');
            d_state<=(others=>'0'); dt_reg<=DT_MIN_Q824; out_reg<=(others=>'0');

        elsif rising_edge(Clk) then
            -- Stage 1
            if signed(DtS) < DT_MIN_Q824 then v_dt := DT_MIN_Q824;
            else v_dt := signed(DtS); end if;
            dt_reg <= v_dt;
            if    signed(Setpoint) > signed(SetpointHigh) then v_sp := signed(SetpointHigh);
            elsif signed(Setpoint) < signed(SetpointLow)  then v_sp := signed(SetpointLow);
            else                                               v_sp := signed(Setpoint);
            end if;
            if Reinitialize = '1' then
                i_accum <= (others=>'0');
                pv_prev <= signed(ProcessVariable);
                d_state <= (others=>'0');
            end if;
            v_spb := mul_q230_q1616(signed(Beta), v_sp);
            v_ep  := v_spb - signed(ProcessVariable);
            v_ei  := v_sp  - signed(ProcessVariable);
            s1_ep<=v_ep; s1_ei<=v_ei; s1_pv<=signed(ProcessVariable);
            s1_kc<=signed(ProportionalGainKc); s1_ki<=signed(Ki_Coeff);
            s1_kd<=signed(Kd_Coeff);
            s1_outhi<=signed(OutputHigh); s1_outlo<=signed(OutputLow);
            s1_auto<=AutoMode; s1_man<=signed(ManualControl);
            s1_alpha<=signed(Alpha); s1_reinit<=Reinitialize;

            -- Stage 2: P = Kc * ep
            v_P := mul_q824_q1616(s1_kc, s1_ep);
            s2_P<=v_P; s2_ei<=s1_ei; s2_pv<=s1_pv;
            s2_ki<=s1_ki; s2_kd<=s1_kd;
            s2_outhi<=s1_outhi; s2_outlo<=s1_outlo;
            s2_auto<=s1_auto; s2_man<=s1_man;
            s2_alpha<=s1_alpha; s2_reinit<=s1_reinit;

            -- Stage 3: dI = Ki*ei,  Dbase = -Kd*(PV-PV_prev)
            v_dI  := mul_q824_q1616(s2_ki, s2_ei);
            v_dpv := s2_pv - pv_prev;
            v_Db  := -mul_q824_q1616(s2_kd, v_dpv);
            if s2_reinit = '0' then pv_prev <= s2_pv; end if;
            s3_P<=s2_P; s3_dI<=v_dI; s3_Dbase<=v_Db;
            s3_outhi<=s2_outhi; s3_outlo<=s2_outlo;
            s3_auto<=s2_auto; s3_man<=s2_man;
            s3_alpha<=s2_alpha; s3_reinit<=s2_reinit;

            -- Stage 4: alpha filter + sum
            v_alq16 := shift_right(s3_alpha, 14);
            v_Df    := mul_q1616_q1616(v_alq16, d_state) +
                       mul_q1616_q1616(ONE_Q1616 - v_alq16, s3_Dbase);
            if s3_reinit = '0' then d_state <= v_Df;
            else                    d_state <= (others=>'0'); end if;
            v_sum64 := resize(s3_P,64) + resize(i_accum,64) +
                       resize(s3_dI,64) + resize(v_Df,64);
            v_uraw  := sat32(v_sum64);
            s4_u_raw<=v_uraw; s4_dI<=s3_dI;
            s4_outhi<=s3_outhi; s4_outlo<=s3_outlo;
            s4_auto<=s3_auto; s4_man<=s3_man; s4_reinit<=s3_reinit;

            -- Stage 5: saturate, anti-windup, mux
            if s4_reinit = '1' then
                i_accum <= (others=>'0');
                v_out := s4_man;
                if v_out > s4_outhi then v_out := s4_outhi; end if;
                if v_out < s4_outlo then v_out := s4_outlo; end if;
            elsif s4_auto = '0' then
                v_out := s4_man;
                if v_out > s4_outhi then v_out := s4_outhi; end if;
                if v_out < s4_outlo then v_out := s4_outlo; end if;
                i_accum <= v_out - s3_P - d_state;
            else
                v_shi := (s4_u_raw >= s4_outhi);
                v_slo := (s4_u_raw <= s4_outlo);
                if    v_shi then v_usat := s4_outhi;
                elsif v_slo then v_usat := s4_outlo;
                else             v_usat := s4_u_raw; end if;
                v_out := v_usat;
                v_inew := i_accum + s4_dI;
                if (not v_shi and not v_slo)
                   or (v_shi and s4_dI < to_signed(0,32))
                   or (v_slo and s4_dI > to_signed(0,32))
                then i_accum <= v_inew; end if;
            end if;
            out_reg <= v_out;
        end if;
    end process pid_pipeline;

end architecture RTL;
