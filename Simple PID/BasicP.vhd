library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity BasicPid is
  port (
    Clk                : in  std_logic;
    Ce                 : in  std_logic;
    aReset             : in  std_logic;
    Setpoint           : in  std_logic_vector(31 downto 0);
    ProcessVariable    : in  std_logic_vector(31 downto 0);
    ProportionalGainKp : in  std_logic_vector(31 downto 0);
    Output             : out std_logic_vector(31 downto 0)
  );
end BasicPid;

architecture RTL of BasicPid is
  signal output_reg : std_logic_vector(31 downto 0);
begin
  process(Clk)
  begin
    if rising_edge(Clk) then
      if aReset = '1' then
        output_reg <= (others => '0');
      elsif Ce = '1' then
        output_reg <= Setpoint;
      end if;
    end if;
  end process;
  Output <= output_reg;
end RTL;
