// sub_module.v - test submodule for VCG end-to-end testing
module sub_module #(
    parameter WIDTH = 8,
    parameter DEPTH = 16
) (
    input  wire                clk,
    input  wire                rst_n,
    input  wire [WIDTH-1:0]    data_in,
    output wire [WIDTH-1:0]    data_out,
    output wire                valid
);

    assign data_out = data_in;
    assign valid = 1'b1;

endmodule
