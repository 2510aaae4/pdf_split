library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity sevenseg is
    port (
        bin  : in  std_logic_vector(3 downto 0);
        seg  : out std_logic_vector(6 downto 0)  -- a,b,c,d,e,f,g
    );
end entity;

architecture rtl of sevenseg is
begin
    process(bin)
    begin
        case bin is
            when "0000" => seg <= "1111110"; -- 0
            when "0001" => seg <= "0110000"; -- 1
            when "0010" => seg <= "1101101"; -- 2
            when "0011" => seg <= "1111001"; -- 3
            when "0100" => seg <= "0110011"; -- 4
            when "0101" => seg <= "1011011"; -- 5
            when "0110" => seg <= "1011111"; -- 6
            when "0111" => seg <= "1110000"; -- 7
            when "1000" => seg <= "1111111"; -- 8
            when "1001" => seg <= "1111011"; -- 9
            when others => seg <= "0000001"; -- dash
        end case;
    end process;
end architecture;
