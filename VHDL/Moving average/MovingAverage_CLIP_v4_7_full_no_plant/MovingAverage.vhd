-- MovingAverage.vhd
-- LabVIEW FPGA CLIP Node — 16-sample sliding-window moving average filter
-- Target:  NI cRIO-class Kintex-7, xc7k70tfbg676-1
-- Clock:   40 MHz synchronous
-- FXP:     Input/Output  FXP<+/-,32,16>  Q16.16
--          AvgGain port  FXP<+/-,32,8>   Q8.24  = 1/N, pre-scaled on RT
-- VHDL-2008 compliant
--
-- v4.7 Synthesis rules for NI FPGA CLIP nodes:
--   RULE 1: No architecture-level functions (Synth 8-5809 in NI encrypted wrapper)
--   RULE 2: No signal initial values :=  (Synth 8-5809 in NI encrypted wrapper)
--   RULE 3: No sra / srl operators      (Vivado VRFC 10-724)
--   RULE 4: Saturation inlined as if/elsif — no helper function
--   RULE 5: All state initialized exclusively in aReset branch

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

    -- Shift-right comment convention:
    --   Q16.16 x Q8.24 -> 64-bit product; shift right 24 -> Q16.16 result
    --   Bit-slice idiom: product(55 downto 24) == lower 32 bits of (product >> 24)
    --   sra / srl are forbidden (Vivado VRFC 10-724)
    --
    -- Saturation boundary constants (pre-shifted by 24 to match product scale):
    --   Positive saturation: if product > 2147483647 * 2^24
    --   Negative saturation: if product < -2147483648 * 2^24
    --   These are compared directly to s_Product (64-bit) — no resize needed.

    -- Shift-register type for N=16 samples (no := initializer)
    type t_SampleReg is array (0 to 15) of signed(31 downto 0);
    signal s_SampleReg : t_SampleReg;

    -- Accumulator: 37 bits = 32 data + 5 guard bits (handles sum of 16 x Q16.16)
    signal s_Accum      : signed(36 downto 0);
    signal s_AccumNext  : signed(36 downto 0);

    -- Datapath registers (no := initializers)
    signal s_NewSample  : signed(31 downto 0);
    signal s_OldSample  : signed(31 downto 0);
    signal s_AvgGain_s  : signed(31 downto 0);
    signal s_Product    : signed(63 downto 0);
    signal s_Result     : signed(31 downto 0);
    signal s_Overflow   : std_logic;

    -- Saturation thresholds in product domain (Q16.16 * Q8.24 scale = shift 24)
    -- C_SAT_POS = 2147483647 * 2^24 = 36028797004276736 - 16777216 = 0x007FFFFFFF000000
    -- C_SAT_NEG = -2147483648 * 2^24                               = 0xFF80000000000000
    constant C_SAT_POS : signed(63 downto 0) :=
        to_signed(36028797002186752, 64);  -- 2147483647 * 16777216
    constant C_SAT_NEG : signed(63 downto 0) :=
        to_signed(-36028797018963968, 64); -- -2147483648 * 16777216

begin

    process(Clk)
    begin
        if rising_edge(Clk) then
            if aReset = '1' then
                -- Initialize all state registers and output ports
                for i in 0 to 15 loop
                    s_SampleReg(i) <= (others => '0');
                end loop;
                s_Accum     <= (others => '0');
                s_AccumNext <= (others => '0');
                s_NewSample <= (others => '0');
                s_OldSample <= (others => '0');
                s_AvgGain_s <= (others => '0');
                s_Product   <= (others => '0');
                s_Result    <= (others => '0');
                s_Overflow  <= '0';
                DataOut     <= (others => '0');
                Overflow    <= '0';

            elsif Ce = '1' then

                -- Stage 1: latch inputs and update shift register
                s_AvgGain_s    <= signed(AvgGain);
                s_OldSample    <= s_SampleReg(15);     -- oldest exits
                s_NewSample    <= signed(DataIn);       -- newest enters
                s_SampleReg(0) <= signed(DataIn);
                for i in 1 to 15 loop
                    s_SampleReg(i) <= s_SampleReg(i - 1);
                end loop;

                -- Stage 2: running accumulator (add new, subtract old)
                -- Q16.16 operands in 37-bit container; 5 guard bits for N=16
                s_AccumNext <= s_Accum
                               + resize(s_NewSample, 37)
                               - resize(s_OldSample, 37);
                s_Accum <= s_AccumNext;

                -- Guard-bit overflow check (sign extension bits must all match)
                if s_AccumNext(36 downto 31) = "000000" or
                   s_AccumNext(36 downto 31) = "111111" then
                    s_Overflow <= '0';
                else
                    s_Overflow <= '1';
                end if;

                -- Stage 3: multiply accumulator by AvgGain (1/N)
                -- Q16.16 (in 37-bit container) x Q8.24 (32-bit) -> 64-bit product
                s_Product <= resize(s_Accum, 64) * resize(s_AvgGain_s, 64);

                -- Stage 4: extract Q16.16 result via bit-slice (shift right 24)
                -- and apply inline saturation to 32-bit signed range
                -- Q16.16 x Q8.24, shift right 24 via product(55 downto 24)
                -- Saturation compares product to bounds in the product domain
                if s_Product > C_SAT_POS then
                    s_Result <= to_signed(2147483647, 32);
                elsif s_Product < C_SAT_NEG then
                    s_Result <= to_signed(-2147483648, 32);
                else
                    s_Result <= s_Product(55 downto 24);  -- shift right 24, take 32 LSBs
                end if;

                -- Stage 5: drive output ports
                DataOut  <= std_logic_vector(s_Result);
                Overflow <= s_Overflow;

            end if;  -- Ce
        end if;  -- rising_edge
    end process;

end architecture RTL;
