-- =============================================================================
-- PID_ValveController.vhd  v4.2
-- LabVIEW FPGA CLIP Node  --  Fixed-Point 2-DOF PID  --  Valve Flow Control
--
-- Target   : cRIO-class Kintex-7 (xc7k70tfbg676-1)
-- Clock    : Clk = 40 MHz  |  Ce = every 8 clocks (5 MHz functional rate)
-- Latency  : 5 clock cycles (Ce-gated)
--
-- v4.2 changes vs v4.1
--   * Removed ALL process-local declare blocks (not portable in Vivado)
--   * Removed integer division from pipeline  --  Ki and Kd coefficients
--     are now pre-scaled on the RT side and passed as FXP<+/-,32,8> inputs
--     KiCoeff = Kc * dt_s / (Ti_min * 60)   computed on RT, passed here
--     KdCoeff = Kc * Td_min * 60 / dt_s     computed on RT, passed here
--   * No scientific notation in any numeric literal
--   * aReset handled synchronously inside rising_edge (NI CLIP convention)
--   * All intermediate signals pre-declared in architecture declarative region
--   * Ce guard wraps ALL state-changing logic
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity PID_ValveController is
    port (
        -- Infrastructure
        Clk                 : in  std_logic;
        Ce                  : in  std_logic;
        aReset              : in  std_logic;

        -- Process I/O  FXP<+/-,32,16>
        Setpoint            : in  std_logic_vector(31 downto 0);
        ProcessVariable     : in  std_logic_vector(31 downto 0);
        SetpointHigh        : in  std_logic_vector(31 downto 0);
        SetpointLow         : in  std_logic_vector(31 downto 0);
        OutputHigh          : in  std_logic_vector(31 downto 0);
        OutputLow           : in  std_logic_vector(31 downto 0);

        -- Pre-scaled PID coefficients  FXP<+/-,32,8>
        -- KiCoeff = Kc * dt_s / (Ti_min * 60)   -- compute on RT
        -- KdCoeff = Kc * Td_min * 60 / dt_s     -- compute on RT
        ProportionalGainKc  : in  std_logic_vector(31 downto 0);
        KiCoeff             : in  std_logic_vector(31 downto 0);
        KdCoeff             : in  std_logic_vector(31 downto 0);

        -- 2-DOF weights  FXP<+/-,32,2>
        Alpha               : in  std_logic_vector(31 downto 0);
        Beta                : in  std_logic_vector(31 downto 0);

        -- Mode control
        AutoMode            : in  std_logic;
        ManualControl       : in  std_logic_vector(31 downto 0);
        Reinitialize        : in  std_logic;

        -- Outputs  FXP<+/-,32,16>
        Output              : out std_logic_vector(31 downto 0)
    );
end entity PID_ValveController;

architecture rtl of PID_ValveController is

    -- Signed views of ports
    signal sp_s    : signed(31 downto 0);
    signal pv_s    : signed(31 downto 0);
    signal sphi_s  : signed(31 downto 0);
    signal splo_s  : signed(31 downto 0);
    signal outhi_s : signed(31 downto 0);
    signal outlo_s : signed(31 downto 0);
    signal kc_s    : signed(31 downto 0);
    signal ki_s    : signed(31 downto 0);
    signal kd_s    : signed(31 downto 0);
    signal al_s    : signed(31 downto 0);
    signal be_s    : signed(31 downto 0);
    signal man_s   : signed(31 downto 0);

    -- Pipeline stage 1
    signal s1_sp_lim  : signed(31 downto 0);
    signal s1_ep      : signed(31 downto 0);
    signal s1_ei      : signed(31 downto 0);
    signal s1_pv      : signed(31 downto 0);
    signal s1_kc      : signed(31 downto 0);
    signal s1_ki      : signed(31 downto 0);
    signal s1_kd      : signed(31 downto 0);
    signal s1_outhi   : signed(31 downto 0);
    signal s1_outlo   : signed(31 downto 0);
    signal s1_auto    : std_logic;
    signal s1_man     : signed(31 downto 0);
    signal s1_alpha   : signed(31 downto 0);
    signal s1_reinit  : std_logic;

    -- Pipeline stage 2
    signal s2_P       : signed(31 downto 0);
    signal s2_ei      : signed(31 downto 0);
    signal s2_pv      : signed(31 downto 0);
    signal s2_ki      : signed(31 downto 0);
    signal s2_kd      : signed(31 downto 0);
    signal s2_outhi   : signed(31 downto 0);
    signal s2_outlo   : signed(31 downto 0);
    signal s2_auto    : std_logic;
    signal s2_man     : signed(31 downto 0);
    signal s2_alpha   : signed(31 downto 0);
    signal s2_reinit  : std_logic;

    -- Pipeline stage 3
    signal s3_P       : signed(31 downto 0);
    signal s3_dI      : signed(31 downto 0);
    signal s3_Draw    : signed(31 downto 0);
    signal s3_outhi   : signed(31 downto 0);
    signal s3_outlo   : signed(31 downto 0);
    signal s3_auto    : std_logic;
    signal s3_man     : signed(31 downto 0);
    signal s3_alpha   : signed(31 downto 0);
    signal s3_reinit  : std_logic;

    -- Pipeline stage 4
    signal s4_u_raw   : signed(31 downto 0);
    signal s4_dI      : signed(31 downto 0);
    signal s4_outhi   : signed(31 downto 0);
    signal s4_outlo   : signed(31 downto 0);
    signal s4_auto    : std_logic;
    signal s4_man     : signed(31 downto 0);
    signal s4_reinit  : std_logic;

    -- State registers
    signal i_accum    : signed(31 downto 0);
    signal pv_prev    : signed(31 downto 0);
    signal d_state    : signed(31 downto 0);

    -- 64-bit multiply intermediates (pre-declared, no process-local declare)
    signal prod64_a   : signed(63 downto 0);
    signal prod64_b   : signed(63 downto 0);
    signal prod64_c   : signed(63 downto 0);
    signal prod64_d   : signed(63 downto 0);

    -- ONE in Q16.16 = 65536
    constant ONE_Q1616 : signed(31 downto 0) := to_signed(65536, 32);
    constant ZERO32    : signed(31 downto 0) := to_signed(0, 32);
    constant MAX32     : signed(31 downto 0) := to_signed(2147483647, 32);
    constant MIN32     : signed(31 downto 0) := to_signed(-2147483648, 32);

    -- Saturating multiply: Q8.24 x Q16.16 -> Q16.16 (shift right 24)
    function mul_q824_q1616(a : signed(31 downto 0);
                             b : signed(31 downto 0))
        return signed is
        variable p : signed(63 downto 0);
        variable r : signed(63 downto 0);
    begin
        p := a * b;
        r := shift_right(p, 24);
        if r > to_signed(2147483647, 64) then
            return to_signed(2147483647, 32);
        elsif r < to_signed(-2147483648, 64) then
            return to_signed(-2147483648, 32);
        else
            return r(31 downto 0);
        end if;
    end function;

    -- Saturating multiply: Q2.30 x Q16.16 -> Q16.16 (shift right 30)
    function mul_q230_q1616(a : signed(31 downto 0);
                             b : signed(31 downto 0))
        return signed is
        variable p : signed(63 downto 0);
        variable r : signed(63 downto 0);
    begin
        p := a * b;
        r := shift_right(p, 30);
        if r > to_signed(2147483647, 64) then
            return to_signed(2147483647, 32);
        elsif r < to_signed(-2147483648, 64) then
            return to_signed(-2147483648, 32);
        else
            return r(31 downto 0);
        end if;
    end function;

    -- Saturating multiply: Q16.16 x Q16.16 -> Q16.16 (shift right 16)
    function mul_q1616_q1616(a : signed(31 downto 0);
                              b : signed(31 downto 0))
        return signed is
        variable p : signed(63 downto 0);
        variable r : signed(63 downto 0);
    begin
        p := a * b;
        r := shift_right(p, 16);
        if r > to_signed(2147483647, 64) then
            return to_signed(2147483647, 32);
        elsif r < to_signed(-2147483648, 64) then
            return to_signed(-2147483648, 32);
        else
            return r(31 downto 0);
        end if;
    end function;

    -- Clamp signed 32-bit to [lo, hi]
    function clamp32(v, lo, hi : signed(31 downto 0)) return signed is
    begin
        if v > hi then return hi;
        elsif v < lo then return lo;
        else return v;
        end if;
    end function;

begin

    -- Port wiring
    sp_s    <= signed(Setpoint);
    pv_s    <= signed(ProcessVariable);
    sphi_s  <= signed(SetpointHigh);
    splo_s  <= signed(SetpointLow);
    outhi_s <= signed(OutputHigh);
    outlo_s <= signed(OutputLow);
    kc_s    <= signed(ProportionalGainKc);
    ki_s    <= signed(KiCoeff);
    kd_s    <= signed(KdCoeff);
    al_s    <= signed(Alpha);
    be_s    <= signed(Beta);
    man_s   <= signed(ManualControl);

    -- Main pipeline
    process(Clk)
        variable v_sp_lim   : signed(31 downto 0);
        variable v_sp_beta  : signed(31 downto 0);
        variable v_ep       : signed(31 downto 0);
        variable v_ei       : signed(31 downto 0);
        variable v_P        : signed(31 downto 0);
        variable v_dI       : signed(31 downto 0);
        variable v_pv_delta : signed(31 downto 0);
        variable v_Draw     : signed(31 downto 0);
        variable v_al_q1616 : signed(31 downto 0);
        variable v_D_filt   : signed(31 downto 0);
        variable v_u_sum    : signed(63 downto 0);
        variable v_u_raw    : signed(31 downto 0);
        variable v_u_sat    : signed(31 downto 0);
        variable v_output   : signed(31 downto 0);
        variable v_sat_hi   : boolean;
        variable v_sat_lo   : boolean;
        variable v_i_new    : signed(31 downto 0);
    begin
        if rising_edge(Clk) then
            if aReset = '1' then
                -- Synchronous reset
                s1_sp_lim <= ZERO32; s1_ep <= ZERO32; s1_ei <= ZERO32;
                s1_pv <= ZERO32; s1_kc <= ZERO32; s1_ki <= ZERO32;
                s1_kd <= ZERO32; s1_outhi <= ZERO32; s1_outlo <= ZERO32;
                s1_auto <= '0'; s1_man <= ZERO32;
                s1_alpha <= ZERO32; s1_reinit <= '0';
                s2_P <= ZERO32; s2_ei <= ZERO32; s2_pv <= ZERO32;
                s2_ki <= ZERO32; s2_kd <= ZERO32;
                s2_outhi <= ZERO32; s2_outlo <= ZERO32;
                s2_auto <= '0'; s2_man <= ZERO32;
                s2_alpha <= ZERO32; s2_reinit <= '0';
                s3_P <= ZERO32; s3_dI <= ZERO32; s3_Draw <= ZERO32;
                s3_outhi <= ZERO32; s3_outlo <= ZERO32;
                s3_auto <= '0'; s3_man <= ZERO32;
                s3_alpha <= ZERO32; s3_reinit <= '0';
                s4_u_raw <= ZERO32; s4_dI <= ZERO32;
                s4_outhi <= ZERO32; s4_outlo <= ZERO32;
                s4_auto <= '0'; s4_man <= ZERO32; s4_reinit <= '0';
                i_accum <= ZERO32; pv_prev <= ZERO32; d_state <= ZERO32;
                Output <= (others => '0');

            elsif Ce = '1' then
                -- =====================================================
                -- STAGE 1: Clamp SP, compute errors
                -- =====================================================
                v_sp_lim   := clamp32(sp_s, splo_s, sphi_s);
                v_sp_beta  := mul_q230_q1616(be_s, v_sp_lim);
                v_ep       := v_sp_beta - pv_s;
                v_ei       := v_sp_lim  - pv_s;

                if Reinitialize = '1' then
                    i_accum <= ZERO32;
                    pv_prev <= pv_s;
                    d_state <= ZERO32;
                end if;

                s1_sp_lim <= v_sp_lim;
                s1_ep     <= v_ep;
                s1_ei     <= v_ei;
                s1_pv     <= pv_s;
                s1_kc     <= kc_s;
                s1_ki     <= ki_s;
                s1_kd     <= kd_s;
                s1_outhi  <= outhi_s;
                s1_outlo  <= outlo_s;
                s1_auto   <= AutoMode;
                s1_man    <= man_s;
                s1_alpha  <= al_s;
                s1_reinit <= Reinitialize;

                -- =====================================================
                -- STAGE 2: P-term  P = Kc * ep  (Q8.24 x Q16.16)
                -- =====================================================
                v_P := mul_q824_q1616(s1_kc, s1_ep);

                s2_P      <= v_P;
                s2_ei     <= s1_ei;
                s2_pv     <= s1_pv;
                s2_ki     <= s1_ki;
                s2_kd     <= s1_kd;
                s2_outhi  <= s1_outhi;
                s2_outlo  <= s1_outlo;
                s2_auto   <= s1_auto;
                s2_man    <= s1_man;
                s2_alpha  <= s1_alpha;
                s2_reinit <= s1_reinit;

                -- =====================================================
                -- STAGE 3: I-increment and D-raw
                -- dI   = KiCoeff * ei    (Q8.24 x Q16.16 -> Q16.16)
                -- Draw = -KdCoeff * (pv - pv_prev)
                -- =====================================================
                v_dI       := mul_q824_q1616(s2_ki, s2_ei);
                v_pv_delta := s2_pv - pv_prev;
                v_Draw     := -mul_q824_q1616(s2_kd, v_pv_delta);

                if s2_reinit = '0' then
                    pv_prev <= s2_pv;
                end if;

                s3_P      <= s2_P;
                s3_dI     <= v_dI;
                s3_Draw   <= v_Draw;
                s3_outhi  <= s2_outhi;
                s3_outlo  <= s2_outlo;
                s3_auto   <= s2_auto;
                s3_man    <= s2_man;
                s3_alpha  <= s2_alpha;
                s3_reinit <= s2_reinit;

                -- =====================================================
                -- STAGE 4: D filter + sum
                -- alpha_q1616 = alpha_q230 >> 14
                -- D_filt = alpha*D_prev + (1-alpha)*D_raw
                -- =====================================================
                v_al_q1616 := shift_right(s3_alpha, 14)(31 downto 0);
                v_D_filt   := mul_q1616_q1616(v_al_q1616, d_state) +
                              mul_q1616_q1616(ONE_Q1616 - v_al_q1616, s3_Draw);

                if s3_reinit = '0' then
                    d_state <= v_D_filt;
                else
                    d_state <= ZERO32;
                end if;

                v_u_sum  := resize(s3_P, 64) + resize(i_accum, 64) +
                            resize(s3_dI, 64) + resize(v_D_filt, 64);

                if v_u_sum > to_signed(2147483647, 64) then
                    v_u_raw := MAX32;
                elsif v_u_sum < to_signed(-2147483648, 64) then
                    v_u_raw := MIN32;
                else
                    v_u_raw := v_u_sum(31 downto 0);
                end if;

                s4_u_raw  <= v_u_raw;
                s4_dI     <= s3_dI;
                s4_outhi  <= s3_outhi;
                s4_outlo  <= s3_outlo;
                s4_auto   <= s3_auto;
                s4_man    <= s3_man;
                s4_reinit <= s3_reinit;

                -- =====================================================
                -- STAGE 5: Saturate, anti-windup, auto/manual mux
                -- =====================================================
                if s4_reinit = '1' then
                    i_accum <= ZERO32;
                    v_output := clamp32(s4_man, s4_outlo, s4_outhi);

                elsif s4_auto = '0' then
                    v_output := clamp32(s4_man, s4_outlo, s4_outhi);
                    -- Bumpless: preload integrator = manual - P - D
                    i_accum  <= v_output - s3_P - d_state;

                else
                    v_sat_hi := (s4_u_raw >= s4_outhi);
                    v_sat_lo := (s4_u_raw <= s4_outlo);
                    v_u_sat  := clamp32(s4_u_raw, s4_outlo, s4_outhi);
                    v_output := v_u_sat;

                    v_i_new  := i_accum + s4_dI;
                    if (not v_sat_hi and not v_sat_lo) or
                       (v_sat_hi and s4_dI < ZERO32) or
                       (v_sat_lo and s4_dI > ZERO32) then
                        i_accum <= v_i_new;
                    end if;
                end if;

                Output <= std_logic_vector(v_output);

            end if;
        end if;
    end process;

end architecture rtl;