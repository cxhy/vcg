module uart_system (
    input sys_clk,
    input sys_rst_n,
    
    // 应用层接口
    input [7:0] app_tx_data,
    input app_tx_valid,
    output app_tx_ready,
    
    output [7:0] app_rx_data,
    output app_rx_valid,
    input app_rx_ready,
    
    // 物理接口
    output uart_tx_pin,
    input uart_rx_pin,
    
    // 状态指示
    output uart_tx_busy,
    output uart_rx_busy,
    output uart_error
);

//VCG_BEGIN
// # 基础连接规则 - 从通用到具体
// Connect("*", "uart_*")              
// Connect("clk", "sys_clk")           
// Connect("rst_n", "sys_rst_n")       
// Connect("tx_data", "app_tx_data")   
// Connect("tx_valid", "app_tx_valid") 
// Connect("tx_ready", "app_tx_ready") 
// Connect("rx_data", "app_rx_data")   
// Connect("rx_valid", "app_rx_valid") 
// Connect("rx_ready", "app_rx_ready") 
// Connect("uart_tx", "uart_tx_pin")   
// Connect("uart_rx", "uart_rx_pin")   
// Connect("frame_error", "uart_error")
//
// # 参数配置
// ConnectParam("BAUD_RATE", "115200")
// ConnectParam("DATA_WIDTH", "8")
// ConnectParam("STOP_BITS", "1")
//
// # 生成UART核心实例
// Instance("./uart_core.v", "uart_core", "u_uart_core")
//VCG_END
//VCG_GEN_BEGIN_0
uart_core #(
    .BAUD_RATE         (115200),
    .DATA_WIDTH        (8),
    .STOP_BITS         (1)
) u_uart_core (
    .clk               (sys_clk),       // input
    .rst_n             (sys_rst_n),     // input
    .tx_data           (app_tx_data),   // input [DATA_WIDTH-1:0]
    .tx_valid          (app_tx_valid),  // input
    .tx_ready          (app_tx_ready),  // output
    .uart_tx           (uart_tx_pin),   // output
    .rx_data           (app_rx_data),   // output [DATA_WIDTH-1:0]
    .rx_valid          (app_rx_valid),  // output
    .rx_ready          (app_rx_ready),  // input
    .uart_rx           (uart_rx_pin),   // input
    .tx_busy           (uart_tx_busy),  // output
    .rx_busy           (uart_rx_busy),  // output
    .frame_error       (uart_error)     // output
);
//VCG_GEN_END_0

endmodule