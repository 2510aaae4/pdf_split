library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity alu is
    port (
        op   : in  opcode_t;
        a    : in  data_word;
        b    : in  data_word;
        result : out data_word
    );
end entity;

architecture rtl of alu is
begin
    process(op, a, b)
    begin
        case op is
            when OP_ADD  => result <= std_logic_vector(unsigned(a) + unsigned(b));
            when OP_SUB  => result <= std_logic_vector(unsigned(a) - unsigned(b));
            when OP_AND  => result <= a and b;
            when OP_OR   => result <= a or b;
            when others  => result <= (others => '0');
        end case;
    end process;
end architecture;
