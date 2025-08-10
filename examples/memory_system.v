module memory_system (
    input sys_clk,
    input sys_rst_n,
    
    // CPU总线接口
    input [31:0] cpu_mem_addr,
    input [63:0] cpu_mem_wdata, 
    output [63:0] cpu_mem_rdata,
    input cpu_mem_valid,
    input cpu_mem_write,
    output cpu_mem_ready,
    
    // DDR物理接口
    output ddr_clk_p,
    output ddr_clk_n,
    output [13:0] ddr_addr,
    output [2:0] ddr_ba,
    inout [15:0] ddr_dq,
    output ddr_we_n,
    output ddr_cas_n,
    output ddr_ras_n
);

//VCG_BEGIN
// # 线网生成规则 - 演示复杂的线网管理
// WiresRule("mem_*", "sys_*")                                              
// WiresRule("ddr_*", "*")                       
// WiresRule("cpu_*", "w_cpu_*", "64")      
// WiresRule("*_addr", "w_*_address", "32")   
// WiresRule("*_valid", "w_*_vld")                
// WiresRule("*_ready", "w_*_rdy")                
//
// # 批量生成DDR控制器的输入线网（lazy模式）
// WiresDef("ddr_controller.v", "ddr_controller", "input", "lazy")
//VCG_END
//VCG_GEN_BEGIN_0
wire           sys_clk;
wire           sys_rst_n;
wire [31:0]    w_cpu_address;
wire [63:0]    w_cpu_wdata;
wire           w_cpu_vld;
wire [63:0]    w_cpu_write;
//VCG_GEN_END_0

//VCG_BEGIN
// # 信号连接规则 - 演示高级模式匹配
// Connect("mem_*", "sys_*")
// Connect("cpu_*", "${replace(*, 'cpu_', 'cpu_mem_')}")  
// Connect("ddr_*", "*")                                  
//
// # 参数配置 - 模式化参数设置
// ConnectParam("ADDR_WIDTH", "32")
// ConnectParam("DATA_WIDTH", "64") 
// ConnectParam("BURST_LENGTH", "8")
//
// # 实例化DDR控制器
// Instance("ddr_controller.v", "ddr_controller", "u_ddr_ctrl")
//VCG_END
//VCG_GEN_BEGIN_1
ddr_controller #(
    .ADDR_WIDTH        (32),
    .DATA_WIDTH        (64),
    .BURST_LENGTH      (8)
) u_ddr_ctrl (
    .mem_clk           (sys_clk),       // input
    .mem_rst_n         (sys_rst_n),     // input
    .cpu_addr          (addr),          // input [ADDR_WIDTH-1:0]
    .cpu_wdata         (wdata),         // input [DATA_WIDTH-1:0]
    .cpu_rdata         (rdata),         // output [DATA_WIDTH-1:0]
    .cpu_valid         (valid),         // input
    .cpu_write         (write),         // input
    .cpu_ready         (ready),         // output
    .ddr_clk_p         (clk_p),         // output
    .ddr_clk_n         (clk_n),         // output
    .ddr_addr          (addr),          // output [13:0]
    .ddr_ba            (ba),            // output [2:0]
    .ddr_dq            (dq),            // inout [15:0]
    .ddr_we_n          (we_n),          // output
    .ddr_cas_n         (cas_n),         // output
    .ddr_ras_n         (ras_n)          // output
);
//VCG_GEN_END_1

endmodule