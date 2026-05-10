// test_top.v - top module for VCG end-to-end testing
module test_top (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  data_in,
    output wire [7:0]  data_out,
    output wire        valid
);

// Test 1: Basic Instance with Connect rules
//VCG_BEGIN
//Connect("clk", "sys_clk")
//Connect("rst_n", "sys_rst_n")
//Connect("data_*", "bus_*")
//ConnectParam("WIDTH", "8")
//Instance("sub_module.v", "sub_module", "u_sub_0")
//VCG_END
//VCG_GEN_BEGIN_0
sub_module #(
    .WIDTH             (8)
) u_sub_0 (
    .clk               (sys_clk),       // input
    .rst_n             (sys_rst_n),     // input
    .data_in           (bus_in),        // input [WIDTH - 1:0]
    .data_out          (bus_out),       // output [WIDTH - 1:0]
    .valid             (valid)          // output
);
//VCG_GEN_END_0

// Test 2: WiresDef generation
//VCG_BEGIN
//WiresDef("sub_module.v", "sub_module", "output")
//VCG_END
//VCG_GEN_BEGIN_1
wire [WIDTH-1:0] data_out;
wire           valid;
//VCG_GEN_END_1

endmodule
