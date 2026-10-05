-- ============================================================================
-- PID_ValveController.vhd
-- LabVIEW FPGA CLIP Node  —  Fixed-Point 2-DOF PID  (Valve Flow Control)
--
-- NI FXP format:  FXP<+/-,W,IWL>
--   W   = total word bits (incl. sign)
--   IWL = integer word length (incl. sign bit)
--   FWL = W - IWL  (fractional bits);  LSB = 2^(-FWL)
--
-- Port formats:
--   setpoint, PV, output limits, Ti(min), Td(min) : FXP<+/-,32,16>
--   proportional gain (Kc), dt(s), dt out(s)      : FXP<+/-,32,8>
--   alpha, beta, gamma, linearity                  : FXP<+/-,32,2>
--   auto?(T), reinitialize?(F)                     : std_logic (boolean)
--
-- Pipeline: 5 stages  |  Latency: 5 clk  |  40 MHz Kintex-7 target
-- Anti-windup, bumpless auto/manual transfer, 2-DOF (beta setpoint weighting)
--
-- DIVISION NOTE:
--   Stage 3 uses integer '/' for I/D coefficient scaling.
--   GHDL simulates correctly. For production LabVIEW FPGA synthesis either
--   pre-compute Ki/Kd ratios on the RT side or accept LabVIEW FPGA's
--   automatic divider pipelining to meet timing.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity PID_ValveController is
    Port (
        Clk                  : in  std_logic;
        aReset               : in  std_logic;          -- active-high async reset
        -- Process values  [FXP<+/-,32,16>]
        Setpoint             : in  std_logic_vector(31 downto 0);
        ProcessVariable      : in  std_logic_vector(31 downto 0);
        SetpointHigh         : in  std_logic_vector(31 downto 0);
        SetpointLow          : in  std_logic_vector(31 downto 0);
        OutputHigh           : in  std_logic_vector(31 downto 0);
        OutputLow            : in  std_logic_vector(31 downto 0);
        -- Gains  [Kc: FXP<+/-,32,8>]  [Ti,Td: FXP<+/-,32,16>]
        ProportionalGainKc   : in  std_logic_vector(31 downto 0);
        IntegralTimeTiMin    : in  std_logic_vector(31 downto 0);
        DerivativeTimeTdMin  : in  std_logic_vector(31 downto 0);
        -- Sample period  [FXP<+/-,32,8>]
        DtS                  : in  std_logic_vector(31 downto 0);
        -- Mode
        AutoMode             : in  std_logic;
        ManualControl        : in  std_logic_vector(31 downto 0);
        Reinitialize         : in  std_logic;
        -- 2-DOF parameters  [FXP<+/-,32,2>]
        Alpha                : in  std_logic_vector(31 downto 0);
        Beta                 : in  std_logic_vector(31 downto 0);
        Gamma                : in  std_logic_vector(31 downto 0);
        Linearity            : in  std_logic_vector(31 downto 0);
        -- Outputs
        Output               : out std_logic_vector(31 downto 0);
        DtOut                : out std_logic_vector(31 downto 0)
    );
end entity PID_ValveController;

architecture RTL of PID_ValveController is
    constant FWL_Q1616    : integer := 16;
    constant FWL_Q824     : integer := 24;
    constant FWL_Q230     : integer := 30;
    constant DT_MIN_Q824  : signed(31 downto 0) := to_signed(16777,32);   -- 0.001s
    constant TI_MIN_Q1616 : signed(31 downto 0) := to_signed(65,32);      -- 0.001min
    constant ONE_Q1616    : signed(31 downto 0) := to_signed(65536,32);   -- 1.0

    -- Stage 1 registers
    signal s1_ep,s1_ei,s1_pv,s1_kc,s1_ti,s1_td,s1_dt       : signed(31 downto 0):=(others=>'0');
    signal s1_outhi,s1_outlo,s1_man,s1_alpha                 : signed(31 downto 0):=(others=>'0');
    signal s1_auto,s1_reinit                                  : std_logic:='0';
    -- Stage 2 registers
    signal s2_P,s2_ei,s2_pv,s2_kc,s2_ti,s2_td,s2_dt         : signed(31 downto 0):=(others=>'0');
    signal s2_outhi,s2_outlo,s2_man,s2_alpha                  : signed(31 downto 0):=(others=>'0');
    signal s2_auto,s2_reinit                                   : std_logic:='0';
    -- Stage 3 registers
    signal s3_P,s3_dI,s3_Dbase                               : signed(31 downto 0):=(others=>'0');
    signal s3_outhi,s3_outlo,s3_man,s3_alpha                  : signed(31 downto 0):=(others=>'0');
    signal s3_auto,s3_reinit                                   : std_logic:='0';
    -- Stage 4 registers
    signal s4_u_raw,s4_dI,s4_outhi,s4_outlo,s4_man           : signed(31 downto 0):=(others=>'0');
    signal s4_auto,s4_reinit                                   : std_logic:='0';
    -- Persistent state
    signal i_accum,pv_prev,d_state,dt_reg                     : signed(31 downto 0):=(others=>'0');

    function sat32(v:signed(63 downto 0)) return signed is begin
        if    v> to_signed( 2147483647,64) then return  to_signed( 2147483647,32);
        elsif v<-to_signed( 2147483648,64) then return -to_signed( 2147483648,32);
        else return v(31 downto 0); end if;
    end;
    function mul_q824_q1616(a,b:signed(31 downto 0)) return signed is
        variable p:signed(63 downto 0); begin p:=a*b; return sat32(shift_right(p,24)); end;
    function mul_q230_q1616(a,b:signed(31 downto 0)) return signed is
        variable p:signed(63 downto 0); begin p:=a*b; return sat32(shift_right(p,30)); end;
    function mul_q1616_q1616(a,b:signed(31 downto 0)) return signed is
        variable p:signed(63 downto 0); begin p:=a*b; return sat32(shift_right(p,16)); end;

begin
    DtOut <= std_logic_vector(dt_reg);

    pid_pipeline : process(Clk,aReset)
        variable v_sp_lim,v_dt_safe,v_ti_safe,v_ep,v_ei,v_sp_beta : signed(31 downto 0);
        variable v_ti_sec64,v_td_sec64,v_dI_num,v_dI_den           : signed(63 downto 0);
        variable v_Kc_ei,v_dI,v_pv_delta,v_Kc_pv,v_Dbase          : signed(31 downto 0);
        variable v_D_num,v_D_den                                    : signed(63 downto 0);
        variable v_alpha16,v_one_m_a,v_D_filt,v_u_raw              : signed(31 downto 0);
        variable v_u_sum64                                          : signed(63 downto 0);
        variable v_output,v_u_sat,v_i_new                          : signed(31 downto 0);
        variable v_sat_hi,v_sat_lo                                  : boolean;
    begin
    if aReset='1' then
        s1_ep<=(others=>'0');s1_ei<=(others=>'0');s1_pv<=(others=>'0');
        s1_kc<=(others=>'0');s1_ti<=(others=>'0');s1_td<=(others=>'0');
        s1_dt<=(others=>'0');s1_outhi<=(others=>'0');s1_outlo<=(others=>'0');
        s1_man<=(others=>'0');s1_alpha<=(others=>'0');s1_auto<='0';s1_reinit<='0';
        s2_P<=(others=>'0');s2_ei<=(others=>'0');s2_pv<=(others=>'0');
        s2_kc<=(others=>'0');s2_ti<=(others=>'0');s2_td<=(others=>'0');
        s2_dt<=(others=>'0');s2_outhi<=(others=>'0');s2_outlo<=(others=>'0');
        s2_man<=(others=>'0');s2_alpha<=(others=>'0');s2_auto<='0';s2_reinit<='0';
        s3_P<=(others=>'0');s3_dI<=(others=>'0');s3_Dbase<=(others=>'0');
        s3_outhi<=(others=>'0');s3_outlo<=(others=>'0');s3_man<=(others=>'0');
        s3_alpha<=(others=>'0');s3_auto<='0';s3_reinit<='0';
        s4_u_raw<=(others=>'0');s4_dI<=(others=>'0');s4_outhi<=(others=>'0');
        s4_outlo<=(others=>'0');s4_man<=(others=>'0');s4_auto<='0';s4_reinit<='0';
        i_accum<=(others=>'0');pv_prev<=(others=>'0');
        d_state<=(others=>'0');dt_reg<=(others=>'0');Output<=(others=>'0');
    elsif rising_edge(Clk) then

        -- === STAGE 1: Input conditioning and error computation ==================
        if signed(DtS)<DT_MIN_Q824 then v_dt_safe:=DT_MIN_Q824;
        else v_dt_safe:=signed(DtS); end if;
        dt_reg<=v_dt_safe;

        if signed(IntegralTimeTiMin)<TI_MIN_Q1616 then v_ti_safe:=TI_MIN_Q1616;
        else v_ti_safe:=signed(IntegralTimeTiMin); end if;

        if    signed(Setpoint)>signed(SetpointHigh) then v_sp_lim:=signed(SetpointHigh);
        elsif signed(Setpoint)<signed(SetpointLow)  then v_sp_lim:=signed(SetpointLow);
        else  v_sp_lim:=signed(Setpoint); end if;

        if Reinitialize='1' then
            i_accum<=(others=>'0');pv_prev<=signed(ProcessVariable);d_state<=(others=>'0');
        end if;

        v_sp_beta:=mul_q230_q1616(signed(Beta),v_sp_lim);
        v_ep:=v_sp_beta-signed(ProcessVariable);
        v_ei:=v_sp_lim -signed(ProcessVariable);

        s1_ep<=v_ep;s1_ei<=v_ei;s1_pv<=signed(ProcessVariable);
        s1_kc<=signed(ProportionalGainKc);s1_ti<=v_ti_safe;
        s1_td<=signed(DerivativeTimeTdMin);s1_dt<=v_dt_safe;
        s1_outhi<=signed(OutputHigh);s1_outlo<=signed(OutputLow);
        s1_auto<=AutoMode;s1_man<=signed(ManualControl);
        s1_alpha<=signed(Alpha);s1_reinit<=Reinitialize;

        -- === STAGE 2: P-term  P = Kc * ep  (Q824 x Q1616 >> 24 -> Q1616) ======
        s2_P<=mul_q824_q1616(s1_kc,s1_ep);
        s2_ei<=s1_ei;s2_pv<=s1_pv;s2_kc<=s1_kc;s2_ti<=s1_ti;s2_td<=s1_td;
        s2_dt<=s1_dt;s2_outhi<=s1_outhi;s2_outlo<=s1_outlo;
        s2_auto<=s1_auto;s2_man<=s1_man;s2_alpha<=s1_alpha;s2_reinit<=s1_reinit;

        -- === STAGE 3: I increment and raw D =====================================
        -- Ti_sec (Q1616*60):  Ti_bits * 60
        v_ti_sec64:=resize(s2_ti,64)*to_signed(60,64);
        if s2_td>to_signed(0,32) then
            v_td_sec64:=resize(s2_td,64)*to_signed(60,64);
        else v_td_sec64:=(others=>'0'); end if;

        v_Kc_ei:=mul_q824_q1616(s2_kc,s2_ei);
        -- dI = (Kc_ei * dt) / (Ti_sec * 256)   [256 = 2^(FWL_Q824-FWL_Q1616)]
        v_dI_num:=resize(v_Kc_ei,64)*resize(s2_dt,64);
        v_dI_den:=v_ti_sec64*to_signed(256,64);
        if v_dI_den/=to_signed(0,64) then v_dI:=sat32(v_dI_num/v_dI_den);
        else v_dI:=(others=>'0'); end if;

        -- D_raw = -(Kc * pv_delta * Td_sec) / (dt * 2^16)
        v_pv_delta:=s2_pv-pv_prev;
        if v_td_sec64/=to_signed(0,64) and s2_dt>to_signed(0,32) then
            v_Kc_pv:=mul_q824_q1616(s2_kc,v_pv_delta);
            v_D_num:=-(resize(v_Kc_pv,64)*resize(v_td_sec64(31 downto 0),64));
            v_D_den:=resize(s2_dt,64)*to_signed(65536,64);
            if v_D_den/=to_signed(0,64) then v_Dbase:=sat32(v_D_num/v_D_den);
            else v_Dbase:=(others=>'0'); end if;
        else v_Dbase:=(others=>'0'); end if;

        if s2_reinit='0' then pv_prev<=s2_pv; end if;

        s3_P<=s2_P;s3_dI<=v_dI;s3_Dbase<=v_Dbase;
        s3_outhi<=s2_outhi;s3_outlo<=s2_outlo;s3_auto<=s2_auto;
        s3_man<=s2_man;s3_alpha<=s2_alpha;s3_reinit<=s2_reinit;

        -- === STAGE 4: Derivative alpha-filter and sum u = P + I + D =============
        -- alpha Q230 -> Q1616: shift right (30-16)=14
        v_alpha16:=shift_right(s3_alpha,14)(31 downto 0);
        v_one_m_a:=ONE_Q1616-v_alpha16;
        v_D_filt:=mul_q1616_q1616(v_alpha16,d_state)+mul_q1616_q1616(v_one_m_a,s3_Dbase);
        if s3_reinit='0' then d_state<=v_D_filt; else d_state<=(others=>'0'); end if;

        v_u_sum64:=resize(s3_P,64)+resize(i_accum,64)+resize(s3_dI,64)+resize(v_D_filt,64);
        v_u_raw:=sat32(v_u_sum64);

        s4_u_raw<=v_u_raw;s4_dI<=s3_dI;
        s4_outhi<=s3_outhi;s4_outlo<=s3_outlo;
        s4_auto<=s3_auto;s4_man<=s3_man;s4_reinit<=s3_reinit;

        -- === STAGE 5: Saturation, anti-windup, auto/manual output mux ===========
        if s4_reinit='1' then
            i_accum<=(others=>'0');
            v_output:=s4_man;
            if v_output>s4_outhi then v_output:=s4_outhi; end if;
            if v_output<s4_outlo then v_output:=s4_outlo; end if;
        elsif s4_auto='0' then
            v_output:=s4_man;
            if v_output>s4_outhi then v_output:=s4_outhi; end if;
            if v_output<s4_outlo then v_output:=s4_outlo; end if;
            i_accum<=v_output-s3_P-d_state;     -- bumpless transfer preload
        else
            v_sat_hi:=(s4_u_raw>=s4_outhi); v_sat_lo:=(s4_u_raw<=s4_outlo);
            if    v_sat_hi then v_u_sat:=s4_outhi;
            elsif v_sat_lo then v_u_sat:=s4_outlo;
            else               v_u_sat:=s4_u_raw; end if;
            v_output:=v_u_sat;
            v_i_new:=i_accum+s4_dI;
            if (not v_sat_hi and not v_sat_lo) or
               (v_sat_hi and s4_dI<to_signed(0,32)) or
               (v_sat_lo and s4_dI>to_signed(0,32)) then
                i_accum<=v_i_new;
            end if;
        end if;
        Output<=std_logic_vector(v_output);
    end if;
    end process pid_pipeline;
end architecture RTL;
