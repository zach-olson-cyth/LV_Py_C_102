-- MovingAverage.vhd
-- 16-sample sliding-window moving average
-- CLIP_GEN_v4_9 envelope-safe rules:
--   - One synchronous process, sensitivity list (Clk) only
--   - No architecture-level functions
--   - No signal := initializers
--   - No shift-right-arithmetic or shift-right-logical  (VRFC 10-724)
--   - No integer literals with |value| > 2147483647  (VRFC 10-985)
--   - No 64-bit product-domain saturation constants (0x007FFFFFFF000000 etc.)
--   - Saturation via inlined if/elsif on bit-slice of 64-bit product
-- FXP formats:
--   DataIn  / DataOut : FXP<+/-,32,16>  Q16.16  range 0-100
--   AvgGain           : FXP<+/-,32,8>   Q8.24   = 1/N written from RT
--   Overflow          : Boolean (std_logic)
-- Algorithm:
--   Accumulator s_Sum (37 bits = 32+5 guard) holds running sum of 16 samples.
--   Each Ce clock: subtract oldest sample, add new sample.
--   Multiply sum by AvgGain (Q8.24) -> 64-bit product; shift right 24
--   via bit-slice (63 downto 24); inline saturation to Q16.16.
-- Q16.16 x Q8.24 multiply: 64-bit product, shift right 24
-- Shift-right idiom: resize(s_Product(63 downto 24), 64)

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity MovingAverage is
    port (
        Clk      : in  std_logic;
        aReset   : in  std_logic;
        Ce       : in  std_logic;
        DataIn   : in  std_logic_vector(31 downto 0);
        AvgGain  : in  std_logic_vector(31 downto 0);
        DataOut  : out std_logic_vector(31 downto 0);
        Overflow : out std_logic
    );
end entity MovingAverage;

architecture RTL of MovingAverage is

    attribute keep           : string;
    attribute dont_touch     : string;
    attribute keep_hierarchy : string;

    -- 16-deep shift register for samples; no := initializer
    type t_SampleReg is array (0 to 15) of signed(31 downto 0);
    signal s_SampleReg : t_SampleReg;

    -- Accumulator: 32 data bits + 5 guard bits for N=16
    signal s_Sum     : signed(36 downto 0);
    -- 64-bit product for multiply
    signal s_Product : signed(63 downto 0);
    -- Saturated 32-bit result
    signal s_Result  : signed(31 downto 0);
    -- Overflow flag register
    signal s_Ov      : std_logic;

    attribute keep       of s_Sum     : signal is "true";
    attribute keep       of s_Product : signal is "true";
    attribute keep       of s_Result  : signal is "true";
    attribute dont_touch of s_Sum     : signal is "true";
    attribute dont_touch of s_Product : signal is "true";
    attribute dont_touch of s_Result  : signal is "true";
    attribute keep_hierarchy of RTL   : architecture is "yes";

begin

    process(Clk)
        variable v_NewSum    : signed(36 downto 0);
        variable v_Shifted   : signed(63 downto 0);
        variable v_OvDetect  : std_logic;
    begin
        if rising_edge(Clk) then
            if aReset = '1' then
                -- Clear shift register
                for i in 0 to 15 loop
                    s_SampleReg(i) <= (others => '0');
                end loop;
                s_Sum     <= (others => '0');
                s_Product <= (others => '0');
                s_Result  <= (others => '0');
                s_Ov      <= '0';
            elsif Ce = '1' then
                -- Sliding-window accumulator:
                -- subtract oldest sample (index 15), add new sample
                v_NewSum := s_Sum
                          - resize(s_SampleReg(15), 37)
                          + resize(signed(DataIn), 37);

                -- Shift register update: shift right, insert new sample at 0
                for i in 15 downto 1 loop
                    s_SampleReg(i) <= s_SampleReg(i-1);
                end loop;
                s_SampleReg(0) <= signed(DataIn);

                s_Sum <= v_NewSum;

                -- Q16.16 x Q8.24 -> 64-bit product, shift right 24
                -- Multiply: resize sum to 64 bits x AvgGain (Q8.24)
                s_Product <= resize(v_NewSum, 64) * resize(signed(AvgGain), 64);

                -- Shift right 24 via bit-slice: product(63 downto 24)
                -- then resize to 64 for comparison
                v_Shifted := resize(s_Product(63 downto 24), 64);

                -- Inline saturation: compare against 32-bit bounds only
                -- (no 64-bit product-domain constants per v4.9 rule)
                v_OvDetect := '0';
                if v_Shifted > to_signed(2147483647, 64) then
                    s_Result   <= to_signed(2147483647, 32);
                    v_OvDetect := '1';
                elsif v_Shifted < to_signed(-2147483648, 64) then
                    s_Result   <= to_signed(-2147483648, 32);
                    v_OvDetect := '1';
                else
                    s_Result <= s_Product(55 downto 24);
                end if;

                s_Ov <= v_OvDetect;
            end if;
        end if;
    end process;

    DataOut  <= std_logic_vector(s_Result);
    Overflow <= s_Ov;

end architecture RTL;
