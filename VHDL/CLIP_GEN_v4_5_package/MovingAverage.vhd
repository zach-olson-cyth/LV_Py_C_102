-- MovingAverage.vhd
-- LabVIEW FPGA CLIP Node — 16-sample moving average filter
-- Target:  NI cRIO-class Kintex-7, xc7k70tfbg676-1
-- Clock:   40 MHz, synchronous reset
-- FXP:     Input/Output  FXP<+/-,32,16>  (Q16.16)
--          AvgGain port  FXP<+/-,32,8>   (Q8.24) = 1/N pre-scaled on RT
-- VHDL-2008  (ghdl --std=08)
-- v4.4 compliant — no generics, no process-local declare, all signals pre-declared

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity MovingAverage is
    port (
        Clk      : in  std_logic;
        aReset   : in  std_logic;
        Ce       : in  std_logic;
        -- Data input  FXP<+/-,32,16>
        DataIn   : in  std_logic_vector(31 downto 0);
        -- Pre-scaled gain = 1/N, computed on RT   FXP<+/-,32,8>
        AvgGain  : in  std_logic_vector(31 downto 0);
        -- Averaged output  FXP<+/-,32,16>
        DataOut  : out std_logic_vector(31 downto 0);
        -- Accumulator overflow flag
        Overflow : out std_logic
    );
end entity MovingAverage;

architecture RTL of MovingAverage is

    -- Saturation helper: clamp 64-bit product to signed 32-bit range
    function sat32(v : signed(63 downto 0)) return signed is
    begin
        if    v >  to_signed(2147483647, 64) then return to_signed( 2147483647, 32);
        elsif v < to_signed(-2147483648, 64) then return to_signed(-2147483648, 32);
        else  return v(31 downto 0);
        end if;
    end function;

    -- Shift-register type: 16 samples, each Q16.16 (32-bit signed)
    type t_SampleReg is array (0 to 15) of signed(31 downto 0);

    -- Architecture-level signal declarations (v4.4: no process-local declare)
    signal s_SampleReg  : t_SampleReg := (others => (others => '0'));
    signal s_Accum      : signed(36 downto 0) := (others => '0');  -- 32+5 guard bits
    signal s_DataIn_s   : signed(31 downto 0) := (others => '0');
    signal s_AvgGain_s  : signed(31 downto 0) := (others => '0');
    signal s_Product    : signed(63 downto 0) := (others => '0');
    signal s_Result     : signed(31 downto 0) := (others => '0');
    signal s_Overflow   : std_logic := '0';
    signal s_NewSample  : signed(31 downto 0) := (others => '0');
    signal s_OldSample  : signed(31 downto 0) := (others => '0');
    signal s_AccumNext  : signed(36 downto 0) := (others => '0');

begin

    -- Single clocked process — sensitivity list is (Clk) only (v4.4 rule)
    process(Clk)
    begin
        if rising_edge(Clk) then
            if aReset = '1' then
                -- Clear all state registers
                s_SampleReg <= (others => (others => '0'));
                s_Accum     <= (others => '0');
                s_DataIn_s  <= (others => '0');
                s_AvgGain_s <= (others => '0');
                s_Product   <= (others => '0');
                s_Result    <= (others => '0');
                s_Overflow  <= '0';
                s_NewSample <= (others => '0');
                s_OldSample <= (others => '0');
                s_AccumNext <= (others => '0');
                DataOut     <= (others => '0');
                Overflow    <= '0';

            elsif Ce = '1' then
                -- Latch inputs
                s_DataIn_s  <= signed(DataIn);
                s_AvgGain_s <= signed(AvgGain);

                -- Sliding window: oldest sample exits, newest enters
                -- s_OldSample = sample leaving the window
                s_OldSample <= s_SampleReg(15);

                -- Shift register: index 0 is newest, 15 is oldest
                s_SampleReg(0) <= signed(DataIn);
                for i in 1 to 15 loop
                    s_SampleReg(i) <= s_SampleReg(i - 1);
                end loop;

                -- s_NewSample registered one cycle after DataIn is latched
                s_NewSample <= signed(DataIn);

                -- Running accumulator update: add new, subtract outgoing
                -- Both operands are Q16.16; accumulator has 5 guard bits
                -- for N=16 (max sum = 16 * 2^16-1, needs ~37 bits)
                s_AccumNext <= s_Accum
                               + resize(s_NewSample, 37)
                               - resize(s_OldSample, 37);
                s_Accum     <= s_AccumNext;

                -- Overflow detection: upper 6 bits all same means no overflow
                if s_AccumNext(36 downto 31) = "000000" or
                   s_AccumNext(36 downto 31) = "111111" then
                    s_Overflow <= '0';
                else
                    s_Overflow <= '1';
                end if;

                -- Multiply accumulator by AvgGain (Q8.24 = 1/N)
                -- Accum is Q16.16 in 37-bit container; AvgGain is Q8.24
                -- Product scale: Q16.16 * Q8.24 = Q24.40 in 64 bits
                -- To recover Q16.16: shift product right by 24 (FWL of gain)
                s_Product <= resize(s_Accum, 64) * resize(s_AvgGain_s, 64);

                -- Scale: shift right 24 to align back to Q16.16
                -- s_Product(63 downto 24) is the Q16.16 result in 40 bits
                -- sat32 clamps to 32-bit signed
                s_Result <= sat32(s_Product(63 downto 0) sra 24);

                -- Drive outputs
                DataOut  <= std_logic_vector(s_Result);
                Overflow <= s_Overflow;

            end if;  -- Ce
        end if;  -- rising_edge
    end process;

end architecture RTL;
