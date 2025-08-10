module uart_core #(
    parameter BAUD_RATE = 9600,
    parameter DATA_WIDTH = 8,
    parameter STOP_BITS = 1
) (
    // 时钟和复位
    input clk,
    input rst_n,
    
    // 发送接口
    input [DATA_WIDTH-1:0] tx_data,
    input tx_valid,
    output tx_ready,
    output uart_tx,
    
    // 接收接口  
    output [DATA_WIDTH-1:0] rx_data,
    output rx_valid,
    input rx_ready,
    input uart_rx,
    
    // 状态指示
    output tx_busy,
    output rx_busy,
    output frame_error
);

// 模块实现代码...
// (这里省略具体实现)

endmodule