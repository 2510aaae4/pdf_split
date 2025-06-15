library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity register_file is
    port (
        clk   : in  std_logic;
        we    : in  std_logic;
        rd    : in  reg_index;
        rs    : in  reg_index;
        rt    : in  reg_index;
        din   : in  data_word;
        doutR : out data_word;
        doutS : out data_word;
        doutT : out data_word
    );
end entity;

architecture rtl of register_file is
    type reg_array is array(reg_index) of data_word;
    signal regs : reg_array := (others => (others => '0'));
begin
    process(clk)
    begin
        if rising_edge(clk) then
            if we = '1' then
                regs(rd) <= din;
            end if;
        end if;
    end process;
    doutR <= regs(rd);
    doutS <= regs(rs);
    doutT <= regs(rt);
end architecture;
