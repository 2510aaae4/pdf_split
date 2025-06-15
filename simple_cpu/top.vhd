library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity top is
    port (
        clk     : in  std_logic;
        reset   : in  std_logic;
        start   : in  std_logic;
        instr   : in  std_logic_vector(15 downto 0);
        seg_rs  : out std_logic_vector(6 downto 0);
        seg_rt  : out std_logic_vector(6 downto 0);
        seg_bus : out std_logic_vector(6 downto 0)
    );
end entity;

architecture rtl of top is
    signal op      : opcode_t;
    signal rd, rs, rt : reg_index;
    signal imm     : data_word;
    signal we      : std_logic;
    signal done    : std_logic;

    signal rs_val, rt_val, alu_out : data_word;

begin
    ctrl: entity work.controller
        port map(
            clk   => clk,
            reset => reset,
            start => start,
            instr => instr,
            op    => op,
            rd    => rd,
            rs    => rs,
            rt    => rt,
            imm   => imm,
            we    => we,
            done  => done
        );

    regs: entity work.register_file
        port map(
            clk   => clk,
            we    => we,
            rd    => rd,
            rs    => rs,
            rt    => rt,
            din   => alu_out,
            doutR => open,
            doutS => rs_val,
            doutT => rt_val
        );

    ualu: entity work.alu
        port map(
            op    => op,
            a     => rs_val,
            b     => rt_val,
            result => alu_out
        );

    disp_rs: entity work.sevenseg port map(bin => rs_val(3 downto 0), seg => seg_rs);
    disp_rt: entity work.sevenseg port map(bin => rt_val(3 downto 0), seg => seg_rt);
    disp_bus: entity work.sevenseg port map(bin => alu_out(3 downto 0), seg => seg_bus);

end architecture;
