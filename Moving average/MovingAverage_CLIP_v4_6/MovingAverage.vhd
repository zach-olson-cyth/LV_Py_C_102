-- MovingAverage.vhd
-- LabVIEW FPGA CLIP Node — 16-sample sliding-window moving average filter
-- Target:  NI cRIO-class Kintex-7, xc7k70tfbg676-1
-- Clock:   40 MHz synchronous
-- FXP:     Input/Output  FXP<+/-,32,16>  Q16.16
--          AvgGain port  FXP<+/-,32,8>   Q8.24  = 1/N, pre-scaled on RT
-- VHDL-2008  (ghdl --std=08)
-- v4.5 compliant — no generics, no process-local declare,
--   all intermediate signals pre-declared at architecture level

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity MovingAverage is
    port (
        Clk      : in  std_logic;
        aReset   : in  std_logic;
        Ce       : in  std_logic;
        DataIn   : in  std_logic_vector(31 downto 0);  -- FXP<+/-,32,16>
        AvgGain  : in  std_logic_vector(31 downto 0);  -- FXP<+/-,32,8> = 1/N
        DataOut  : out std_logic_vector(31 downto 0);  -- FXP<+/-,32,16>
        Overflow : out std_logic
    );
end entity MovingAverage;

architecture RTL of MovingAverage is

    -- Shift-right rules for FXP multiplication:
    -- shift_right = FWL of the GAIN operand = WordLength - IWL of the gain
    -- FXP<+/-,32,8>  gain: shift = 32 - 8  = 24
    -- FXP<+/-,32,16> gain: shift = 32 - 16 = 16
    -- Comment format: -- Q<SI>.<SFW> x Q<GI>.<GFW>, shift right <GFW>

    -- Saturation helper: clamp 64-bit signed product to 32-bit signed range
    function sat32(v : signed(63 downto 0)) return signed is
    begin
        if    v >  to_signed(2147483647, 64) then return to_signed( 2147483647, 32);
        elsif v < to_signed(-2147483648, 64) then return to_signed(-2147483648, 32);
        else  return v(31 downto 0);
        end if;
    end function;

    -- Shift-register type: 16 samples of Q16.16 (32-bit signed)
    type t_SampleReg is array (0 to 15) of signed(31 downto 0);

    -- Architecture-level signal declarations
    -- (v4.5: no process-local declare blocks permitted)
    signal s_SampleReg  : t_SampleReg  := (others => (others => '0'));
    signal s_Accum      : signed(36 downto 0) := (others => '0');  -- 5 guard bits for N=16
    signal s_AccumNext  : signed(36 downto 0) := (others => '0');
    signal s_NewSample  : signed(31 downto 0) := (others => '0');
    signal s_OldSample  : signed(31 downto 0) := (others => '0');
    signal s_AvgGain_s  : signed(31 downto 0) := (others => '0');
    signal s_Product    : signed(63 downto 0) := (others => '0');
    signal s_Result     : signed(31 downto 0) := (others => '0');
    signal s_Overflow   : std_logic := '0';

begin

    -- Single clocked process; sensitivity list is (Clk) only (v4.5 rule)
    process(Clk)
    begin
        if rising_edge(Clk) then
            if aReset = '1' then
                -- Clear every state register and output register
                s_SampleReg  <= (others => (others => '0'));
                s_Accum      <= (others => '0');
                s_AccumNext  <= (others => '0');
                s_NewSample  <= (others => '0');
                s_OldSample  <= (others => '0');
                s_AvgGain_s  <= (others => '0');
                s_Product    <= (others => '0');
                s_Result     <= (others => '0');
                s_Overflow   <= '0';
                DataOut      <= (others => '0');
                Overflow     <= '0';

            elsif Ce = '1' then
                -- Stage 1: latch inputs, update shift register
                s_AvgGain_s     <= signed(AvgGain);
                s_OldSample     <= s_SampleReg(15);          -- oldest exits
                s_NewSample     <= signed(DataIn);           -- newest enters
                s_SampleReg(0)  <= signed(DataIn);
                for i in 1 to 15 loop
                    s_SampleReg(i) <= s_SampleReg(i - 1);
                end loop;

                -- Stage 2: running accumulator — add newest, subtract oldest
                -- Both operands are Q16.16; 5 guard bits support N=16 max sum
                s_AccumNext <= s_Accum
                               + resize(s_NewSample, 37)
                               - resize(s_OldSample, 37);
                s_Accum     <= s_AccumNext;

                -- Accumulator overflow detection (guard bits exhausted)
                if s_AccumNext(36 downto 31) = "000000" or
                   s_AccumNext(36 downto 31) = "111111" then
                    s_Overflow <= '0';
                else
                    s_Overflow <= '1';
                end if;

                -- Stage 3: multiply accumulator by AvgGain (1/N)
                -- Q16.16 (in 37-bit container) x Q8.24, shift right 24
                -- Product is Q24.40 in 64 bits; shift right 24 -> Q16.16
                s_Product <= resize(s_Accum, 64) * resize(s_AvgGain_s, 64);
                -- Q16.16 x Q8.24, shift right 24
                s_Result  <= sat32(s_Product sra 24);

                -- Stage 4: drive outputs
                DataOut  <= std_logic_vector(s_Result);
                Overflow <= s_Overflow;

            end if;  -- Ce
        end if;  -- rising_edge
    end process;

end architecture RTL;
