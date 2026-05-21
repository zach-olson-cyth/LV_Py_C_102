library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity PID_ValveController_Simple is
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
end entity;

architecture rtl of PID_ValveController_Simple is
    function sat32(x : signed(63 downto 0)) return signed is
        variable y : signed(31 downto 0);
        constant MAX32 : signed(63 downto 0) := to_signed(2147483647, 64);
        constant MIN32 : signed(63 downto 0) := to_signed(-2147483648, 64);
    begin
        if x > MAX32 then
            y := to_signed(2147483647, 32);
        elsif x < MIN32 then
            y := to_signed(-2147483648, 32);
        else
            y := resize(x, 32);
        end if;
        return y;
    end function;

    function clamp32(x, lo, hi : signed(31 downto 0)) return signed is
    begin
        if x > hi then
            return hi;
        elsif x < lo then
            return lo;
        else
            return x;
        end if;
    end function;

    signal sp_r, pv_r, sphi_r, splo_r, outhi_r, outlo_r : signed(31 downto 0) := (others => '0');
    signal kc_r, ti_r, td_r, dt_r, man_r : signed(31 downto 0) := (others => '0');
    signal auto_r, rein_r : std_logic := '0';
    signal p_term, i_term, d_term, out_reg, pv_prev, dt_used : signed(31 downto 0) := (others => '0');
    constant DT_MIN_Q24 : signed(31 downto 0) := to_signed(16777, 32);
    constant SIXTY_Q16  : signed(31 downto 0) := to_signed(3932160, 32);
begin
    process(Clk)
        variable v_sp_lim, v_err : signed(31 downto 0);
        variable v_p64, v_i64, v_d64, v_out64 : signed(63 downto 0);
        variable v_ti_sec, v_td_sec : signed(31 downto 0);
        variable v_pv_delta : signed(31 downto 0);
        variable v_i_next, v_d_next, v_out_next : signed(31 downto 0);
    begin
        if rising_edge(Clk) then
            if aReset = '1' then
                sp_r <= (others => '0'); pv_r <= (others => '0'); sphi_r <= (others => '0'); splo_r <= (others => '0');
                outhi_r <= (others => '0'); outlo_r <= (others => '0'); kc_r <= (others => '0'); ti_r <= (others => '0');
                td_r <= (others => '0'); dt_r <= DT_MIN_Q24; man_r <= (others => '0'); auto_r <= '0'; rein_r <= '0';
                p_term <= (others => '0'); i_term <= (others => '0'); d_term <= (others => '0'); out_reg <= (others => '0');
                pv_prev <= (others => '0'); dt_used <= DT_MIN_Q24;
            elsif Ce = '1' then
                sp_r    <= signed(Setpoint);
                pv_r    <= signed(ProcessVariable);
                sphi_r  <= signed(SetpointHigh);
                splo_r  <= signed(SetpointLow);
                outhi_r <= signed(OutputHigh);
                outlo_r <= signed(OutputLow);
                kc_r    <= signed(ProportionalGainKc);
                ti_r    <= signed(IntegralTimeTiMin);
                td_r    <= signed(DerivativeTimeTdMin);
                man_r   <= signed(ManualControl);
                auto_r  <= AutoMode;
                rein_r  <= Reinitialize;

                if signed(DtS) > DT_MIN_Q24 then
                    dt_r <= signed(DtS);
                    dt_used <= signed(DtS);
                else
                    dt_r <= DT_MIN_Q24;
                    dt_used <= DT_MIN_Q24;
                end if;

                v_sp_lim := clamp32(sp_r, splo_r, sphi_r);
                v_err := v_sp_lim - pv_r;

                if rein_r = '1' then
                    i_term <= (others => '0');
                    d_term <= (others => '0');
                    pv_prev <= pv_r;
                else
                    v_p64 := resize(kc_r, 64) * resize(v_err, 64);
                    p_term <= sat32(shift_right(v_p64, 24));

                    v_i_next := i_term;
                    if ti_r > 0 then
                        v_ti_sec := sat32(shift_right(resize(ti_r,64) * resize(SIXTY_Q16,64), 16));
                        if v_ti_sec > 0 then
                            v_i64 := resize(kc_r,64) * resize(v_err,64);
                            v_i64 := shift_right(v_i64, 24);
                            v_i64 := resize(sat32(v_i64),64) * resize(dt_r,64);
                            v_i64 := shift_right(v_i64,24);
                            v_i64 := shift_left(v_i64,16) / resize(v_ti_sec,64);
                            v_i_next := sat32(resize(i_term,64) + v_i64);
                        end if;
                    end if;

                    v_d_next := (others => '0');
                    if td_r > 0 then
                        v_td_sec := sat32(shift_right(resize(td_r,64) * resize(SIXTY_Q16,64), 16));
                        v_pv_delta := pv_r - pv_prev;
                        if dt_r > 0 then
                            v_d64 := resize(kc_r,64) * resize(v_pv_delta,64);
                            v_d64 := shift_right(v_d64,24);
                            v_d64 := resize(sat32(v_d64),64) * resize(v_td_sec,64);
                            v_d64 := shift_right(v_d64,16);
                            v_d64 := -shift_left(v_d64,24) / resize(dt_r,64);
                            v_d_next := sat32(v_d64);
                        end if;
                    end if;

                    i_term <= v_i_next;
                    d_term <= v_d_next;
                    pv_prev <= pv_r;
                end if;

                if auto_r = '1' then
                    v_out64 := resize(p_term,64) + resize(i_term,64) + resize(d_term,64);
                    v_out_next := clamp32(sat32(v_out64), outlo_r, outhi_r);
                    out_reg <= v_out_next;
                else
                    out_reg <= clamp32(man_r, outlo_r, outhi_r);
                end if;
            end if;
        end if;
    end process;

    Output <= std_logic_vector(out_reg);
    DtOut  <= std_logic_vector(dt_used);
end architecture;
