#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 打印带颜色的消息
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装"
        return 1
    fi
    return 0
}

# 安装系统依赖
install_system_deps() {
    print_message "安装系统依赖..."
    sudo apt-get update
    sudo apt-get install -y build-essential pkg-config libssl-dev curl git wget
}

# 安装 Rust
install_rust() {
    if ! check_command rustc; then
        print_message "安装 Rust..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source $HOME/.cargo/env
    else
        print_message "Rust 已安装"
    fi
}

# 安装 Kafka
install_kafka() {
    if [ ! -d "kafka" ]; then
        print_message "安装 Kafka..."
        wget https://downloads.apache.org/kafka/3.6.1/kafka_2.13-3.6.1.tgz
        tar xzf kafka_2.13-3.6.1.tgz
        mv kafka_2.13-3.6.1 kafka
        rm kafka_2.13-3.6.1.tgz
    else
        print_message "Kafka 已安装"
    fi
}

# 安装 yellowstone-grpc-kafka
install_yellowstone() {
    if [ ! -d "yellowstone-grpc-kafka" ]; then
        print_message "安装 yellowstone-grpc-kafka..."
        git clone https://github.com/rpcpool/yellowstone-grpc-kafka.git
        cd yellowstone-grpc-kafka
        cargo build --release
        cd ..
    else
        print_message "yellowstone-grpc-kafka 已安装"
    fi
}

# 创建配置文件
create_configs() {
    print_message "创建配置文件..."
    
    # 创建 yellowstone-grpc-kafka 配置
    cat > yellowstone-grpc-kafka/config.json << EOF
{
  "grpc": {
    "bind_addr": "0.0.0.0:10000",
    "filters": {
      "accounts": {
        "max": 1000,
        "any": true
      },
      "slots": {
        "max": 1
      },
      "transactions": {
        "max": 1000,
        "any": true
      },
      "blocks": {
        "max": 1,
        "include_transactions": true,
        "include_accounts": true
      }
    }
  },
  "kafka": {
    "brokers": ["localhost:9092"],
    "topic_prefix": "solana"
  }
}
EOF

    # 创建启动脚本
    cat > start-services.sh << EOF
#!/bin/bash

# 启动 Zookeeper
echo "启动 Zookeeper..."
./kafka/bin/zookeeper-server-start.sh ./kafka/config/zookeeper.properties &

# 等待 Zookeeper 启动
sleep 5

# 启动 Kafka
echo "启动 Kafka..."
./kafka/bin/kafka-server-start.sh ./kafka/config/server.properties &

# 等待 Kafka 启动
sleep 5

# 启动 yellowstone-grpc-kafka
echo "启动 yellowstone-grpc-kafka..."
./yellowstone-grpc-kafka/target/release/yellowstone-grpc-kafka --config ./yellowstone-grpc-kafka/config.json
EOF

    chmod +x start-services.sh
}

# 安装 Python 依赖
install_python_deps() {
    print_message "安装 Python 依赖..."
    pip install -r requirements.txt
}

# 主函数
main() {
    print_message "开始安装..."
    
    # 检查 Python 版本
    if ! check_command python3; then
        print_error "请先安装 Python 3"
        exit 1
    fi
    
    # 检查 pip
    if ! check_command pip; then
        print_error "请先安装 pip"
        exit 1
    fi
    
    # 执行安装步骤
    install_system_deps
    install_rust
    install_kafka
    install_yellowstone
    create_configs
    install_python_deps
    
    print_message "安装完成！"
    print_message "使用 ./start-services.sh 启动服务"
}

# 执行主函数
main
