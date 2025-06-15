# Simple VHDL CPU

This directory contains a minimal VHDL design for a small CPU with four
registers (R0--R3), an ALU, a control unit with an FSM, and a seven-segment
display module used to show the values of selected registers and the data bus.

The design is intended for educational purposes and demonstrates how basic
CPU components can be interconnected in VHDL.

## Files
- `cpu_pkg.vhd` – Common type and constant declarations.
- `register_file.vhd` – Four-register file implementation.
- `alu.vhd` – Simple arithmetic logic unit supporting ADD, SUB and AND.
- `controller.vhd` – Control unit and finite state machine that decodes
  instructions and coordinates operations.
- `sevenseg.vhd` – Seven‑segment display driver.
- `top.vhd` – Top-level entity that instantiates the components.

The design targets a simple 8‑bit data path. Instructions are 16 bits with a
4‑bit opcode and register fields for source and destination operands.
