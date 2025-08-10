module dma_system (
    input sys_clk,
    input sys_rst_n,
    
    // CPU控制接口
    input [31:0] ctrl_addr,
    input [63:0] ctrl_wdata,
    output [63:0] ctrl_rdata,
    input ctrl_write,
    input ctrl_valid,
    output ctrl_ready,
    
    // 内存总线接口
    output [31:0] mem_addr,
    inout [63:0] mem_data,
    output mem_write,
    output mem_valid,
    input mem_ready,
    
    // DMA状态
    output [3:0] dma_channel_busy,
    output [3:0] dma_transfer_done,
    output [3:0] dma_transfer_error
);

//VCG_BEGIN
// # 复杂的线网生成规则 - 演示表达式和条件生成
// WiresRule("clk", "")                           
// WiresRule("rst_n", "")                         
// WiresRule("*_addr", "w_*_addr", "ADDR_WIDTH")
// WiresRule("*_data", "w_*_data", "DATA_WIDTH")
// WiresRule("*_valid", "w_*_vld")                    
// WiresRule("*_ready", "w_*_rdy")                    
// WiresRule("tie_low_*", "w_tie_low_*", "16", "16'h0000") 
// WiresRule("unused_*", "")                                
//
// # 生成所有输入信号的线网声明
// WiresDef("dma_channel.v", "dma_channel", "input", "lazy")
//VCG_END
//VCG_GEN_BEGIN_0
wire [ADDR_WIDTH-1:0] w_src_addr;
wire [ADDR_WIDTH-1:0] w_dst_addr;
wire [DATA_WIDTH-1:0] w_src_read_data;
wire           w_src_read_rdy;
wire           w_dst_write_rdy;
//VCG_GEN_END_0

//VCG_BEGIN
// # 使用Python变量和循环进行批量连接
// base_signals = ["src_addr", "dst_addr", "transfer_length", "start_transfer", 
//                 "transfer_done", "transfer_error", "channel_busy"]
//
// # 为每个DMA通道生成连接规则
// for ch in range(4):
//     # 通用信号连接
//     Connect("clk", "sys_clk")
//     Connect("rst_n", "sys_rst_n")
//     
//     # 通道特定信号连接 - 使用函数转换
//     Connect("src_read_addr", f"mem_ch{ch}_src_addr")
//     Connect("dst_write_addr", f"mem_ch{ch}_dst_addr") 
//     Connect("src_read_data", f"mem_ch{ch}_rdata")
//     Connect("dst_write_data", f"mem_ch{ch}_wdata")
//     Connect("src_*", f"mem_ch{ch}_${{*.upper()}}")
//     
//     # 状态信号聚合
//     Connect("channel_busy", f"dma_channel_busy[{ch}]")
//     Connect("transfer_done", f"dma_transfer_done[{ch}]")
//     Connect("transfer_error", f"dma_transfer_error[{ch}]")
//     
//     # 参数配置
//     ConnectParam("CHANNEL_ID", str(ch))
//     ConnectParam("ADDR_WIDTH", "32")
//     ConnectParam("DATA_WIDTH", "64")
//     ConnectParam("FIFO_DEPTH", "16")
//     
//     # 生成通道实例
//     Instance("dma_channel.v", "dma_channel", f"u_dma_ch{ch}")
//
//     print("")  # 在生成的代码中添加空行分隔
//VCG_END
//VCG_GEN_BEGIN_1
dma_channel #(
    .CHANNEL_ID        (0),
    .ADDR_WIDTH        (32),
    .DATA_WIDTH        (64),
    .FIFO_DEPTH        (16)
) u_dma_ch0 (
    .clk               (sys_clk),       // input
    .rst_n             (sys_rst_n),     // input
    .src_addr          (mem_ch0_ADDR),  // input [ADDR_WIDTH-1:0]
    .dst_addr          (dst_addr),      // input [ADDR_WIDTH-1:0]
    .transfer_length   (transfer_length),// input [15:0]
    .start_transfer    (start_transfer),// input
    .transfer_done     (dma_transfer_done[0]),// output
    .transfer_error    (dma_transfer_error[0]),// output
    .src_read_addr     (mem_ch0_READ_ADDR),// output [ADDR_WIDTH-1:0]
    .src_read_data     (mem_ch0_READ_DATA),// input [DATA_WIDTH-1:0]
    .src_read_valid    (mem_ch0_READ_VALID),// output
    .src_read_ready    (mem_ch0_READ_READY),// input
    .dst_write_addr    (mem_ch0_dst_addr),// output [ADDR_WIDTH-1:0]
    .dst_write_data    (mem_ch0_wdata), // output [DATA_WIDTH-1:0]
    .dst_write_valid   (dst_write_valid),// output
    .dst_write_ready   (dst_write_ready),// input
    .channel_busy      (dma_channel_busy[0]),// output
    .bytes_transferred (bytes_transferred)// output [15:0]
);

dma_channel #(
    .CHANNEL_ID        (1),
    .ADDR_WIDTH        (32),
    .DATA_WIDTH        (64),
    .FIFO_DEPTH        (16)
) u_dma_ch1 (
    .clk               (sys_clk),       // input
    .rst_n             (sys_rst_n),     // input
    .src_addr          (mem_ch1_ADDR),  // input [ADDR_WIDTH-1:0]
    .dst_addr          (dst_addr),      // input [ADDR_WIDTH-1:0]
    .transfer_length   (transfer_length),// input [15:0]
    .start_transfer    (start_transfer),// input
    .transfer_done     (dma_transfer_done[1]),// output
    .transfer_error    (dma_transfer_error[1]),// output
    .src_read_addr     (mem_ch1_READ_ADDR),// output [ADDR_WIDTH-1:0]
    .src_read_data     (mem_ch1_READ_DATA),// input [DATA_WIDTH-1:0]
    .src_read_valid    (mem_ch1_READ_VALID),// output
    .src_read_ready    (mem_ch1_READ_READY),// input
    .dst_write_addr    (mem_ch1_dst_addr),// output [ADDR_WIDTH-1:0]
    .dst_write_data    (mem_ch1_wdata), // output [DATA_WIDTH-1:0]
    .dst_write_valid   (dst_write_valid),// output
    .dst_write_ready   (dst_write_ready),// input
    .channel_busy      (dma_channel_busy[1]),// output
    .bytes_transferred (bytes_transferred)// output [15:0]
);

dma_channel #(
    .CHANNEL_ID        (2),
    .ADDR_WIDTH        (32),
    .DATA_WIDTH        (64),
    .FIFO_DEPTH        (16)
) u_dma_ch2 (
    .clk               (sys_clk),       // input
    .rst_n             (sys_rst_n),     // input
    .src_addr          (mem_ch2_ADDR),  // input [ADDR_WIDTH-1:0]
    .dst_addr          (dst_addr),      // input [ADDR_WIDTH-1:0]
    .transfer_length   (transfer_length),// input [15:0]
    .start_transfer    (start_transfer),// input
    .transfer_done     (dma_transfer_done[2]),// output
    .transfer_error    (dma_transfer_error[2]),// output
    .src_read_addr     (mem_ch2_READ_ADDR),// output [ADDR_WIDTH-1:0]
    .src_read_data     (mem_ch2_READ_DATA),// input [DATA_WIDTH-1:0]
    .src_read_valid    (mem_ch2_READ_VALID),// output
    .src_read_ready    (mem_ch2_READ_READY),// input
    .dst_write_addr    (mem_ch2_dst_addr),// output [ADDR_WIDTH-1:0]
    .dst_write_data    (mem_ch2_wdata), // output [DATA_WIDTH-1:0]
    .dst_write_valid   (dst_write_valid),// output
    .dst_write_ready   (dst_write_ready),// input
    .channel_busy      (dma_channel_busy[2]),// output
    .bytes_transferred (bytes_transferred)// output [15:0]
);

dma_channel #(
    .CHANNEL_ID        (3),
    .ADDR_WIDTH        (32),
    .DATA_WIDTH        (64),
    .FIFO_DEPTH        (16)
) u_dma_ch3 (
    .clk               (sys_clk),       // input
    .rst_n             (sys_rst_n),     // input
    .src_addr          (mem_ch3_ADDR),  // input [ADDR_WIDTH-1:0]
    .dst_addr          (dst_addr),      // input [ADDR_WIDTH-1:0]
    .transfer_length   (transfer_length),// input [15:0]
    .start_transfer    (start_transfer),// input
    .transfer_done     (dma_transfer_done[3]),// output
    .transfer_error    (dma_transfer_error[3]),// output
    .src_read_addr     (mem_ch3_READ_ADDR),// output [ADDR_WIDTH-1:0]
    .src_read_data     (mem_ch3_READ_DATA),// input [DATA_WIDTH-1:0]
    .src_read_valid    (mem_ch3_READ_VALID),// output
    .src_read_ready    (mem_ch3_READ_READY),// input
    .dst_write_addr    (mem_ch3_dst_addr),// output [ADDR_WIDTH-1:0]
    .dst_write_data    (mem_ch3_wdata), // output [DATA_WIDTH-1:0]
    .dst_write_valid   (dst_write_valid),// output
    .dst_write_ready   (dst_write_ready),// input
    .channel_busy      (dma_channel_busy[3]),// output
    .bytes_transferred (bytes_transferred)// output [15:0]
);
//VCG_GEN_END_1

endmodule