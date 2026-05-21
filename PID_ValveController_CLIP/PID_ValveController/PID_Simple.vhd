library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- PID_Simple: Standard PID controller for LabVIEW FPGA CLIP import
-- Build mode  : Quick
-- Target      : cRIO-class Kintex-7
-- Master clock: 40 MHz; functional rate: 5 MHz via Ce every 8 clocks
-- FXP formats : Q16.16 process values, Q8.24 gains/dt, Boolean flags
-- No advanced coefficients (no Alpha, Beta, Gamma, Linearity)

entity PID_Simple is
    port (
        Clk                 : in  std_logic;
        Ce                  : in  std_logic;
        aReset              : in  std_logic;
        Setpoint            : in  std_logic_vector(31 downto 0);
        ProcessVariable     : in  std_logic_vector(31 downto 0);
        SetpointHigh        : in  std_logic_vector(31 downto 0);
        SetpointLow         : in  std_logic_vector(31 downto 0);
        OutputHigh          : in  std_logic_vector(31 downto 0);
        OutputLow           : in  std_logic_vector(31 downto 0);
        ProportionalGainKc  : in  std_logic_vector(31 downto 0);
        IntegralTimeTiMin   : in  std_logic_vector(31 downto 0);
        DerivativeTimeTdMin : in  std_logic_vector(31 downto 0);
        DtS                 : in  std_logic_vector(31 downto 0);
        AutoMode            : in  std_logic;
        ManualControl       : in  std_logic_vector(31 downto 0);
        Reinitialize        : in  std_logic;
        Output              : out std_logic_vector(31 downto 0);
        DtOut               : out std_logic_vector(31 downto 0)
    );
end entity PID_Simple;

architecture rtl of PID_Simple is

    -- -----------------------------------------------------------------------
    -- Saturate a 64-bit signed value into a 32-bit signed result
    -- -----------------------------------------------------------------------
    function sat32(x : signed(63 downto 0)) return signed is
        constant HI : signed(63 downto 0) := to_signed( 2147483647, 64);
        constant LO : signed(63 downto 0) := to_signed(-2147483648, 64);
    begin
        if    x > HI then return to_signed( 2147483647, 32);
        elsif x < LO then return to_signed(-2147483648, 32);
        else               return x(31 downto 0);
        end if;
    end function;

    -- -----------------------------------------------------------------------
    -- Clamp a 32-bit signed value between lo and hi
    -- -----------------------------------------------------------------------
    function clamp32(x, lo, hi : signed(31 downto 0)) return signed is
    begin
        if    x > hi then return hi;
        elsif x < lo then return lo;
        else               return x;
        end if;
    end function;

    -- -----------------------------------------------------------------------
    -- Scale constants
    -- DT_MIN: 0.001 s in Q8.24  = 0.001 * 2^24 = 16777
    -- SIXTY : 60 in Q16.16      = 60   * 2^16  = 3932160
    -- -----------------------------------------------------------------------
    constant DT_MIN  : signed(31 downto 0) := to_signed(16777,   32);
    constant SIXTY   : signed(31 downto 0) := to_signed(3932160, 32);

    -- Internal state
    signal i_accum  : signed(31 downto 0) := (others => '0'); -- Q16.16
    signal pv_prev  : signed(31 downto 0) := (others => '0'); -- Q16.16
    signal dt_safe  : signed(31 downto 0) := DT_MIN;          -- Q8.24
    signal out_reg  : signed(31 downto 0) := (others => '0'); -- Q16.16

begin

    process(Clk)
        -- working copies of inputs
        variable v_sp    : signed(31 downto 0);
        variable v_pv    : signed(31 downto 0);
        variable v_sphi  : signed(31 downto 0);
        variable v_splo  : signed(31 downto 0);
        variable v_outhi : signed(31 downto 0);
        variable v_outlo : signed(31 downto 0);
        variable v_kc    : signed(31 downto 0);
        variable v_ti    : signed(31 downto 0);
        variable v_td    : signed(31 downto 0);
        variable v_dt    : signed(31 downto 0);
        variable v_man   : signed(31 downto 0);

        -- intermediate results
        variable v_sp_lim  : signed(31 downto 0);
        variable v_err     : signed(31 downto 0);
        variable v_ti_sec  : signed(31 downto 0); -- Ti in seconds Q16.16
        variable v_td_sec  : signed(31 downto 0); -- Td in seconds Q16.16
        variable v_p       : signed(31 downto 0); -- P term Q16.16
        variable v_di      : signed(31 downto 0); -- I increment Q16.16
        variable v_d       : signed(31 downto 0); -- D term Q16.16
        variable v_i_next  : signed(31 downto 0); -- candidate i_accum
        variable v_u_raw   : signed(31 downto 0); -- unsaturated sum
        variable v_tmp64   : signed(63 downto 0); -- scratch
        variable v_out     : signed(31 downto 0); -- final output
    begin
        if rising_edge(Clk) then
            if aReset = '1' then
                i_accum <= (others => '0');
                pv_prev <= (others => '0');
                dt_safe <= DT_MIN;
                out_reg <= (others => '0');

            elsif Ce = '1' then
                -- --------------------------------------------------------
                -- Latch inputs
                -- --------------------------------------------------------
                v_sp    := signed(Setpoint);
                v_pv    := signed(ProcessVariable);
                v_sphi  := signed(SetpointHigh);
                v_splo  := signed(SetpointLow);
                v_outhi := signed(OutputHigh);
                v_outlo := signed(OutputLow);
                v_kc    := signed(ProportionalGainKc);
                v_ti    := signed(IntegralTimeTiMin);
                v_td    := signed(DerivativeTimeTdMin);
                v_dt    := signed(DtS);
                v_man   := signed(ManualControl);

                -- --------------------------------------------------------
                -- Sanitise dt; enforce minimum to prevent divide issues
                -- --------------------------------------------------------
                if v_dt > DT_MIN then
                    dt_safe <= v_dt;
                    v_dt    := v_dt;
                else
                    dt_safe <= DT_MIN;
                    v_dt    := DT_MIN;
                end if;

                -- --------------------------------------------------------
                -- Clamp setpoint to [SetpointLow, SetpointHigh]
                -- --------------------------------------------------------
                v_sp_lim := clamp32(v_sp, v_splo, v_sphi);

                -- --------------------------------------------------------
                -- Reinitialize: clear state, exit early via manual path
                -- --------------------------------------------------------
                if Reinitialize = '1' then
                    i_accum <= (others => '0');
                    pv_prev <= v_pv;
                    out_reg <= clamp32(v_man, v_outlo, v_outhi);

                -- --------------------------------------------------------
                -- Manual mode: pass ManualControl directly; track integrator
                -- for bumpless auto resume
                -- --------------------------------------------------------
                elsif AutoMode = '0' then
                    v_out   := clamp32(v_man, v_outlo, v_outhi);
                    out_reg <= v_out;
                    -- Track: i_accum = output so P+I matches on auto resume
                    i_accum <= v_out;
                    pv_prev <= v_pv;

                -- --------------------------------------------------------
                -- Auto mode: compute PID
                -- --------------------------------------------------------
                else
                    v_err := v_sp_lim - v_pv;

                    -- P term: Kc * err
                    -- Kc is Q8.24, err is Q16.16 -> product is Q24.40
                    -- Right-shift 24 to get Q16.16
                    v_tmp64 := resize(v_kc, 64) * resize(v_err, 64);
                    v_p     := sat32(shift_right(v_tmp64, 24));

                    -- I increment: Kc * err * dt / Ti_sec
                    -- Ti_sec (Q16.16) = Ti_min (Q16.16) * 60 (integer)
                    -- -> multiply, right-shift 16 to stay Q16.16
                    if v_ti > to_signed(65, 32) then   -- guard: Ti > ~0.001 min
                        v_tmp64  := resize(v_ti, 64) * resize(SIXTY, 64);
                        v_ti_sec := sat32(shift_right(v_tmp64, 16));

                        -- di = Kc * err (Q16.16 from above) * dt (Q8.24)
                        --      then divide by Ti_sec (Q16.16)
                        -- di is Q16.16
                        v_tmp64 := resize(v_p, 64) * resize(v_dt, 64);
                        v_tmp64 := shift_right(v_tmp64, 24); -- * dt, now Q16.16
                        if v_ti_sec /= to_signed(0, 32) then
                            v_tmp64 := shift_left(v_tmp64, 16) /
                                       resize(v_ti_sec, 64);
                        else
                            v_tmp64 := (others => '0');
                        end if;
                        v_di := sat32(v_tmp64);
                    else
                        v_di := (others => '0');
                    end if;

                    -- D term: -Kc * (pv - pv_prev) * Td_sec / dt
                    -- Td_sec (Q16.16) = Td_min (Q16.16) * 60
                    if v_td > to_signed(0, 32) then
                        v_tmp64  := resize(v_td, 64) * resize(SIXTY, 64);
                        v_td_sec := sat32(shift_right(v_tmp64, 16));

                        -- -Kc * (pv - pv_prev) -> Q16.16
                        v_tmp64 := resize(v_kc, 64) *
                                   resize(v_pv - pv_prev, 64);
                        v_tmp64 := shift_right(v_tmp64, 24); -- Q16.16

                        -- multiply by Td_sec (Q16.16), shift right 16
                        v_tmp64 := v_tmp64 * resize(v_td_sec, 64);
                        v_tmp64 := shift_right(v_tmp64, 16);

                        -- divide by dt (Q8.24); adjust scale: shift left 24
                        if v_dt /= to_signed(0, 32) then
                            v_tmp64 := shift_left(v_tmp64, 24) /
                                       resize(v_dt, 64);
                        else
                            v_tmp64 := (others => '0');
                        end if;
                        v_d := sat32(-v_tmp64);
                    else
                        v_d := (others => '0');
                    end if;

                    -- Sum and anti-windup
                    v_i_next := sat32(resize(i_accum, 64) +
                                      resize(v_di, 64));
                    v_tmp64  := resize(v_p, 64) + resize(v_i_next, 64) +
                                resize(v_d, 64);
                    v_u_raw  := sat32(v_tmp64);
                    v_out    := clamp32(v_u_raw, v_outlo, v_outhi);

                    -- Only accumulate integral when not saturated,
                    -- or when saturation and error push in opposite directions
                    if (v_u_raw = v_out) or
                       (v_out = v_outhi and v_di < to_signed(0, 32)) or
                       (v_out = v_outlo and v_di > to_signed(0, 32)) then
                        i_accum <= v_i_next;
                    end if;

                    out_reg <= v_out;
                    pv_prev <= v_pv;
                end if;
            end if;
        end if;
    end process;

    Output <= std_logic_vector(out_reg);
    DtOut  <= std_logic_vector(dt_safe);

end architecture rtl;
