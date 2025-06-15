library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package cpu_pkg is
    constant REG_COUNT : integer := 4;
    subtype reg_index is integer range 0 to REG_COUNT-1;

    constant DATA_WIDTH : integer := 8;
    subtype data_word is std_logic_vector(DATA_WIDTH-1 downto 0);

    -- Opcodes
    type opcode_t is (OP_ADD, OP_SUB, OP_AND, OP_OR, OP_LOADI, OP_MOV);
end package;
