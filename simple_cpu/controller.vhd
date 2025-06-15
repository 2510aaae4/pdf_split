library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity controller is
    port (
        clk     : in  std_logic;
        reset   : in  std_logic;
        start   : in  std_logic;
        instr   : in  std_logic_vector(15 downto 0);
        -- control outputs
        op      : out opcode_t;
        rd      : out reg_index;
        rs      : out reg_index;
        rt      : out reg_index;
        imm     : out data_word;
        we      : out std_logic;
        done    : out std_logic
    );
end entity;

architecture rtl of controller is
    type state_t is (S_IDLE, S_EXEC);
    signal state : state_t := S_IDLE;
    signal op_reg : opcode_t;
    signal rd_reg, rs_reg, rt_reg : reg_index;
    signal imm_reg : data_word;
begin
    op  <= op_reg;
    rd  <= rd_reg;
    rs  <= rs_reg;
    rt  <= rt_reg;
    imm <= imm_reg;

    process(clk, reset)
    begin
        if reset = '1' then
            state <= S_IDLE;
            done  <= '0';
            we    <= '0';
        elsif rising_edge(clk) then
            case state is
                when S_IDLE =>
                    done <= '0';
                    we   <= '0';
                    if start = '1' then
                        -- Convert the upper four bits of the instruction to an
                        -- opcode value using 'val so the enumerated literal is
                        -- selected by position.
                        op_reg <= opcode_t'val(to_integer(unsigned(instr(15 downto 12))));
                        rd_reg <= to_integer(unsigned(instr(11 downto 10)));
                        rs_reg <= to_integer(unsigned(instr(9 downto 8)));
                        rt_reg <= to_integer(unsigned(instr(7 downto 6)));
                        imm_reg <= instr(7 downto 0);
                        state <= S_EXEC;
                    end if;
                when S_EXEC =>
                    we   <= '1';
                    done <= '1';
                    state <= S_IDLE;
                when others =>
                    state <= S_IDLE;
            end case;
        end if;
    end process;
end architecture;
