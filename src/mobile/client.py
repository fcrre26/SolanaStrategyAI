"""
移动客户端示例
展示如何使用移动端存储和API分析功能
"""
import os
import json
import asyncio
import argparse
import logging
import time
from typing import Dict, List, Any, Optional

from .storage import init_storage, get_storage, analyze_wallet
from ..solana.collector import SolanaCollector

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.expanduser("~"), "solana_analyzer", "config.json")

# 硬编码的GRPC节点地址
DEFAULT_GRPC_ENDPOINT = "solana-yellowstone-grpc.publicnode.com:443"

# 监控中的币对列表(全局缓存)
monitored_pairs = {}

async def collect_and_store(wallet_address: str, rpc_url: str, days: int = 7, use_grpc: bool = False, grpc_endpoint: str = None):
    """
    从Solana收集交易并存储到移动设备
    
    Args:
        wallet_address: 钱包地址
        rpc_url: Solana RPC节点URL
        days: 收集多少天的交易数据
        use_grpc: 是否使用GRPC连接
        grpc_endpoint: GRPC节点地址
    """
    logger.info(f"开始收集钱包 {wallet_address} 的交易数据")
    
    # 初始化收集器
    collector_kwargs = {"rpc_url": rpc_url}
    if use_grpc:
        collector_kwargs["use_grpc"] = True
        collector_kwargs["grpc_endpoint"] = grpc_endpoint or DEFAULT_GRPC_ENDPOINT
        logger.info(f"使用GRPC节点: {collector_kwargs['grpc_endpoint']}")
    
    collector = SolanaCollector(**collector_kwargs)
    
    try:
        # 获取交易
        transactions = await collector.get_historical_transactions(wallet_address, days=days)
        logger.info(f"从链上获取了 {len(transactions)} 个交易")
        
        # 获取交换交易
        swap_txs = await collector.fetch_recent_swap_transactions(wallet_address, days=days)
        logger.info(f"其中交换交易有 {len(swap_txs)} 个")
        
        # 获取存储实例
        storage = get_storage()
        
        # 存储交易
        file_paths = storage.store_transactions(transactions, wallet_address)
        logger.info(f"已存储 {len(file_paths)} 个交易到移动设备")
        
        # 返回结果统计
        return {
            "wallet_address": wallet_address,
            "total_transactions": len(transactions),
            "swap_transactions": len(swap_txs),
            "stored_transactions": len(file_paths)
        }
    
    finally:
        # 关闭收集器
        await collector.close()

async def analyze_stored_data(wallet_address: str, days: int = 30, api_key: str = None):
    """
    分析存储在移动设备上的交易数据
    
    Args:
        wallet_address: 钱包地址
        days: 分析多少天的数据
        api_key: API密钥
    """
    # 初始化存储(如果提供了API密钥)
    if api_key:
        init_storage(api_key=api_key)
    
    logger.info(f"开始分析钱包 {wallet_address} 的交易数据")
    
    # 获取存储实例
    storage = get_storage()
    
    # 列出存储的交易
    transactions = storage.list_transactions(wallet_address, days)
    logger.info(f"移动设备上找到 {len(transactions)} 个交易")
    
    if not transactions:
        logger.warning("没有找到交易数据，无法分析")
        return None
    
    # 请求API分析
    analysis_result = await analyze_wallet(wallet_address, days)
    
    if analysis_result:
        logger.info("分析完成，结果已存储")
        return {
            "wallet_address": wallet_address,
            "analyzed_transactions": len(transactions),
            "analysis_result": analysis_result
        }
    else:
        logger.error("分析失败")
        return None

async def list_wallet_data(wallet_address: str = None):
    """
    列出存储在移动设备上的钱包数据
    
    Args:
        wallet_address: 钱包地址(如果为None，列出所有钱包)
    """
    storage = get_storage()
    
    # 获取存储信息
    storage_info = storage.get_storage_info()
    
    if wallet_address:
        # 列出特定钱包的信息
        wallet_found = False
        for wallet in storage_info["wallets"]:
            if wallet["address"] == wallet_address:
                wallet_found = True
                print(f"钱包: {wallet_address}")
                print(f"  交易数量: {wallet['transactions']}")
                print(f"  分析结果数量: {wallet['analyses']}")
                
                # 列出最近的交易
                transactions = storage.list_transactions(wallet_address, days=30)
                print(f"\n最近 30 天的交易 ({len(transactions)}):")
                for i, tx in enumerate(transactions[:5]):  # 只显示前5个
                    print(f"  {i+1}. {tx.get('transaction_id')} - {tx.get('timestamp')}")
                
                if len(transactions) > 5:
                    print(f"  ... 还有 {len(transactions) - 5} 个交易未显示")
                
                # 列出分析结果
                analyses = storage.list_analysis_results(wallet_address)
                print(f"\n分析结果 ({len(analyses)}):")
                for i, analysis in enumerate(analyses):
                    print(f"  {i+1}. {analysis.get('analysis_id')} - {analysis.get('timestamp')}")
                
                break
        
        if not wallet_found:
            print(f"未找到钱包 {wallet_address} 的数据")
    else:
        # 列出所有钱包的汇总信息
        print("存储信息:")
        print(f"  存储路径: {storage_info['base_dir']}")
        print(f"  钱包数量: {len(storage_info['wallets'])}")
        print(f"  总交易数量: {storage_info['total_transactions']}")
        print(f"  总分析结果数量: {storage_info['total_analyses']}")
        print(f"  存储大小: {storage_info['storage_size'] / 1024 / 1024:.2f} MB")
        
        print("\n钱包列表:")
        for i, wallet in enumerate(storage_info["wallets"]):
            print(f"  {i+1}. {wallet['address']} - 交易: {wallet['transactions']}, 分析: {wallet['analyses']}")

async def export_analysis_result(wallet_address: str, output_file: str = None):
    """
    导出分析结果
    
    Args:
        wallet_address: 钱包地址
        output_file: 输出文件路径(默认为当前目录下的wallet_analysis.json)
    """
    storage = get_storage()
    
    # 获取最新的分析结果
    analyses = storage.list_analysis_results(wallet_address, limit=1)
    
    if not analyses:
        logger.error(f"没有找到钱包 {wallet_address} 的分析结果")
        return False
    
    latest_analysis = analyses[0]
    
    # 设置输出文件路径
    if not output_file:
        output_file = f"{wallet_address}_analysis.json"
    
    # 写入文件
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(latest_analysis, f, indent=2, ensure_ascii=False)
        
        logger.info(f"分析结果已导出到: {output_file}")
        return True
    except Exception as e:
        logger.error(f"导出分析结果出错: {e}")
        return False

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件出错: {e}")
    return {
        "api_key": "",
        "api_endpoint": "https://ark.cn-beijing.volces.com/api/v3",
        "monitored_wallets": [],
        "use_grpc": True,
        "grpc_endpoint": DEFAULT_GRPC_ENDPOINT
    }

def save_config(config):
    """保存配置文件"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"保存配置文件出错: {e}")
        return False

async def interactive_menu():
    """交互式菜单"""
    # 加载配置
    config = load_config()
    
    while True:
        print("\n====== Solana交易分析工具 ======")
        print("1. 填写监听的地址")
        print("2. 录入API密钥和设置")
        print("3. 查看监听简报")
        print("4. 启动自动监控")
        print("5. 分析特定钱包")
        print("6. 导出分析结果")
        print("7. 实时监控交易")
        print("0. 退出")
        
        choice = input("\n请选择功能 (0-7): ")
        
        if choice == "1":
            await manage_wallet_addresses(config)
        elif choice == "2":
            update_api_key(config)
        elif choice == "3":
            await view_monitoring_report(config)
        elif choice == "4":
            await start_automatic_monitoring(config)
        elif choice == "5":
            await analyze_specific_wallet(config)
        elif choice == "6":
            await export_specific_analysis(config)
        elif choice == "7":
            await real_time_monitor(config)
        elif choice == "0":
            print("谢谢使用，再见！")
            break
        else:
            print("无效的选择，请重试")

async def manage_wallet_addresses(config):
    """管理监听的钱包地址"""
    while True:
        print("\n----- 监听地址管理 -----")
        print("当前监听的地址:")
        
        if not config.get("monitored_wallets"):
            print("  (无)")
        else:
            for i, wallet in enumerate(config["monitored_wallets"]):
                print(f"  {i+1}. {wallet}")
        
        print("\n操作选项:")
        print("1. 添加新地址")
        print("2. 删除地址")
        print("0. 返回主菜单")
        
        choice = input("\n请选择操作 (0-2): ")
        
        if choice == "1":
            wallet = input("请输入要添加的Solana钱包地址: ").strip()
            if wallet:
                if "monitored_wallets" not in config:
                    config["monitored_wallets"] = []
                if wallet not in config["monitored_wallets"]:
                    config["monitored_wallets"].append(wallet)
                    save_config(config)
                    print(f"已添加地址: {wallet}")
                else:
                    print("该地址已在监听列表中")
            else:
                print("地址不能为空")
        
        elif choice == "2":
            if not config.get("monitored_wallets"):
                print("没有要删除的地址")
                continue
                
            index = input("请输入要删除的地址编号: ")
            try:
                idx = int(index) - 1
                if 0 <= idx < len(config["monitored_wallets"]):
                    removed = config["monitored_wallets"].pop(idx)
                    save_config(config)
                    print(f"已删除地址: {removed}")
                else:
                    print("无效的编号")
            except ValueError:
                print("请输入有效的数字")
        
        elif choice == "0":
            break
        
        else:
            print("无效的选择，请重试")

def update_api_key(config):
    """更新API密钥"""
    print("\n----- API密钥设置 -----")
    print(f"当前API密钥: {config.get('api_key', '未设置')}")
    
    new_key = input("请输入新的API密钥 (保留空白则不变): ").strip()
    if new_key:
        config["api_key"] = new_key
        save_config(config)
        # 同时更新存储实例的API密钥
        init_storage(api_key=new_key)
        print("API密钥已更新")
    else:
        print("API密钥未变更")
    
    endpoint = input("请输入API端点 (保留空白则使用默认): ").strip()
    if endpoint:
        config["api_endpoint"] = endpoint
        save_config(config)
        # 同时更新存储实例的API端点
        init_storage(api_endpoint=endpoint)
        print("API端点已更新")
    
    print(f"\n----- GRPC设置 -----")
    print(f"当前使用GRPC: {'是' if config.get('use_grpc', True) else '否'}")
    print(f"当前GRPC节点: {config.get('grpc_endpoint', DEFAULT_GRPC_ENDPOINT)}")
    print("注意: GRPC节点默认使用 solana-yellowstone-grpc.publicnode.com:443")

async def view_monitoring_report(config):
    """查看监听简报"""
    print("\n----- 监听简报 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址")
        return
    
    storage = get_storage()
    
    for wallet in config["monitored_wallets"]:
        print(f"\n钱包: {wallet}")
        
        # 获取交易数据
        transactions = storage.list_transactions(wallet, days=30)
        print(f"  最近30天交易数: {len(transactions)}")
        
        # 获取分析结果
        analyses = storage.list_analysis_results(wallet, limit=1)
        if analyses:
            latest = analyses[0]
            print(f"  最新分析时间: {latest.get('timestamp')}")
            
            # 尝试提取主要交易模式
            result = latest.get("result", {})
            if "pattern_recognition" in result:
                pattern = result["pattern_recognition"].get("primary_pattern", "未知")
                print(f"  主要交易模式: {pattern}")
            
            # 尝试提取策略名称
            if "strategy" in result:
                strategy = result["strategy"].get("name", "未知")
                print(f"  推荐策略: {strategy}")
        else:
            print("  尚无分析结果")

async def start_automatic_monitoring(config):
    """启动自动监控"""
    print("\n----- 自动监控 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址，请先添加")
        return
    
    if not config.get("api_key"):
        print("未设置API密钥，无法进行分析")
        return
    
    # 设置RPC URL
    rpc_url = input("请输入Solana RPC URL (留空使用默认): ").strip()
    if not rpc_url:
        rpc_url = "https://api.mainnet-beta.solana.com"
    
    # 设置是否使用GRPC
    use_grpc = config.get("use_grpc", True)
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    print(f"使用GRPC连接: {'是' if use_grpc else '否'}")
    if use_grpc:
        print(f"GRPC节点: {grpc_endpoint}")
    
    # 设置监控间隔
    interval_str = input("请输入监控间隔(分钟，默认30): ").strip()
    try:
        interval = int(interval_str) if interval_str else 30
    except ValueError:
        print("无效的间隔，使用默认值30分钟")
        interval = 30
    
    # 设置监控时长
    duration_str = input("请输入监控时长(小时，默认24): ").strip()
    try:
        duration = int(duration_str) if duration_str else 24
    except ValueError:
        print("无效的时长，使用默认值24小时")
        duration = 24
    
    print(f"\n开始自动监控 {len(config['monitored_wallets'])} 个钱包...")
    print(f"监控间隔: {interval} 分钟")
    print(f"计划监控时长: {duration} 小时")
    print("按 Ctrl+C 停止监控")
    
    # 初始化存储
    init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 计算总循环次数
    total_cycles = (duration * 60) // interval
    current_cycle = 0
    
    try:
        while current_cycle < total_cycles:
            current_cycle += 1
            print(f"\n===== 监控周期 {current_cycle}/{total_cycles} =====")
            
            for wallet in config["monitored_wallets"]:
                print(f"\n监控钱包: {wallet}")
                
                # 收集数据
                try:
                    result = await collect_and_store(
                        wallet, 
                        rpc_url, 
                        days=1,  # 只收集最近1天的数据
                        use_grpc=use_grpc,
                        grpc_endpoint=grpc_endpoint
                    )
                    print(f"收集结果: 总交易 {result['total_transactions']}, 交换交易 {result['swap_transactions']}")
                    
                    # 分析数据
                    if result['total_transactions'] > 0:
                        analysis = await analyze_stored_data(wallet)
                        if analysis:
                            print("分析完成")
                        else:
                            print("分析失败或无数据")
                    else:
                        print("无新交易，跳过分析")
                        
                except Exception as e:
                    print(f"处理钱包 {wallet} 时出错: {e}")
            
            # 如果不是最后一个周期，则等待
            if current_cycle < total_cycles:
                print(f"\n等待 {interval} 分钟后开始下一轮监控...")
                await asyncio.sleep(interval * 60)
        
        print("\n监控完成！")
            
    except KeyboardInterrupt:
        print("\n监控已手动停止")

async def analyze_specific_wallet(config):
    """分析特定钱包"""
    print("\n----- 分析特定钱包 -----")
    
    # 检查API密钥
    if not config.get("api_key"):
        print("未设置API密钥，请先设置")
        return
    
    # 获取钱包地址
    wallet = input("请输入要分析的钱包地址: ").strip()
    if not wallet:
        print("钱包地址不能为空")
        return
    
    # 获取分析天数
    days_str = input("分析最近多少天的数据 (默认30): ").strip()
    try:
        days = int(days_str) if days_str else 30
    except ValueError:
        print("无效的天数，使用默认值30")
        days = 30
    
    # 设置RPC URL
    rpc_url = input("请输入Solana RPC URL (留空使用默认): ").strip()
    if not rpc_url:
        rpc_url = "https://api.mainnet-beta.solana.com"
    
    # 设置是否使用GRPC
    use_grpc = config.get("use_grpc", True)
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    print(f"使用GRPC连接: {'是' if use_grpc else '否'}")
    if use_grpc:
        print(f"GRPC节点: {grpc_endpoint}")
    
    print(f"\n开始分析钱包 {wallet}...")
    
    # 初始化存储和API密钥
    init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 收集数据
    try:
        print("正在收集交易数据...")
        result = await collect_and_store(
            wallet, 
            rpc_url, 
            days=days,
            use_grpc=use_grpc,
            grpc_endpoint=grpc_endpoint
        )
        print(f"收集完成，获取了 {result['total_transactions']} 个交易")
        
        if result['total_transactions'] > 0:
            print("正在分析数据...")
            analysis = await analyze_stored_data(wallet, days)
            
            if analysis and "analysis_result" in analysis:
                print("\n分析完成！")
                
                # 显示简要结果
                result = analysis["analysis_result"]
                if "pattern_recognition" in result:
                    pattern = result["pattern_recognition"].get("primary_pattern", "未知")
                    print(f"主要交易模式: {pattern}")
                
                if "strategy" in result:
                    strategy = result["strategy"]
                    print(f"策略名称: {strategy.get('name', '未知')}")
                    print(f"策略描述: {strategy.get('description', '未知')}")
                    
                    if "target_selection" in strategy:
                        criteria = strategy["target_selection"].get("criteria", [])
                        print(f"目标选择标准: {', '.join(criteria)}")
                    
                    if "risk_control" in strategy:
                        risk = strategy["risk_control"]
                        print(f"风险控制: 最大仓位 {risk.get('max_position_size', '未知')}, 最大日亏损 {risk.get('max_daily_loss', '未知')}")
                
                # 询问是否导出完整结果
                if input("\n是否导出完整分析结果？(y/n): ").lower() == 'y':
                    output_file = input("请输入输出文件名 (默认为 {wallet}_analysis.json): ").strip()
                    if not output_file:
                        output_file = f"{wallet}_analysis.json"
                    
                    if await export_analysis_result(wallet, output_file):
                        print(f"分析结果已导出到 {output_file}")
            else:
                print("分析失败或无数据")
        else:
            print("没有发现交易，无法分析")
            
    except Exception as e:
        print(f"处理钱包时出错: {e}")

async def export_specific_analysis(config):
    """导出特定分析结果"""
    print("\n----- 导出分析结果 -----")
    
    # 获取钱包地址
    wallet = input("请输入钱包地址: ").strip()
    if not wallet:
        print("钱包地址不能为空")
        return
    
    # 获取存储实例
    storage = get_storage()
    
    # 获取分析结果列表
    analyses = storage.list_analysis_results(wallet)
    
    if not analyses:
        print(f"未找到钱包 {wallet} 的分析结果")
        return
    
    print(f"\n找到 {len(analyses)} 个分析结果:")
    for i, analysis in enumerate(analyses):
        print(f"  {i+1}. {analysis.get('analysis_id')} - {analysis.get('timestamp')}")
    
    # 选择要导出的结果
    index_str = input("\n请选择要导出的结果编号 (默认1): ").strip()
    try:
        index = int(index_str) - 1 if index_str else 0
        if not (0 <= index < len(analyses)):
            print("无效的编号，使用最新的分析结果")
            index = 0
    except ValueError:
        print("无效的编号，使用最新的分析结果")
        index = 0
    
    # 获取输出文件名
    output_file = input("请输入输出文件名 (默认为 {wallet}_analysis.json): ").strip()
    if not output_file:
        output_file = f"{wallet}_analysis.json"
    
    # 导出结果
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analyses[index], f, indent=2, ensure_ascii=False)
        print(f"分析结果已导出到 {output_file}")
    except Exception as e:
        print(f"导出分析结果出错: {e}")

async def real_time_monitor(config):
    """
    实时监控钱包交易
    使用GRPC流式连接，实时接收和处理交易数据
    
    Args:
        config: 配置信息
    """
    print("\n----- 实时监控 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址，请先添加")
        return
    
    # 选择是否使用API分析
    use_api = False
    if config.get("api_key"):
        use_api_input = input("是否启用API分析? (y/n, 默认n): ").strip().lower()
        use_api = use_api_input == 'y'
    else:
        print("未设置API密钥，无法启用API分析")
    
    # 设置分析间隔(如果启用API分析)
    analysis_interval = 0
    if use_api:
        interval_str = input("设置分析间隔(小时，默认6): ").strip()
        try:
            analysis_interval = int(interval_str) if interval_str else 6
        except ValueError:
            print("无效的间隔，使用默认值6小时")
            analysis_interval = 6
    
    # 确保GRPC端点设置
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    
    print(f"\n开始实时监控 {len(config['monitored_wallets'])} 个钱包...")
    print(f"GRPC节点: {grpc_endpoint}")
    
    if use_api:
        print(f"API分析间隔: {analysis_interval}小时")
    else:
        print("API分析: 已禁用")
    
    print("按 Ctrl+C 停止监控")
    
    # 初始化存储
    storage = init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 初始化收集器(每个钱包一个收集器)
    collectors = {}
    callbacks = {}
    analysis_times = {}
    
    for wallet in config["monitored_wallets"]:
        # 创建收集器
        collectors[wallet] = SolanaCollector(
            use_grpc=True,
            grpc_endpoint=grpc_endpoint
        )
        
        # 创建交易处理回调
        callbacks[wallet] = create_transaction_callback(wallet, storage, use_api)
        
        # 初始化分析时间
        analysis_times[wallet] = time.time()
    
    try:
        # 启动监听
        tasks = []
        for wallet, collector in collectors.items():
            task = asyncio.create_task(
                monitor_wallet_transactions(
                    wallet, 
                    collector, 
                    callbacks[wallet], 
                    analysis_times, 
                    analysis_interval
                )
            )
            tasks.append(task)
        
        # 等待所有任务完成(实际上不会完成，除非发生错误或用户中断)
        await asyncio.gather(*tasks)
        
    except KeyboardInterrupt:
        print("\n监控已手动停止")
    except Exception as e:
        print(f"\n监控出错: {e}")
    finally:
        # 关闭所有收集器
        for wallet, collector in collectors.items():
            await collector.close()
            print(f"已关闭钱包 {wallet} 的监控")

def create_transaction_callback(wallet_address, storage, use_api):
    """
    创建交易处理回调函数
    
    Args:
        wallet_address: 钱包地址
        storage: 存储实例
        use_api: 是否使用API分析
        
    Returns:
        回调函数
    """
    async def callback(tx_data):
        try:
            # 打印交易信息
            tx_hash = tx_data.get("transaction_id", "unknown")
            timestamp = tx_data.get("timestamp", "unknown")
            success = "成功" if tx_data.get("success", False) else "失败"
            
            # 识别交易类型
            tx_type = "普通"
            if tx_data.get("is_swap", False):
                tx_type = "交换"
            elif tx_data.get("is_liquidity", False):
                tx_type = "流动性"
            elif tx_data.get("is_stake", False):
                tx_type = "质押"
            
            print(f"\n接收到 {wallet_address} 的{tx_type}交易: {tx_hash}")
            print(f"  时间: {timestamp}")
            print(f"  状态: {success}")
            
            # 提取交易对信息
            if tx_data.get("is_swap", False) and "swap_info" in tx_data:
                swap_info = tx_data["swap_info"]
                input_token = swap_info.get("input_token_symbol", "未知")
                output_token = swap_info.get("output_token_symbol", "未知")
                input_amount = swap_info.get("input_amount", 0)
                output_amount = swap_info.get("output_amount", 0)
                
                print(f"  交易: {input_amount} {input_token} -> {output_amount} {output_token}")
                
                # 更新全局监控的交易对
                token_pair = f"{input_token}/{output_token}"
                global monitored_pairs
                
                if token_pair not in monitored_pairs:
                    monitored_pairs[token_pair] = {
                        "start_time": time.time(),
                        "last_activity": time.time(),
                        "last_analysis": 0,
                        "transactions": [],
                        "pool_states": [],
                        "market_data": [],
                        "routes": []
                    }
                else:
                    monitored_pairs[token_pair]["last_activity"] = time.time()
                
                monitored_pairs[token_pair]["transactions"].append(tx_data)
            
            # 存储交易数据
            storage.store_transaction(tx_data, wallet_address)
            print(f"  已存储交易数据")
            
        except Exception as e:
            print(f"处理交易时出错: {e}")
    
    return callback

async def monitor_wallet_transactions(wallet_address, collector, callback, analysis_times, analysis_interval):
    """
    持续监控钱包交易
    
    Args:
        wallet_address: 钱包地址
        collector: 收集器实例
        callback: 交易处理回调
        analysis_times: 上次分析时间字典
        analysis_interval: 分析间隔(小时)
    """
    print(f"开始监控钱包 {wallet_address} 的交易...")
    
    # 监听新交易
    await collector.listen_for_transactions(wallet_address, callback)
    
    # 注意：由于listen_for_transactions是一个阻塞调用，
    # 以下代码只会在监听结束后执行，这里添加是为了保持完整性
    print(f"钱包 {wallet_address} 的监控已结束")

async def perform_periodic_analysis(wallet_address, storage, analysis_times, analysis_interval):
    """
    定期执行分析
    
    Args:
        wallet_address: 钱包地址
        storage: 存储实例
        analysis_times: 上次分析时间字典
        analysis_interval: 分析间隔(小时)
    """
    current_time = time.time()
    last_analysis = analysis_times.get(wallet_address, 0)
    
    # 检查是否需要分析
    if analysis_interval > 0 and (current_time - last_analysis) >= (analysis_interval * 3600):
        print(f"\n开始分析钱包 {wallet_address} 的交易...")
        
        # 执行分析
        analysis_result = await analyze_wallet(wallet_address)
        
        if analysis_result:
            print(f"分析完成: {wallet_address}")
        else:
            print(f"分析失败: {wallet_address}")
        
        # 更新分析时间
        analysis_times[wallet_address] = current_time

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Solana交易分析移动客户端")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 收集命令
    collect_parser = subparsers.add_parser("collect", help="收集并存储交易数据")
    collect_parser.add_argument("wallet", help="钱包地址")
    collect_parser.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC节点URL")
    collect_parser.add_argument("--days", type=int, default=7, help="收集多少天的数据")
    collect_parser.add_argument("--use-grpc", action="store_true", help="使用GRPC连接")
    collect_parser.add_argument("--grpc-endpoint", default=DEFAULT_GRPC_ENDPOINT, help="GRPC节点地址")
    
    # 分析命令
    analyze_parser = subparsers.add_parser("analyze", help="分析存储的交易数据")
    analyze_parser.add_argument("wallet", help="钱包地址")
    analyze_parser.add_argument("--days", type=int, default=30, help="分析多少天的数据")
    analyze_parser.add_argument("--api-key", help="API密钥")
    
    # 列出命令
    list_parser = subparsers.add_parser("list", help="列出存储的数据")
    list_parser.add_argument("--wallet", help="钱包地址(可选)")
    
    # 导出命令
    export_parser = subparsers.add_parser("export", help="导出分析结果")
    export_parser.add_argument("wallet", help="钱包地址")
    export_parser.add_argument("--output", help="输出文件路径")
    
    # 初始化命令
    init_parser = subparsers.add_parser("init", help="初始化存储")
    init_parser.add_argument("--dir", help="基础存储目录")
    init_parser.add_argument("--api-endpoint", help="API分析端点")
    init_parser.add_argument("--api-key", help="API访问密钥")
    
    # 交互式菜单
    menu_parser = subparsers.add_parser("menu", help="启动交互式菜单")
    
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_arguments()
    
    # 检查命令
    if args.command == "collect":
        result = await collect_and_store(args.wallet, args.rpc, args.days, args.use_grpc, args.grpc_endpoint)
        print(json.dumps(result, indent=2))
    
    elif args.command == "analyze":
        result = await analyze_stored_data(args.wallet, args.days, args.api_key)
        if result:
            # 仅打印分析结果概要，避免输出过多内容
            summary = {
                "wallet_address": result["wallet_address"],
                "analyzed_transactions": result["analyzed_transactions"],
            }
            if "analysis_result" in result and isinstance(result["analysis_result"], dict):
                if "pattern_recognition" in result["analysis_result"]:
                    summary["primary_pattern"] = result["analysis_result"]["pattern_recognition"].get("primary_pattern")
                if "strategy" in result["analysis_result"]:
                    summary["strategy_name"] = result["analysis_result"]["strategy"].get("name")
            print(json.dumps(summary, indent=2))
    
    elif args.command == "list":
        await list_wallet_data(args.wallet)
    
    elif args.command == "export":
        success = await export_analysis_result(args.wallet, args.output)
        if success:
            print("分析结果导出成功")
        else:
            print("分析结果导出失败")
    
    elif args.command == "init":
        init_storage(args.dir, args.api_endpoint, args.api_key)
        print("存储初始化完成")
    
    elif args.command == "menu" or args.command is None:
        await interactive_menu()
    
    else:
        print("请指定命令: collect, analyze, list, export, init 或 menu")

if __name__ == "__main__":
    asyncio.run(main()) 
移动客户端示例
展示如何使用移动端存储和API分析功能
"""
import os
import json
import asyncio
import argparse
import logging
import time
from typing import Dict, List, Any, Optional

from .storage import init_storage, get_storage, analyze_wallet
from ..solana.collector import SolanaCollector

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.expanduser("~"), "solana_analyzer", "config.json")

# 硬编码的GRPC节点地址
DEFAULT_GRPC_ENDPOINT = "solana-yellowstone-grpc.publicnode.com:443"

# 监控中的币对列表(全局缓存)
monitored_pairs = {}

async def collect_and_store(wallet_address: str, rpc_url: str, days: int = 7, use_grpc: bool = False, grpc_endpoint: str = None):
    """
    从Solana收集交易并存储到移动设备
    
    Args:
        wallet_address: 钱包地址
        rpc_url: Solana RPC节点URL
        days: 收集多少天的交易数据
        use_grpc: 是否使用GRPC连接
        grpc_endpoint: GRPC节点地址
    """
    logger.info(f"开始收集钱包 {wallet_address} 的交易数据")
    
    # 初始化收集器
    collector_kwargs = {"rpc_url": rpc_url}
    if use_grpc:
        collector_kwargs["use_grpc"] = True
        collector_kwargs["grpc_endpoint"] = grpc_endpoint or DEFAULT_GRPC_ENDPOINT
        logger.info(f"使用GRPC节点: {collector_kwargs['grpc_endpoint']}")
    
    collector = SolanaCollector(**collector_kwargs)
    
    try:
        # 获取交易
        transactions = await collector.get_historical_transactions(wallet_address, days=days)
        logger.info(f"从链上获取了 {len(transactions)} 个交易")
        
        # 获取交换交易
        swap_txs = await collector.fetch_recent_swap_transactions(wallet_address, days=days)
        logger.info(f"其中交换交易有 {len(swap_txs)} 个")
        
        # 获取存储实例
        storage = get_storage()
        
        # 存储交易
        file_paths = storage.store_transactions(transactions, wallet_address)
        logger.info(f"已存储 {len(file_paths)} 个交易到移动设备")
        
        # 返回结果统计
        return {
            "wallet_address": wallet_address,
            "total_transactions": len(transactions),
            "swap_transactions": len(swap_txs),
            "stored_transactions": len(file_paths)
        }
    
    finally:
        # 关闭收集器
        await collector.close()

async def analyze_stored_data(wallet_address: str, days: int = 30, api_key: str = None):
    """
    分析存储在移动设备上的交易数据
    
    Args:
        wallet_address: 钱包地址
        days: 分析多少天的数据
        api_key: API密钥
    """
    # 初始化存储(如果提供了API密钥)
    if api_key:
        init_storage(api_key=api_key)
    
    logger.info(f"开始分析钱包 {wallet_address} 的交易数据")
    
    # 获取存储实例
    storage = get_storage()
    
    # 列出存储的交易
    transactions = storage.list_transactions(wallet_address, days)
    logger.info(f"移动设备上找到 {len(transactions)} 个交易")
    
    if not transactions:
        logger.warning("没有找到交易数据，无法分析")
        return None
    
    # 请求API分析
    analysis_result = await analyze_wallet(wallet_address, days)
    
    if analysis_result:
        logger.info("分析完成，结果已存储")
        return {
            "wallet_address": wallet_address,
            "analyzed_transactions": len(transactions),
            "analysis_result": analysis_result
        }
    else:
        logger.error("分析失败")
        return None

async def list_wallet_data(wallet_address: str = None):
    """
    列出存储在移动设备上的钱包数据
    
    Args:
        wallet_address: 钱包地址(如果为None，列出所有钱包)
    """
    storage = get_storage()
    
    # 获取存储信息
    storage_info = storage.get_storage_info()
    
    if wallet_address:
        # 列出特定钱包的信息
        wallet_found = False
        for wallet in storage_info["wallets"]:
            if wallet["address"] == wallet_address:
                wallet_found = True
                print(f"钱包: {wallet_address}")
                print(f"  交易数量: {wallet['transactions']}")
                print(f"  分析结果数量: {wallet['analyses']}")
                
                # 列出最近的交易
                transactions = storage.list_transactions(wallet_address, days=30)
                print(f"\n最近 30 天的交易 ({len(transactions)}):")
                for i, tx in enumerate(transactions[:5]):  # 只显示前5个
                    print(f"  {i+1}. {tx.get('transaction_id')} - {tx.get('timestamp')}")
                
                if len(transactions) > 5:
                    print(f"  ... 还有 {len(transactions) - 5} 个交易未显示")
                
                # 列出分析结果
                analyses = storage.list_analysis_results(wallet_address)
                print(f"\n分析结果 ({len(analyses)}):")
                for i, analysis in enumerate(analyses):
                    print(f"  {i+1}. {analysis.get('analysis_id')} - {analysis.get('timestamp')}")
                
                break
        
        if not wallet_found:
            print(f"未找到钱包 {wallet_address} 的数据")
    else:
        # 列出所有钱包的汇总信息
        print("存储信息:")
        print(f"  存储路径: {storage_info['base_dir']}")
        print(f"  钱包数量: {len(storage_info['wallets'])}")
        print(f"  总交易数量: {storage_info['total_transactions']}")
        print(f"  总分析结果数量: {storage_info['total_analyses']}")
        print(f"  存储大小: {storage_info['storage_size'] / 1024 / 1024:.2f} MB")
        
        print("\n钱包列表:")
        for i, wallet in enumerate(storage_info["wallets"]):
            print(f"  {i+1}. {wallet['address']} - 交易: {wallet['transactions']}, 分析: {wallet['analyses']}")

async def export_analysis_result(wallet_address: str, output_file: str = None):
    """
    导出分析结果
    
    Args:
        wallet_address: 钱包地址
        output_file: 输出文件路径(默认为当前目录下的wallet_analysis.json)
    """
    storage = get_storage()
    
    # 获取最新的分析结果
    analyses = storage.list_analysis_results(wallet_address, limit=1)
    
    if not analyses:
        logger.error(f"没有找到钱包 {wallet_address} 的分析结果")
        return False
    
    latest_analysis = analyses[0]
    
    # 设置输出文件路径
    if not output_file:
        output_file = f"{wallet_address}_analysis.json"
    
    # 写入文件
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(latest_analysis, f, indent=2, ensure_ascii=False)
        
        logger.info(f"分析结果已导出到: {output_file}")
        return True
    except Exception as e:
        logger.error(f"导出分析结果出错: {e}")
        return False

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件出错: {e}")
    return {
        "api_key": "",
        "api_endpoint": "https://ark.cn-beijing.volces.com/api/v3",
        "monitored_wallets": [],
        "use_grpc": True,
        "grpc_endpoint": DEFAULT_GRPC_ENDPOINT
    }

def save_config(config):
    """保存配置文件"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"保存配置文件出错: {e}")
        return False

async def interactive_menu():
    """交互式菜单"""
    # 加载配置
    config = load_config()
    
    while True:
        print("\n====== Solana交易分析工具 ======")
        print("1. 填写监听的地址")
        print("2. 录入API密钥和设置")
        print("3. 查看监听简报")
        print("4. 启动自动监控")
        print("5. 分析特定钱包")
        print("6. 导出分析结果")
        print("7. 实时监控交易")
        print("0. 退出")
        
        choice = input("\n请选择功能 (0-7): ")
        
        if choice == "1":
            await manage_wallet_addresses(config)
        elif choice == "2":
            update_api_key(config)
        elif choice == "3":
            await view_monitoring_report(config)
        elif choice == "4":
            await start_automatic_monitoring(config)
        elif choice == "5":
            await analyze_specific_wallet(config)
        elif choice == "6":
            await export_specific_analysis(config)
        elif choice == "7":
            await real_time_monitor(config)
        elif choice == "0":
            print("谢谢使用，再见！")
            break
        else:
            print("无效的选择，请重试")

async def manage_wallet_addresses(config):
    """管理监听的钱包地址"""
    while True:
        print("\n----- 监听地址管理 -----")
        print("当前监听的地址:")
        
        if not config.get("monitored_wallets"):
            print("  (无)")
        else:
            for i, wallet in enumerate(config["monitored_wallets"]):
                print(f"  {i+1}. {wallet}")
        
        print("\n操作选项:")
        print("1. 添加新地址")
        print("2. 删除地址")
        print("0. 返回主菜单")
        
        choice = input("\n请选择操作 (0-2): ")
        
        if choice == "1":
            wallet = input("请输入要添加的Solana钱包地址: ").strip()
            if wallet:
                if "monitored_wallets" not in config:
                    config["monitored_wallets"] = []
                if wallet not in config["monitored_wallets"]:
                    config["monitored_wallets"].append(wallet)
                    save_config(config)
                    print(f"已添加地址: {wallet}")
                else:
                    print("该地址已在监听列表中")
            else:
                print("地址不能为空")
        
        elif choice == "2":
            if not config.get("monitored_wallets"):
                print("没有要删除的地址")
                continue
                
            index = input("请输入要删除的地址编号: ")
            try:
                idx = int(index) - 1
                if 0 <= idx < len(config["monitored_wallets"]):
                    removed = config["monitored_wallets"].pop(idx)
                    save_config(config)
                    print(f"已删除地址: {removed}")
                else:
                    print("无效的编号")
            except ValueError:
                print("请输入有效的数字")
        
        elif choice == "0":
            break
        
        else:
            print("无效的选择，请重试")

def update_api_key(config):
    """更新API密钥"""
    print("\n----- API密钥设置 -----")
    print(f"当前API密钥: {config.get('api_key', '未设置')}")
    
    new_key = input("请输入新的API密钥 (保留空白则不变): ").strip()
    if new_key:
        config["api_key"] = new_key
        save_config(config)
        # 同时更新存储实例的API密钥
        init_storage(api_key=new_key)
        print("API密钥已更新")
    else:
        print("API密钥未变更")
    
    endpoint = input("请输入API端点 (保留空白则使用默认): ").strip()
    if endpoint:
        config["api_endpoint"] = endpoint
        save_config(config)
        # 同时更新存储实例的API端点
        init_storage(api_endpoint=endpoint)
        print("API端点已更新")
    
    print(f"\n----- GRPC设置 -----")
    print(f"当前使用GRPC: {'是' if config.get('use_grpc', True) else '否'}")
    print(f"当前GRPC节点: {config.get('grpc_endpoint', DEFAULT_GRPC_ENDPOINT)}")
    print("注意: GRPC节点默认使用 solana-yellowstone-grpc.publicnode.com:443")

async def view_monitoring_report(config):
    """查看监听简报"""
    print("\n----- 监听简报 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址")
        return
    
    storage = get_storage()
    
    for wallet in config["monitored_wallets"]:
        print(f"\n钱包: {wallet}")
        
        # 获取交易数据
        transactions = storage.list_transactions(wallet, days=30)
        print(f"  最近30天交易数: {len(transactions)}")
        
        # 获取分析结果
        analyses = storage.list_analysis_results(wallet, limit=1)
        if analyses:
            latest = analyses[0]
            print(f"  最新分析时间: {latest.get('timestamp')}")
            
            # 尝试提取主要交易模式
            result = latest.get("result", {})
            if "pattern_recognition" in result:
                pattern = result["pattern_recognition"].get("primary_pattern", "未知")
                print(f"  主要交易模式: {pattern}")
            
            # 尝试提取策略名称
            if "strategy" in result:
                strategy = result["strategy"].get("name", "未知")
                print(f"  推荐策略: {strategy}")
        else:
            print("  尚无分析结果")

async def start_automatic_monitoring(config):
    """启动自动监控"""
    print("\n----- 自动监控 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址，请先添加")
        return
    
    if not config.get("api_key"):
        print("未设置API密钥，无法进行分析")
        return
    
    # 设置RPC URL
    rpc_url = input("请输入Solana RPC URL (留空使用默认): ").strip()
    if not rpc_url:
        rpc_url = "https://api.mainnet-beta.solana.com"
    
    # 设置是否使用GRPC
    use_grpc = config.get("use_grpc", True)
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    print(f"使用GRPC连接: {'是' if use_grpc else '否'}")
    if use_grpc:
        print(f"GRPC节点: {grpc_endpoint}")
    
    # 设置监控间隔
    interval_str = input("请输入监控间隔(分钟，默认30): ").strip()
    try:
        interval = int(interval_str) if interval_str else 30
    except ValueError:
        print("无效的间隔，使用默认值30分钟")
        interval = 30
    
    # 设置监控时长
    duration_str = input("请输入监控时长(小时，默认24): ").strip()
    try:
        duration = int(duration_str) if duration_str else 24
    except ValueError:
        print("无效的时长，使用默认值24小时")
        duration = 24
    
    print(f"\n开始自动监控 {len(config['monitored_wallets'])} 个钱包...")
    print(f"监控间隔: {interval} 分钟")
    print(f"计划监控时长: {duration} 小时")
    print("按 Ctrl+C 停止监控")
    
    # 初始化存储
    init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 计算总循环次数
    total_cycles = (duration * 60) // interval
    current_cycle = 0
    
    try:
        while current_cycle < total_cycles:
            current_cycle += 1
            print(f"\n===== 监控周期 {current_cycle}/{total_cycles} =====")
            
            for wallet in config["monitored_wallets"]:
                print(f"\n监控钱包: {wallet}")
                
                # 收集数据
                try:
                    result = await collect_and_store(
                        wallet, 
                        rpc_url, 
                        days=1,  # 只收集最近1天的数据
                        use_grpc=use_grpc,
                        grpc_endpoint=grpc_endpoint
                    )
                    print(f"收集结果: 总交易 {result['total_transactions']}, 交换交易 {result['swap_transactions']}")
                    
                    # 分析数据
                    if result['total_transactions'] > 0:
                        analysis = await analyze_stored_data(wallet)
                        if analysis:
                            print("分析完成")
                        else:
                            print("分析失败或无数据")
                    else:
                        print("无新交易，跳过分析")
                        
                except Exception as e:
                    print(f"处理钱包 {wallet} 时出错: {e}")
            
            # 如果不是最后一个周期，则等待
            if current_cycle < total_cycles:
                print(f"\n等待 {interval} 分钟后开始下一轮监控...")
                await asyncio.sleep(interval * 60)
        
        print("\n监控完成！")
            
    except KeyboardInterrupt:
        print("\n监控已手动停止")

async def analyze_specific_wallet(config):
    """分析特定钱包"""
    print("\n----- 分析特定钱包 -----")
    
    # 检查API密钥
    if not config.get("api_key"):
        print("未设置API密钥，请先设置")
        return
    
    # 获取钱包地址
    wallet = input("请输入要分析的钱包地址: ").strip()
    if not wallet:
        print("钱包地址不能为空")
        return
    
    # 获取分析天数
    days_str = input("分析最近多少天的数据 (默认30): ").strip()
    try:
        days = int(days_str) if days_str else 30
    except ValueError:
        print("无效的天数，使用默认值30")
        days = 30
    
    # 设置RPC URL
    rpc_url = input("请输入Solana RPC URL (留空使用默认): ").strip()
    if not rpc_url:
        rpc_url = "https://api.mainnet-beta.solana.com"
    
    # 设置是否使用GRPC
    use_grpc = config.get("use_grpc", True)
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    print(f"使用GRPC连接: {'是' if use_grpc else '否'}")
    if use_grpc:
        print(f"GRPC节点: {grpc_endpoint}")
    
    print(f"\n开始分析钱包 {wallet}...")
    
    # 初始化存储和API密钥
    init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 收集数据
    try:
        print("正在收集交易数据...")
        result = await collect_and_store(
            wallet, 
            rpc_url, 
            days=days,
            use_grpc=use_grpc,
            grpc_endpoint=grpc_endpoint
        )
        print(f"收集完成，获取了 {result['total_transactions']} 个交易")
        
        if result['total_transactions'] > 0:
            print("正在分析数据...")
            analysis = await analyze_stored_data(wallet, days)
            
            if analysis and "analysis_result" in analysis:
                print("\n分析完成！")
                
                # 显示简要结果
                result = analysis["analysis_result"]
                if "pattern_recognition" in result:
                    pattern = result["pattern_recognition"].get("primary_pattern", "未知")
                    print(f"主要交易模式: {pattern}")
                
                if "strategy" in result:
                    strategy = result["strategy"]
                    print(f"策略名称: {strategy.get('name', '未知')}")
                    print(f"策略描述: {strategy.get('description', '未知')}")
                    
                    if "target_selection" in strategy:
                        criteria = strategy["target_selection"].get("criteria", [])
                        print(f"目标选择标准: {', '.join(criteria)}")
                    
                    if "risk_control" in strategy:
                        risk = strategy["risk_control"]
                        print(f"风险控制: 最大仓位 {risk.get('max_position_size', '未知')}, 最大日亏损 {risk.get('max_daily_loss', '未知')}")
                
                # 询问是否导出完整结果
                if input("\n是否导出完整分析结果？(y/n): ").lower() == 'y':
                    output_file = input("请输入输出文件名 (默认为 {wallet}_analysis.json): ").strip()
                    if not output_file:
                        output_file = f"{wallet}_analysis.json"
                    
                    if await export_analysis_result(wallet, output_file):
                        print(f"分析结果已导出到 {output_file}")
            else:
                print("分析失败或无数据")
        else:
            print("没有发现交易，无法分析")
            
    except Exception as e:
        print(f"处理钱包时出错: {e}")

async def export_specific_analysis(config):
    """导出特定分析结果"""
    print("\n----- 导出分析结果 -----")
    
    # 获取钱包地址
    wallet = input("请输入钱包地址: ").strip()
    if not wallet:
        print("钱包地址不能为空")
        return
    
    # 获取存储实例
    storage = get_storage()
    
    # 获取分析结果列表
    analyses = storage.list_analysis_results(wallet)
    
    if not analyses:
        print(f"未找到钱包 {wallet} 的分析结果")
        return
    
    print(f"\n找到 {len(analyses)} 个分析结果:")
    for i, analysis in enumerate(analyses):
        print(f"  {i+1}. {analysis.get('analysis_id')} - {analysis.get('timestamp')}")
    
    # 选择要导出的结果
    index_str = input("\n请选择要导出的结果编号 (默认1): ").strip()
    try:
        index = int(index_str) - 1 if index_str else 0
        if not (0 <= index < len(analyses)):
            print("无效的编号，使用最新的分析结果")
            index = 0
    except ValueError:
        print("无效的编号，使用最新的分析结果")
        index = 0
    
    # 获取输出文件名
    output_file = input("请输入输出文件名 (默认为 {wallet}_analysis.json): ").strip()
    if not output_file:
        output_file = f"{wallet}_analysis.json"
    
    # 导出结果
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analyses[index], f, indent=2, ensure_ascii=False)
        print(f"分析结果已导出到 {output_file}")
    except Exception as e:
        print(f"导出分析结果出错: {e}")

async def real_time_monitor(config):
    """
    实时监控钱包交易
    使用GRPC流式连接，实时接收和处理交易数据
    
    Args:
        config: 配置信息
    """
    print("\n----- 实时监控 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址，请先添加")
        return
    
    # 选择是否使用API分析
    use_api = False
    if config.get("api_key"):
        use_api_input = input("是否启用API分析? (y/n, 默认n): ").strip().lower()
        use_api = use_api_input == 'y'
    else:
        print("未设置API密钥，无法启用API分析")
    
    # 设置分析间隔(如果启用API分析)
    analysis_interval = 0
    if use_api:
        interval_str = input("设置分析间隔(小时，默认6): ").strip()
        try:
            analysis_interval = int(interval_str) if interval_str else 6
        except ValueError:
            print("无效的间隔，使用默认值6小时")
            analysis_interval = 6
    
    # 确保GRPC端点设置
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    
    print(f"\n开始实时监控 {len(config['monitored_wallets'])} 个钱包...")
    print(f"GRPC节点: {grpc_endpoint}")
    
    if use_api:
        print(f"API分析间隔: {analysis_interval}小时")
    else:
        print("API分析: 已禁用")
    
    print("按 Ctrl+C 停止监控")
    
    # 初始化存储
    storage = init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 初始化收集器(每个钱包一个收集器)
    collectors = {}
    callbacks = {}
    analysis_times = {}
    
    for wallet in config["monitored_wallets"]:
        # 创建收集器
        collectors[wallet] = SolanaCollector(
            use_grpc=True,
            grpc_endpoint=grpc_endpoint
        )
        
        # 创建交易处理回调
        callbacks[wallet] = create_transaction_callback(wallet, storage, use_api)
        
        # 初始化分析时间
        analysis_times[wallet] = time.time()
    
    try:
        # 启动监听
        tasks = []
        for wallet, collector in collectors.items():
            task = asyncio.create_task(
                monitor_wallet_transactions(
                    wallet, 
                    collector, 
                    callbacks[wallet], 
                    analysis_times, 
                    analysis_interval
                )
            )
            tasks.append(task)
        
        # 等待所有任务完成(实际上不会完成，除非发生错误或用户中断)
        await asyncio.gather(*tasks)
        
    except KeyboardInterrupt:
        print("\n监控已手动停止")
    except Exception as e:
        print(f"\n监控出错: {e}")
    finally:
        # 关闭所有收集器
        for wallet, collector in collectors.items():
            await collector.close()
            print(f"已关闭钱包 {wallet} 的监控")

def create_transaction_callback(wallet_address, storage, use_api):
    """
    创建交易处理回调函数
    
    Args:
        wallet_address: 钱包地址
        storage: 存储实例
        use_api: 是否使用API分析
        
    Returns:
        回调函数
    """
    async def callback(tx_data):
        try:
            # 打印交易信息
            tx_hash = tx_data.get("transaction_id", "unknown")
            timestamp = tx_data.get("timestamp", "unknown")
            success = "成功" if tx_data.get("success", False) else "失败"
            
            # 识别交易类型
            tx_type = "普通"
            if tx_data.get("is_swap", False):
                tx_type = "交换"
            elif tx_data.get("is_liquidity", False):
                tx_type = "流动性"
            elif tx_data.get("is_stake", False):
                tx_type = "质押"
            
            print(f"\n接收到 {wallet_address} 的{tx_type}交易: {tx_hash}")
            print(f"  时间: {timestamp}")
            print(f"  状态: {success}")
            
            # 提取交易对信息
            if tx_data.get("is_swap", False) and "swap_info" in tx_data:
                swap_info = tx_data["swap_info"]
                input_token = swap_info.get("input_token_symbol", "未知")
                output_token = swap_info.get("output_token_symbol", "未知")
                input_amount = swap_info.get("input_amount", 0)
                output_amount = swap_info.get("output_amount", 0)
                
                print(f"  交易: {input_amount} {input_token} -> {output_amount} {output_token}")
                
                # 更新全局监控的交易对
                token_pair = f"{input_token}/{output_token}"
                global monitored_pairs
                
                if token_pair not in monitored_pairs:
                    monitored_pairs[token_pair] = {
                        "start_time": time.time(),
                        "last_activity": time.time(),
                        "last_analysis": 0,
                        "transactions": [],
                        "pool_states": [],
                        "market_data": [],
                        "routes": []
                    }
                else:
                    monitored_pairs[token_pair]["last_activity"] = time.time()
                
                monitored_pairs[token_pair]["transactions"].append(tx_data)
            
            # 存储交易数据
            storage.store_transaction(tx_data, wallet_address)
            print(f"  已存储交易数据")
            
        except Exception as e:
            print(f"处理交易时出错: {e}")
    
    return callback

async def monitor_wallet_transactions(wallet_address, collector, callback, analysis_times, analysis_interval):
    """
    持续监控钱包交易
    
    Args:
        wallet_address: 钱包地址
        collector: 收集器实例
        callback: 交易处理回调
        analysis_times: 上次分析时间字典
        analysis_interval: 分析间隔(小时)
    """
    print(f"开始监控钱包 {wallet_address} 的交易...")
    
    # 监听新交易
    await collector.listen_for_transactions(wallet_address, callback)
    
    # 注意：由于listen_for_transactions是一个阻塞调用，
    # 以下代码只会在监听结束后执行，这里添加是为了保持完整性
    print(f"钱包 {wallet_address} 的监控已结束")

async def perform_periodic_analysis(wallet_address, storage, analysis_times, analysis_interval):
    """
    定期执行分析
    
    Args:
        wallet_address: 钱包地址
        storage: 存储实例
        analysis_times: 上次分析时间字典
        analysis_interval: 分析间隔(小时)
    """
    current_time = time.time()
    last_analysis = analysis_times.get(wallet_address, 0)
    
    # 检查是否需要分析
    if analysis_interval > 0 and (current_time - last_analysis) >= (analysis_interval * 3600):
        print(f"\n开始分析钱包 {wallet_address} 的交易...")
        
        # 执行分析
        analysis_result = await analyze_wallet(wallet_address)
        
        if analysis_result:
            print(f"分析完成: {wallet_address}")
        else:
            print(f"分析失败: {wallet_address}")
        
        # 更新分析时间
        analysis_times[wallet_address] = current_time

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Solana交易分析移动客户端")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 收集命令
    collect_parser = subparsers.add_parser("collect", help="收集并存储交易数据")
    collect_parser.add_argument("wallet", help="钱包地址")
    collect_parser.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC节点URL")
    collect_parser.add_argument("--days", type=int, default=7, help="收集多少天的数据")
    collect_parser.add_argument("--use-grpc", action="store_true", help="使用GRPC连接")
    collect_parser.add_argument("--grpc-endpoint", default=DEFAULT_GRPC_ENDPOINT, help="GRPC节点地址")
    
    # 分析命令
    analyze_parser = subparsers.add_parser("analyze", help="分析存储的交易数据")
    analyze_parser.add_argument("wallet", help="钱包地址")
    analyze_parser.add_argument("--days", type=int, default=30, help="分析多少天的数据")
    analyze_parser.add_argument("--api-key", help="API密钥")
    
    # 列出命令
    list_parser = subparsers.add_parser("list", help="列出存储的数据")
    list_parser.add_argument("--wallet", help="钱包地址(可选)")
    
    # 导出命令
    export_parser = subparsers.add_parser("export", help="导出分析结果")
    export_parser.add_argument("wallet", help="钱包地址")
    export_parser.add_argument("--output", help="输出文件路径")
    
    # 初始化命令
    init_parser = subparsers.add_parser("init", help="初始化存储")
    init_parser.add_argument("--dir", help="基础存储目录")
    init_parser.add_argument("--api-endpoint", help="API分析端点")
    init_parser.add_argument("--api-key", help="API访问密钥")
    
    # 交互式菜单
    menu_parser = subparsers.add_parser("menu", help="启动交互式菜单")
    
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_arguments()
    
    # 检查命令
    if args.command == "collect":
        result = await collect_and_store(args.wallet, args.rpc, args.days, args.use_grpc, args.grpc_endpoint)
        print(json.dumps(result, indent=2))
    
    elif args.command == "analyze":
        result = await analyze_stored_data(args.wallet, args.days, args.api_key)
        if result:
            # 仅打印分析结果概要，避免输出过多内容
            summary = {
                "wallet_address": result["wallet_address"],
                "analyzed_transactions": result["analyzed_transactions"],
            }
            if "analysis_result" in result and isinstance(result["analysis_result"], dict):
                if "pattern_recognition" in result["analysis_result"]:
                    summary["primary_pattern"] = result["analysis_result"]["pattern_recognition"].get("primary_pattern")
                if "strategy" in result["analysis_result"]:
                    summary["strategy_name"] = result["analysis_result"]["strategy"].get("name")
            print(json.dumps(summary, indent=2))
    
    elif args.command == "list":
        await list_wallet_data(args.wallet)
    
    elif args.command == "export":
        success = await export_analysis_result(args.wallet, args.output)
        if success:
            print("分析结果导出成功")
        else:
            print("分析结果导出失败")
    
    elif args.command == "init":
        init_storage(args.dir, args.api_endpoint, args.api_key)
        print("存储初始化完成")
    
    elif args.command == "menu" or args.command is None:
        await interactive_menu()
    
    else:
        print("请指定命令: collect, analyze, list, export, init 或 menu")

if __name__ == "__main__":
    asyncio.run(main()) 
移动客户端示例
展示如何使用移动端存储和API分析功能
"""
import os
import json
import asyncio
import argparse
import logging
import time
from typing import Dict, List, Any, Optional

from .storage import init_storage, get_storage, analyze_wallet
from ..solana.collector import SolanaCollector

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.expanduser("~"), "solana_analyzer", "config.json")

# 硬编码的GRPC节点地址
DEFAULT_GRPC_ENDPOINT = "solana-yellowstone-grpc.publicnode.com:443"

# 监控中的币对列表(全局缓存)
monitored_pairs = {}

async def collect_and_store(wallet_address: str, rpc_url: str, days: int = 7, use_grpc: bool = False, grpc_endpoint: str = None):
    """
    从Solana收集交易并存储到移动设备
    
    Args:
        wallet_address: 钱包地址
        rpc_url: Solana RPC节点URL
        days: 收集多少天的交易数据
        use_grpc: 是否使用GRPC连接
        grpc_endpoint: GRPC节点地址
    """
    logger.info(f"开始收集钱包 {wallet_address} 的交易数据")
    
    # 初始化收集器
    collector_kwargs = {"rpc_url": rpc_url}
    if use_grpc:
        collector_kwargs["use_grpc"] = True
        collector_kwargs["grpc_endpoint"] = grpc_endpoint or DEFAULT_GRPC_ENDPOINT
        logger.info(f"使用GRPC节点: {collector_kwargs['grpc_endpoint']}")
    
    collector = SolanaCollector(**collector_kwargs)
    
    try:
        # 获取交易
        transactions = await collector.get_historical_transactions(wallet_address, days=days)
        logger.info(f"从链上获取了 {len(transactions)} 个交易")
        
        # 获取交换交易
        swap_txs = await collector.fetch_recent_swap_transactions(wallet_address, days=days)
        logger.info(f"其中交换交易有 {len(swap_txs)} 个")
        
        # 获取存储实例
        storage = get_storage()
        
        # 存储交易
        file_paths = storage.store_transactions(transactions, wallet_address)
        logger.info(f"已存储 {len(file_paths)} 个交易到移动设备")
        
        # 返回结果统计
        return {
            "wallet_address": wallet_address,
            "total_transactions": len(transactions),
            "swap_transactions": len(swap_txs),
            "stored_transactions": len(file_paths)
        }
    
    finally:
        # 关闭收集器
        await collector.close()

async def analyze_stored_data(wallet_address: str, days: int = 30, api_key: str = None):
    """
    分析存储在移动设备上的交易数据
    
    Args:
        wallet_address: 钱包地址
        days: 分析多少天的数据
        api_key: API密钥
    """
    # 初始化存储(如果提供了API密钥)
    if api_key:
        init_storage(api_key=api_key)
    
    logger.info(f"开始分析钱包 {wallet_address} 的交易数据")
    
    # 获取存储实例
    storage = get_storage()
    
    # 列出存储的交易
    transactions = storage.list_transactions(wallet_address, days)
    logger.info(f"移动设备上找到 {len(transactions)} 个交易")
    
    if not transactions:
        logger.warning("没有找到交易数据，无法分析")
        return None
    
    # 请求API分析
    analysis_result = await analyze_wallet(wallet_address, days)
    
    if analysis_result:
        logger.info("分析完成，结果已存储")
        return {
            "wallet_address": wallet_address,
            "analyzed_transactions": len(transactions),
            "analysis_result": analysis_result
        }
    else:
        logger.error("分析失败")
        return None

async def list_wallet_data(wallet_address: str = None):
    """
    列出存储在移动设备上的钱包数据
    
    Args:
        wallet_address: 钱包地址(如果为None，列出所有钱包)
    """
    storage = get_storage()
    
    # 获取存储信息
    storage_info = storage.get_storage_info()
    
    if wallet_address:
        # 列出特定钱包的信息
        wallet_found = False
        for wallet in storage_info["wallets"]:
            if wallet["address"] == wallet_address:
                wallet_found = True
                print(f"钱包: {wallet_address}")
                print(f"  交易数量: {wallet['transactions']}")
                print(f"  分析结果数量: {wallet['analyses']}")
                
                # 列出最近的交易
                transactions = storage.list_transactions(wallet_address, days=30)
                print(f"\n最近 30 天的交易 ({len(transactions)}):")
                for i, tx in enumerate(transactions[:5]):  # 只显示前5个
                    print(f"  {i+1}. {tx.get('transaction_id')} - {tx.get('timestamp')}")
                
                if len(transactions) > 5:
                    print(f"  ... 还有 {len(transactions) - 5} 个交易未显示")
                
                # 列出分析结果
                analyses = storage.list_analysis_results(wallet_address)
                print(f"\n分析结果 ({len(analyses)}):")
                for i, analysis in enumerate(analyses):
                    print(f"  {i+1}. {analysis.get('analysis_id')} - {analysis.get('timestamp')}")
                
                break
        
        if not wallet_found:
            print(f"未找到钱包 {wallet_address} 的数据")
    else:
        # 列出所有钱包的汇总信息
        print("存储信息:")
        print(f"  存储路径: {storage_info['base_dir']}")
        print(f"  钱包数量: {len(storage_info['wallets'])}")
        print(f"  总交易数量: {storage_info['total_transactions']}")
        print(f"  总分析结果数量: {storage_info['total_analyses']}")
        print(f"  存储大小: {storage_info['storage_size'] / 1024 / 1024:.2f} MB")
        
        print("\n钱包列表:")
        for i, wallet in enumerate(storage_info["wallets"]):
            print(f"  {i+1}. {wallet['address']} - 交易: {wallet['transactions']}, 分析: {wallet['analyses']}")

async def export_analysis_result(wallet_address: str, output_file: str = None):
    """
    导出分析结果
    
    Args:
        wallet_address: 钱包地址
        output_file: 输出文件路径(默认为当前目录下的wallet_analysis.json)
    """
    storage = get_storage()
    
    # 获取最新的分析结果
    analyses = storage.list_analysis_results(wallet_address, limit=1)
    
    if not analyses:
        logger.error(f"没有找到钱包 {wallet_address} 的分析结果")
        return False
    
    latest_analysis = analyses[0]
    
    # 设置输出文件路径
    if not output_file:
        output_file = f"{wallet_address}_analysis.json"
    
    # 写入文件
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(latest_analysis, f, indent=2, ensure_ascii=False)
        
        logger.info(f"分析结果已导出到: {output_file}")
        return True
    except Exception as e:
        logger.error(f"导出分析结果出错: {e}")
        return False

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件出错: {e}")
    return {
        "api_key": "",
        "api_endpoint": "https://ark.cn-beijing.volces.com/api/v3",
        "monitored_wallets": [],
        "use_grpc": True,
        "grpc_endpoint": DEFAULT_GRPC_ENDPOINT
    }

def save_config(config):
    """保存配置文件"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"保存配置文件出错: {e}")
        return False

async def interactive_menu():
    """交互式菜单"""
    # 加载配置
    config = load_config()
    
    while True:
        print("\n====== Solana交易分析工具 ======")
        print("1. 填写监听的地址")
        print("2. 录入API密钥和设置")
        print("3. 查看监听简报")
        print("4. 启动自动监控")
        print("5. 分析特定钱包")
        print("6. 导出分析结果")
        print("7. 实时监控交易")
        print("0. 退出")
        
        choice = input("\n请选择功能 (0-7): ")
        
        if choice == "1":
            await manage_wallet_addresses(config)
        elif choice == "2":
            update_api_key(config)
        elif choice == "3":
            await view_monitoring_report(config)
        elif choice == "4":
            await start_automatic_monitoring(config)
        elif choice == "5":
            await analyze_specific_wallet(config)
        elif choice == "6":
            await export_specific_analysis(config)
        elif choice == "7":
            await real_time_monitor(config)
        elif choice == "0":
            print("谢谢使用，再见！")
            break
        else:
            print("无效的选择，请重试")

async def manage_wallet_addresses(config):
    """管理监听的钱包地址"""
    while True:
        print("\n----- 监听地址管理 -----")
        print("当前监听的地址:")
        
        if not config.get("monitored_wallets"):
            print("  (无)")
        else:
            for i, wallet in enumerate(config["monitored_wallets"]):
                print(f"  {i+1}. {wallet}")
        
        print("\n操作选项:")
        print("1. 添加新地址")
        print("2. 删除地址")
        print("0. 返回主菜单")
        
        choice = input("\n请选择操作 (0-2): ")
        
        if choice == "1":
            wallet = input("请输入要添加的Solana钱包地址: ").strip()
            if wallet:
                if "monitored_wallets" not in config:
                    config["monitored_wallets"] = []
                if wallet not in config["monitored_wallets"]:
                    config["monitored_wallets"].append(wallet)
                    save_config(config)
                    print(f"已添加地址: {wallet}")
                else:
                    print("该地址已在监听列表中")
            else:
                print("地址不能为空")
        
        elif choice == "2":
            if not config.get("monitored_wallets"):
                print("没有要删除的地址")
                continue
                
            index = input("请输入要删除的地址编号: ")
            try:
                idx = int(index) - 1
                if 0 <= idx < len(config["monitored_wallets"]):
                    removed = config["monitored_wallets"].pop(idx)
                    save_config(config)
                    print(f"已删除地址: {removed}")
                else:
                    print("无效的编号")
            except ValueError:
                print("请输入有效的数字")
        
        elif choice == "0":
            break
        
        else:
            print("无效的选择，请重试")

def update_api_key(config):
    """更新API密钥"""
    print("\n----- API密钥设置 -----")
    print(f"当前API密钥: {config.get('api_key', '未设置')}")
    
    new_key = input("请输入新的API密钥 (保留空白则不变): ").strip()
    if new_key:
        config["api_key"] = new_key
        save_config(config)
        # 同时更新存储实例的API密钥
        init_storage(api_key=new_key)
        print("API密钥已更新")
    else:
        print("API密钥未变更")
    
    endpoint = input("请输入API端点 (保留空白则使用默认): ").strip()
    if endpoint:
        config["api_endpoint"] = endpoint
        save_config(config)
        # 同时更新存储实例的API端点
        init_storage(api_endpoint=endpoint)
        print("API端点已更新")
    
    print(f"\n----- GRPC设置 -----")
    print(f"当前使用GRPC: {'是' if config.get('use_grpc', True) else '否'}")
    print(f"当前GRPC节点: {config.get('grpc_endpoint', DEFAULT_GRPC_ENDPOINT)}")
    print("注意: GRPC节点默认使用 solana-yellowstone-grpc.publicnode.com:443")

async def view_monitoring_report(config):
    """查看监听简报"""
    print("\n----- 监听简报 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址")
        return
    
    storage = get_storage()
    
    for wallet in config["monitored_wallets"]:
        print(f"\n钱包: {wallet}")
        
        # 获取交易数据
        transactions = storage.list_transactions(wallet, days=30)
        print(f"  最近30天交易数: {len(transactions)}")
        
        # 获取分析结果
        analyses = storage.list_analysis_results(wallet, limit=1)
        if analyses:
            latest = analyses[0]
            print(f"  最新分析时间: {latest.get('timestamp')}")
            
            # 尝试提取主要交易模式
            result = latest.get("result", {})
            if "pattern_recognition" in result:
                pattern = result["pattern_recognition"].get("primary_pattern", "未知")
                print(f"  主要交易模式: {pattern}")
            
            # 尝试提取策略名称
            if "strategy" in result:
                strategy = result["strategy"].get("name", "未知")
                print(f"  推荐策略: {strategy}")
        else:
            print("  尚无分析结果")

async def start_automatic_monitoring(config):
    """启动自动监控"""
    print("\n----- 自动监控 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址，请先添加")
        return
    
    if not config.get("api_key"):
        print("未设置API密钥，无法进行分析")
        return
    
    # 设置RPC URL
    rpc_url = input("请输入Solana RPC URL (留空使用默认): ").strip()
    if not rpc_url:
        rpc_url = "https://api.mainnet-beta.solana.com"
    
    # 设置是否使用GRPC
    use_grpc = config.get("use_grpc", True)
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    print(f"使用GRPC连接: {'是' if use_grpc else '否'}")
    if use_grpc:
        print(f"GRPC节点: {grpc_endpoint}")
    
    # 设置监控间隔
    interval_str = input("请输入监控间隔(分钟，默认30): ").strip()
    try:
        interval = int(interval_str) if interval_str else 30
    except ValueError:
        print("无效的间隔，使用默认值30分钟")
        interval = 30
    
    # 设置监控时长
    duration_str = input("请输入监控时长(小时，默认24): ").strip()
    try:
        duration = int(duration_str) if duration_str else 24
    except ValueError:
        print("无效的时长，使用默认值24小时")
        duration = 24
    
    print(f"\n开始自动监控 {len(config['monitored_wallets'])} 个钱包...")
    print(f"监控间隔: {interval} 分钟")
    print(f"计划监控时长: {duration} 小时")
    print("按 Ctrl+C 停止监控")
    
    # 初始化存储
    init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 计算总循环次数
    total_cycles = (duration * 60) // interval
    current_cycle = 0
    
    try:
        while current_cycle < total_cycles:
            current_cycle += 1
            print(f"\n===== 监控周期 {current_cycle}/{total_cycles} =====")
            
            for wallet in config["monitored_wallets"]:
                print(f"\n监控钱包: {wallet}")
                
                # 收集数据
                try:
                    result = await collect_and_store(
                        wallet, 
                        rpc_url, 
                        days=1,  # 只收集最近1天的数据
                        use_grpc=use_grpc,
                        grpc_endpoint=grpc_endpoint
                    )
                    print(f"收集结果: 总交易 {result['total_transactions']}, 交换交易 {result['swap_transactions']}")
                    
                    # 分析数据
                    if result['total_transactions'] > 0:
                        analysis = await analyze_stored_data(wallet)
                        if analysis:
                            print("分析完成")
                        else:
                            print("分析失败或无数据")
                    else:
                        print("无新交易，跳过分析")
                        
                except Exception as e:
                    print(f"处理钱包 {wallet} 时出错: {e}")
            
            # 如果不是最后一个周期，则等待
            if current_cycle < total_cycles:
                print(f"\n等待 {interval} 分钟后开始下一轮监控...")
                await asyncio.sleep(interval * 60)
        
        print("\n监控完成！")
            
    except KeyboardInterrupt:
        print("\n监控已手动停止")

async def analyze_specific_wallet(config):
    """分析特定钱包"""
    print("\n----- 分析特定钱包 -----")
    
    # 检查API密钥
    if not config.get("api_key"):
        print("未设置API密钥，请先设置")
        return
    
    # 获取钱包地址
    wallet = input("请输入要分析的钱包地址: ").strip()
    if not wallet:
        print("钱包地址不能为空")
        return
    
    # 获取分析天数
    days_str = input("分析最近多少天的数据 (默认30): ").strip()
    try:
        days = int(days_str) if days_str else 30
    except ValueError:
        print("无效的天数，使用默认值30")
        days = 30
    
    # 设置RPC URL
    rpc_url = input("请输入Solana RPC URL (留空使用默认): ").strip()
    if not rpc_url:
        rpc_url = "https://api.mainnet-beta.solana.com"
    
    # 设置是否使用GRPC
    use_grpc = config.get("use_grpc", True)
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    print(f"使用GRPC连接: {'是' if use_grpc else '否'}")
    if use_grpc:
        print(f"GRPC节点: {grpc_endpoint}")
    
    print(f"\n开始分析钱包 {wallet}...")
    
    # 初始化存储和API密钥
    init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 收集数据
    try:
        print("正在收集交易数据...")
        result = await collect_and_store(
            wallet, 
            rpc_url, 
            days=days,
            use_grpc=use_grpc,
            grpc_endpoint=grpc_endpoint
        )
        print(f"收集完成，获取了 {result['total_transactions']} 个交易")
        
        if result['total_transactions'] > 0:
            print("正在分析数据...")
            analysis = await analyze_stored_data(wallet, days)
            
            if analysis and "analysis_result" in analysis:
                print("\n分析完成！")
                
                # 显示简要结果
                result = analysis["analysis_result"]
                if "pattern_recognition" in result:
                    pattern = result["pattern_recognition"].get("primary_pattern", "未知")
                    print(f"主要交易模式: {pattern}")
                
                if "strategy" in result:
                    strategy = result["strategy"]
                    print(f"策略名称: {strategy.get('name', '未知')}")
                    print(f"策略描述: {strategy.get('description', '未知')}")
                    
                    if "target_selection" in strategy:
                        criteria = strategy["target_selection"].get("criteria", [])
                        print(f"目标选择标准: {', '.join(criteria)}")
                    
                    if "risk_control" in strategy:
                        risk = strategy["risk_control"]
                        print(f"风险控制: 最大仓位 {risk.get('max_position_size', '未知')}, 最大日亏损 {risk.get('max_daily_loss', '未知')}")
                
                # 询问是否导出完整结果
                if input("\n是否导出完整分析结果？(y/n): ").lower() == 'y':
                    output_file = input("请输入输出文件名 (默认为 {wallet}_analysis.json): ").strip()
                    if not output_file:
                        output_file = f"{wallet}_analysis.json"
                    
                    if await export_analysis_result(wallet, output_file):
                        print(f"分析结果已导出到 {output_file}")
            else:
                print("分析失败或无数据")
        else:
            print("没有发现交易，无法分析")
            
    except Exception as e:
        print(f"处理钱包时出错: {e}")

async def export_specific_analysis(config):
    """导出特定分析结果"""
    print("\n----- 导出分析结果 -----")
    
    # 获取钱包地址
    wallet = input("请输入钱包地址: ").strip()
    if not wallet:
        print("钱包地址不能为空")
        return
    
    # 获取存储实例
    storage = get_storage()
    
    # 获取分析结果列表
    analyses = storage.list_analysis_results(wallet)
    
    if not analyses:
        print(f"未找到钱包 {wallet} 的分析结果")
        return
    
    print(f"\n找到 {len(analyses)} 个分析结果:")
    for i, analysis in enumerate(analyses):
        print(f"  {i+1}. {analysis.get('analysis_id')} - {analysis.get('timestamp')}")
    
    # 选择要导出的结果
    index_str = input("\n请选择要导出的结果编号 (默认1): ").strip()
    try:
        index = int(index_str) - 1 if index_str else 0
        if not (0 <= index < len(analyses)):
            print("无效的编号，使用最新的分析结果")
            index = 0
    except ValueError:
        print("无效的编号，使用最新的分析结果")
        index = 0
    
    # 获取输出文件名
    output_file = input("请输入输出文件名 (默认为 {wallet}_analysis.json): ").strip()
    if not output_file:
        output_file = f"{wallet}_analysis.json"
    
    # 导出结果
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analyses[index], f, indent=2, ensure_ascii=False)
        print(f"分析结果已导出到 {output_file}")
    except Exception as e:
        print(f"导出分析结果出错: {e}")

async def real_time_monitor(config):
    """
    实时监控钱包交易
    使用GRPC流式连接，实时接收和处理交易数据
    
    Args:
        config: 配置信息
    """
    print("\n----- 实时监控 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址，请先添加")
        return
    
    # 选择是否使用API分析
    use_api = False
    if config.get("api_key"):
        use_api_input = input("是否启用API分析? (y/n, 默认n): ").strip().lower()
        use_api = use_api_input == 'y'
    else:
        print("未设置API密钥，无法启用API分析")
    
    # 设置分析间隔(如果启用API分析)
    analysis_interval = 0
    if use_api:
        interval_str = input("设置分析间隔(小时，默认6): ").strip()
        try:
            analysis_interval = int(interval_str) if interval_str else 6
        except ValueError:
            print("无效的间隔，使用默认值6小时")
            analysis_interval = 6
    
    # 确保GRPC端点设置
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    
    print(f"\n开始实时监控 {len(config['monitored_wallets'])} 个钱包...")
    print(f"GRPC节点: {grpc_endpoint}")
    
    if use_api:
        print(f"API分析间隔: {analysis_interval}小时")
    else:
        print("API分析: 已禁用")
    
    print("按 Ctrl+C 停止监控")
    
    # 初始化存储
    storage = init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 初始化收集器(每个钱包一个收集器)
    collectors = {}
    callbacks = {}
    analysis_times = {}
    
    for wallet in config["monitored_wallets"]:
        # 创建收集器
        collectors[wallet] = SolanaCollector(
            use_grpc=True,
            grpc_endpoint=grpc_endpoint
        )
        
        # 创建交易处理回调
        callbacks[wallet] = create_transaction_callback(wallet, storage, use_api)
        
        # 初始化分析时间
        analysis_times[wallet] = time.time()
    
    try:
        # 启动监听
        tasks = []
        for wallet, collector in collectors.items():
            task = asyncio.create_task(
                monitor_wallet_transactions(
                    wallet, 
                    collector, 
                    callbacks[wallet], 
                    analysis_times, 
                    analysis_interval
                )
            )
            tasks.append(task)
        
        # 等待所有任务完成(实际上不会完成，除非发生错误或用户中断)
        await asyncio.gather(*tasks)
        
    except KeyboardInterrupt:
        print("\n监控已手动停止")
    except Exception as e:
        print(f"\n监控出错: {e}")
    finally:
        # 关闭所有收集器
        for wallet, collector in collectors.items():
            await collector.close()
            print(f"已关闭钱包 {wallet} 的监控")

def create_transaction_callback(wallet_address, storage, use_api):
    """
    创建交易处理回调函数
    
    Args:
        wallet_address: 钱包地址
        storage: 存储实例
        use_api: 是否使用API分析
        
    Returns:
        回调函数
    """
    async def callback(tx_data):
        try:
            # 打印交易信息
            tx_hash = tx_data.get("transaction_id", "unknown")
            timestamp = tx_data.get("timestamp", "unknown")
            success = "成功" if tx_data.get("success", False) else "失败"
            
            # 识别交易类型
            tx_type = "普通"
            if tx_data.get("is_swap", False):
                tx_type = "交换"
            elif tx_data.get("is_liquidity", False):
                tx_type = "流动性"
            elif tx_data.get("is_stake", False):
                tx_type = "质押"
            
            print(f"\n接收到 {wallet_address} 的{tx_type}交易: {tx_hash}")
            print(f"  时间: {timestamp}")
            print(f"  状态: {success}")
            
            # 提取交易对信息
            if tx_data.get("is_swap", False) and "swap_info" in tx_data:
                swap_info = tx_data["swap_info"]
                input_token = swap_info.get("input_token_symbol", "未知")
                output_token = swap_info.get("output_token_symbol", "未知")
                input_amount = swap_info.get("input_amount", 0)
                output_amount = swap_info.get("output_amount", 0)
                
                print(f"  交易: {input_amount} {input_token} -> {output_amount} {output_token}")
                
                # 更新全局监控的交易对
                token_pair = f"{input_token}/{output_token}"
                global monitored_pairs
                
                if token_pair not in monitored_pairs:
                    monitored_pairs[token_pair] = {
                        "start_time": time.time(),
                        "last_activity": time.time(),
                        "last_analysis": 0,
                        "transactions": [],
                        "pool_states": [],
                        "market_data": [],
                        "routes": []
                    }
                else:
                    monitored_pairs[token_pair]["last_activity"] = time.time()
                
                monitored_pairs[token_pair]["transactions"].append(tx_data)
            
            # 存储交易数据
            storage.store_transaction(tx_data, wallet_address)
            print(f"  已存储交易数据")
            
        except Exception as e:
            print(f"处理交易时出错: {e}")
    
    return callback

async def monitor_wallet_transactions(wallet_address, collector, callback, analysis_times, analysis_interval):
    """
    持续监控钱包交易
    
    Args:
        wallet_address: 钱包地址
        collector: 收集器实例
        callback: 交易处理回调
        analysis_times: 上次分析时间字典
        analysis_interval: 分析间隔(小时)
    """
    print(f"开始监控钱包 {wallet_address} 的交易...")
    
    # 监听新交易
    await collector.listen_for_transactions(wallet_address, callback)
    
    # 注意：由于listen_for_transactions是一个阻塞调用，
    # 以下代码只会在监听结束后执行，这里添加是为了保持完整性
    print(f"钱包 {wallet_address} 的监控已结束")

async def perform_periodic_analysis(wallet_address, storage, analysis_times, analysis_interval):
    """
    定期执行分析
    
    Args:
        wallet_address: 钱包地址
        storage: 存储实例
        analysis_times: 上次分析时间字典
        analysis_interval: 分析间隔(小时)
    """
    current_time = time.time()
    last_analysis = analysis_times.get(wallet_address, 0)
    
    # 检查是否需要分析
    if analysis_interval > 0 and (current_time - last_analysis) >= (analysis_interval * 3600):
        print(f"\n开始分析钱包 {wallet_address} 的交易...")
        
        # 执行分析
        analysis_result = await analyze_wallet(wallet_address)
        
        if analysis_result:
            print(f"分析完成: {wallet_address}")
        else:
            print(f"分析失败: {wallet_address}")
        
        # 更新分析时间
        analysis_times[wallet_address] = current_time

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Solana交易分析移动客户端")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 收集命令
    collect_parser = subparsers.add_parser("collect", help="收集并存储交易数据")
    collect_parser.add_argument("wallet", help="钱包地址")
    collect_parser.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC节点URL")
    collect_parser.add_argument("--days", type=int, default=7, help="收集多少天的数据")
    collect_parser.add_argument("--use-grpc", action="store_true", help="使用GRPC连接")
    collect_parser.add_argument("--grpc-endpoint", default=DEFAULT_GRPC_ENDPOINT, help="GRPC节点地址")
    
    # 分析命令
    analyze_parser = subparsers.add_parser("analyze", help="分析存储的交易数据")
    analyze_parser.add_argument("wallet", help="钱包地址")
    analyze_parser.add_argument("--days", type=int, default=30, help="分析多少天的数据")
    analyze_parser.add_argument("--api-key", help="API密钥")
    
    # 列出命令
    list_parser = subparsers.add_parser("list", help="列出存储的数据")
    list_parser.add_argument("--wallet", help="钱包地址(可选)")
    
    # 导出命令
    export_parser = subparsers.add_parser("export", help="导出分析结果")
    export_parser.add_argument("wallet", help="钱包地址")
    export_parser.add_argument("--output", help="输出文件路径")
    
    # 初始化命令
    init_parser = subparsers.add_parser("init", help="初始化存储")
    init_parser.add_argument("--dir", help="基础存储目录")
    init_parser.add_argument("--api-endpoint", help="API分析端点")
    init_parser.add_argument("--api-key", help="API访问密钥")
    
    # 交互式菜单
    menu_parser = subparsers.add_parser("menu", help="启动交互式菜单")
    
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_arguments()
    
    # 检查命令
    if args.command == "collect":
        result = await collect_and_store(args.wallet, args.rpc, args.days, args.use_grpc, args.grpc_endpoint)
        print(json.dumps(result, indent=2))
    
    elif args.command == "analyze":
        result = await analyze_stored_data(args.wallet, args.days, args.api_key)
        if result:
            # 仅打印分析结果概要，避免输出过多内容
            summary = {
                "wallet_address": result["wallet_address"],
                "analyzed_transactions": result["analyzed_transactions"],
            }
            if "analysis_result" in result and isinstance(result["analysis_result"], dict):
                if "pattern_recognition" in result["analysis_result"]:
                    summary["primary_pattern"] = result["analysis_result"]["pattern_recognition"].get("primary_pattern")
                if "strategy" in result["analysis_result"]:
                    summary["strategy_name"] = result["analysis_result"]["strategy"].get("name")
            print(json.dumps(summary, indent=2))
    
    elif args.command == "list":
        await list_wallet_data(args.wallet)
    
    elif args.command == "export":
        success = await export_analysis_result(args.wallet, args.output)
        if success:
            print("分析结果导出成功")
        else:
            print("分析结果导出失败")
    
    elif args.command == "init":
        init_storage(args.dir, args.api_endpoint, args.api_key)
        print("存储初始化完成")
    
    elif args.command == "menu" or args.command is None:
        await interactive_menu()
    
    else:
        print("请指定命令: collect, analyze, list, export, init 或 menu")

if __name__ == "__main__":
    asyncio.run(main()) 
移动客户端示例
展示如何使用移动端存储和API分析功能
"""
import os
import json
import asyncio
import argparse
import logging
import time
from typing import Dict, List, Any, Optional

from .storage import init_storage, get_storage, analyze_wallet
from ..solana.collector import SolanaCollector

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.expanduser("~"), "solana_analyzer", "config.json")

# 硬编码的GRPC节点地址
DEFAULT_GRPC_ENDPOINT = "solana-yellowstone-grpc.publicnode.com:443"

# 监控中的币对列表(全局缓存)
monitored_pairs = {}

async def collect_and_store(wallet_address: str, rpc_url: str, days: int = 7, use_grpc: bool = False, grpc_endpoint: str = None):
    """
    从Solana收集交易并存储到移动设备
    
    Args:
        wallet_address: 钱包地址
        rpc_url: Solana RPC节点URL
        days: 收集多少天的交易数据
        use_grpc: 是否使用GRPC连接
        grpc_endpoint: GRPC节点地址
    """
    logger.info(f"开始收集钱包 {wallet_address} 的交易数据")
    
    # 初始化收集器
    collector_kwargs = {"rpc_url": rpc_url}
    if use_grpc:
        collector_kwargs["use_grpc"] = True
        collector_kwargs["grpc_endpoint"] = grpc_endpoint or DEFAULT_GRPC_ENDPOINT
        logger.info(f"使用GRPC节点: {collector_kwargs['grpc_endpoint']}")
    
    collector = SolanaCollector(**collector_kwargs)
    
    try:
        # 获取交易
        transactions = await collector.get_historical_transactions(wallet_address, days=days)
        logger.info(f"从链上获取了 {len(transactions)} 个交易")
        
        # 获取交换交易
        swap_txs = await collector.fetch_recent_swap_transactions(wallet_address, days=days)
        logger.info(f"其中交换交易有 {len(swap_txs)} 个")
        
        # 获取存储实例
        storage = get_storage()
        
        # 存储交易
        file_paths = storage.store_transactions(transactions, wallet_address)
        logger.info(f"已存储 {len(file_paths)} 个交易到移动设备")
        
        # 返回结果统计
        return {
            "wallet_address": wallet_address,
            "total_transactions": len(transactions),
            "swap_transactions": len(swap_txs),
            "stored_transactions": len(file_paths)
        }
    
    finally:
        # 关闭收集器
        await collector.close()

async def analyze_stored_data(wallet_address: str, days: int = 30, api_key: str = None):
    """
    分析存储在移动设备上的交易数据
    
    Args:
        wallet_address: 钱包地址
        days: 分析多少天的数据
        api_key: API密钥
    """
    # 初始化存储(如果提供了API密钥)
    if api_key:
        init_storage(api_key=api_key)
    
    logger.info(f"开始分析钱包 {wallet_address} 的交易数据")
    
    # 获取存储实例
    storage = get_storage()
    
    # 列出存储的交易
    transactions = storage.list_transactions(wallet_address, days)
    logger.info(f"移动设备上找到 {len(transactions)} 个交易")
    
    if not transactions:
        logger.warning("没有找到交易数据，无法分析")
        return None
    
    # 请求API分析
    analysis_result = await analyze_wallet(wallet_address, days)
    
    if analysis_result:
        logger.info("分析完成，结果已存储")
        return {
            "wallet_address": wallet_address,
            "analyzed_transactions": len(transactions),
            "analysis_result": analysis_result
        }
    else:
        logger.error("分析失败")
        return None

async def list_wallet_data(wallet_address: str = None):
    """
    列出存储在移动设备上的钱包数据
    
    Args:
        wallet_address: 钱包地址(如果为None，列出所有钱包)
    """
    storage = get_storage()
    
    # 获取存储信息
    storage_info = storage.get_storage_info()
    
    if wallet_address:
        # 列出特定钱包的信息
        wallet_found = False
        for wallet in storage_info["wallets"]:
            if wallet["address"] == wallet_address:
                wallet_found = True
                print(f"钱包: {wallet_address}")
                print(f"  交易数量: {wallet['transactions']}")
                print(f"  分析结果数量: {wallet['analyses']}")
                
                # 列出最近的交易
                transactions = storage.list_transactions(wallet_address, days=30)
                print(f"\n最近 30 天的交易 ({len(transactions)}):")
                for i, tx in enumerate(transactions[:5]):  # 只显示前5个
                    print(f"  {i+1}. {tx.get('transaction_id')} - {tx.get('timestamp')}")
                
                if len(transactions) > 5:
                    print(f"  ... 还有 {len(transactions) - 5} 个交易未显示")
                
                # 列出分析结果
                analyses = storage.list_analysis_results(wallet_address)
                print(f"\n分析结果 ({len(analyses)}):")
                for i, analysis in enumerate(analyses):
                    print(f"  {i+1}. {analysis.get('analysis_id')} - {analysis.get('timestamp')}")
                
                break
        
        if not wallet_found:
            print(f"未找到钱包 {wallet_address} 的数据")
    else:
        # 列出所有钱包的汇总信息
        print("存储信息:")
        print(f"  存储路径: {storage_info['base_dir']}")
        print(f"  钱包数量: {len(storage_info['wallets'])}")
        print(f"  总交易数量: {storage_info['total_transactions']}")
        print(f"  总分析结果数量: {storage_info['total_analyses']}")
        print(f"  存储大小: {storage_info['storage_size'] / 1024 / 1024:.2f} MB")
        
        print("\n钱包列表:")
        for i, wallet in enumerate(storage_info["wallets"]):
            print(f"  {i+1}. {wallet['address']} - 交易: {wallet['transactions']}, 分析: {wallet['analyses']}")

async def export_analysis_result(wallet_address: str, output_file: str = None):
    """
    导出分析结果
    
    Args:
        wallet_address: 钱包地址
        output_file: 输出文件路径(默认为当前目录下的wallet_analysis.json)
    """
    storage = get_storage()
    
    # 获取最新的分析结果
    analyses = storage.list_analysis_results(wallet_address, limit=1)
    
    if not analyses:
        logger.error(f"没有找到钱包 {wallet_address} 的分析结果")
        return False
    
    latest_analysis = analyses[0]
    
    # 设置输出文件路径
    if not output_file:
        output_file = f"{wallet_address}_analysis.json"
    
    # 写入文件
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(latest_analysis, f, indent=2, ensure_ascii=False)
        
        logger.info(f"分析结果已导出到: {output_file}")
        return True
    except Exception as e:
        logger.error(f"导出分析结果出错: {e}")
        return False

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件出错: {e}")
    return {
        "api_key": "",
        "api_endpoint": "https://ark.cn-beijing.volces.com/api/v3",
        "monitored_wallets": [],
        "use_grpc": True,
        "grpc_endpoint": DEFAULT_GRPC_ENDPOINT
    }

def save_config(config):
    """保存配置文件"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"保存配置文件出错: {e}")
        return False

async def interactive_menu():
    """交互式菜单"""
    # 加载配置
    config = load_config()
    
    while True:
        print("\n====== Solana交易分析工具 ======")
        print("1. 填写监听的地址")
        print("2. 录入API密钥和设置")
        print("3. 查看监听简报")
        print("4. 启动自动监控")
        print("5. 分析特定钱包")
        print("6. 导出分析结果")
        print("7. 实时监控交易")
        print("0. 退出")
        
        choice = input("\n请选择功能 (0-7): ")
        
        if choice == "1":
            await manage_wallet_addresses(config)
        elif choice == "2":
            update_api_key(config)
        elif choice == "3":
            await view_monitoring_report(config)
        elif choice == "4":
            await start_automatic_monitoring(config)
        elif choice == "5":
            await analyze_specific_wallet(config)
        elif choice == "6":
            await export_specific_analysis(config)
        elif choice == "7":
            await real_time_monitor(config)
        elif choice == "0":
            print("谢谢使用，再见！")
            break
        else:
            print("无效的选择，请重试")

async def manage_wallet_addresses(config):
    """管理监听的钱包地址"""
    while True:
        print("\n----- 监听地址管理 -----")
        print("当前监听的地址:")
        
        if not config.get("monitored_wallets"):
            print("  (无)")
        else:
            for i, wallet in enumerate(config["monitored_wallets"]):
                print(f"  {i+1}. {wallet}")
        
        print("\n操作选项:")
        print("1. 添加新地址")
        print("2. 删除地址")
        print("0. 返回主菜单")
        
        choice = input("\n请选择操作 (0-2): ")
        
        if choice == "1":
            wallet = input("请输入要添加的Solana钱包地址: ").strip()
            if wallet:
                if "monitored_wallets" not in config:
                    config["monitored_wallets"] = []
                if wallet not in config["monitored_wallets"]:
                    config["monitored_wallets"].append(wallet)
                    save_config(config)
                    print(f"已添加地址: {wallet}")
                else:
                    print("该地址已在监听列表中")
            else:
                print("地址不能为空")
        
        elif choice == "2":
            if not config.get("monitored_wallets"):
                print("没有要删除的地址")
                continue
                
            index = input("请输入要删除的地址编号: ")
            try:
                idx = int(index) - 1
                if 0 <= idx < len(config["monitored_wallets"]):
                    removed = config["monitored_wallets"].pop(idx)
                    save_config(config)
                    print(f"已删除地址: {removed}")
                else:
                    print("无效的编号")
            except ValueError:
                print("请输入有效的数字")
        
        elif choice == "0":
            break
        
        else:
            print("无效的选择，请重试")

def update_api_key(config):
    """更新API密钥"""
    print("\n----- API密钥设置 -----")
    print(f"当前API密钥: {config.get('api_key', '未设置')}")
    
    new_key = input("请输入新的API密钥 (保留空白则不变): ").strip()
    if new_key:
        config["api_key"] = new_key
        save_config(config)
        # 同时更新存储实例的API密钥
        init_storage(api_key=new_key)
        print("API密钥已更新")
    else:
        print("API密钥未变更")
    
    endpoint = input("请输入API端点 (保留空白则使用默认): ").strip()
    if endpoint:
        config["api_endpoint"] = endpoint
        save_config(config)
        # 同时更新存储实例的API端点
        init_storage(api_endpoint=endpoint)
        print("API端点已更新")
    
    print(f"\n----- GRPC设置 -----")
    print(f"当前使用GRPC: {'是' if config.get('use_grpc', True) else '否'}")
    print(f"当前GRPC节点: {config.get('grpc_endpoint', DEFAULT_GRPC_ENDPOINT)}")
    print("注意: GRPC节点默认使用 solana-yellowstone-grpc.publicnode.com:443")

async def view_monitoring_report(config):
    """查看监听简报"""
    print("\n----- 监听简报 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址")
        return
    
    storage = get_storage()
    
    for wallet in config["monitored_wallets"]:
        print(f"\n钱包: {wallet}")
        
        # 获取交易数据
        transactions = storage.list_transactions(wallet, days=30)
        print(f"  最近30天交易数: {len(transactions)}")
        
        # 获取分析结果
        analyses = storage.list_analysis_results(wallet, limit=1)
        if analyses:
            latest = analyses[0]
            print(f"  最新分析时间: {latest.get('timestamp')}")
            
            # 尝试提取主要交易模式
            result = latest.get("result", {})
            if "pattern_recognition" in result:
                pattern = result["pattern_recognition"].get("primary_pattern", "未知")
                print(f"  主要交易模式: {pattern}")
            
            # 尝试提取策略名称
            if "strategy" in result:
                strategy = result["strategy"].get("name", "未知")
                print(f"  推荐策略: {strategy}")
        else:
            print("  尚无分析结果")

async def start_automatic_monitoring(config):
    """启动自动监控"""
    print("\n----- 自动监控 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址，请先添加")
        return
    
    if not config.get("api_key"):
        print("未设置API密钥，无法进行分析")
        return
    
    # 设置RPC URL
    rpc_url = input("请输入Solana RPC URL (留空使用默认): ").strip()
    if not rpc_url:
        rpc_url = "https://api.mainnet-beta.solana.com"
    
    # 设置是否使用GRPC
    use_grpc = config.get("use_grpc", True)
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    print(f"使用GRPC连接: {'是' if use_grpc else '否'}")
    if use_grpc:
        print(f"GRPC节点: {grpc_endpoint}")
    
    # 设置监控间隔
    interval_str = input("请输入监控间隔(分钟，默认30): ").strip()
    try:
        interval = int(interval_str) if interval_str else 30
    except ValueError:
        print("无效的间隔，使用默认值30分钟")
        interval = 30
    
    # 设置监控时长
    duration_str = input("请输入监控时长(小时，默认24): ").strip()
    try:
        duration = int(duration_str) if duration_str else 24
    except ValueError:
        print("无效的时长，使用默认值24小时")
        duration = 24
    
    print(f"\n开始自动监控 {len(config['monitored_wallets'])} 个钱包...")
    print(f"监控间隔: {interval} 分钟")
    print(f"计划监控时长: {duration} 小时")
    print("按 Ctrl+C 停止监控")
    
    # 初始化存储
    init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 计算总循环次数
    total_cycles = (duration * 60) // interval
    current_cycle = 0
    
    try:
        while current_cycle < total_cycles:
            current_cycle += 1
            print(f"\n===== 监控周期 {current_cycle}/{total_cycles} =====")
            
            for wallet in config["monitored_wallets"]:
                print(f"\n监控钱包: {wallet}")
                
                # 收集数据
                try:
                    result = await collect_and_store(
                        wallet, 
                        rpc_url, 
                        days=1,  # 只收集最近1天的数据
                        use_grpc=use_grpc,
                        grpc_endpoint=grpc_endpoint
                    )
                    print(f"收集结果: 总交易 {result['total_transactions']}, 交换交易 {result['swap_transactions']}")
                    
                    # 分析数据
                    if result['total_transactions'] > 0:
                        analysis = await analyze_stored_data(wallet)
                        if analysis:
                            print("分析完成")
                        else:
                            print("分析失败或无数据")
                    else:
                        print("无新交易，跳过分析")
                        
                except Exception as e:
                    print(f"处理钱包 {wallet} 时出错: {e}")
            
            # 如果不是最后一个周期，则等待
            if current_cycle < total_cycles:
                print(f"\n等待 {interval} 分钟后开始下一轮监控...")
                await asyncio.sleep(interval * 60)
        
        print("\n监控完成！")
            
    except KeyboardInterrupt:
        print("\n监控已手动停止")

async def analyze_specific_wallet(config):
    """分析特定钱包"""
    print("\n----- 分析特定钱包 -----")
    
    # 检查API密钥
    if not config.get("api_key"):
        print("未设置API密钥，请先设置")
        return
    
    # 获取钱包地址
    wallet = input("请输入要分析的钱包地址: ").strip()
    if not wallet:
        print("钱包地址不能为空")
        return
    
    # 获取分析天数
    days_str = input("分析最近多少天的数据 (默认30): ").strip()
    try:
        days = int(days_str) if days_str else 30
    except ValueError:
        print("无效的天数，使用默认值30")
        days = 30
    
    # 设置RPC URL
    rpc_url = input("请输入Solana RPC URL (留空使用默认): ").strip()
    if not rpc_url:
        rpc_url = "https://api.mainnet-beta.solana.com"
    
    # 设置是否使用GRPC
    use_grpc = config.get("use_grpc", True)
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    print(f"使用GRPC连接: {'是' if use_grpc else '否'}")
    if use_grpc:
        print(f"GRPC节点: {grpc_endpoint}")
    
    print(f"\n开始分析钱包 {wallet}...")
    
    # 初始化存储和API密钥
    init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 收集数据
    try:
        print("正在收集交易数据...")
        result = await collect_and_store(
            wallet, 
            rpc_url, 
            days=days,
            use_grpc=use_grpc,
            grpc_endpoint=grpc_endpoint
        )
        print(f"收集完成，获取了 {result['total_transactions']} 个交易")
        
        if result['total_transactions'] > 0:
            print("正在分析数据...")
            analysis = await analyze_stored_data(wallet, days)
            
            if analysis and "analysis_result" in analysis:
                print("\n分析完成！")
                
                # 显示简要结果
                result = analysis["analysis_result"]
                if "pattern_recognition" in result:
                    pattern = result["pattern_recognition"].get("primary_pattern", "未知")
                    print(f"主要交易模式: {pattern}")
                
                if "strategy" in result:
                    strategy = result["strategy"]
                    print(f"策略名称: {strategy.get('name', '未知')}")
                    print(f"策略描述: {strategy.get('description', '未知')}")
                    
                    if "target_selection" in strategy:
                        criteria = strategy["target_selection"].get("criteria", [])
                        print(f"目标选择标准: {', '.join(criteria)}")
                    
                    if "risk_control" in strategy:
                        risk = strategy["risk_control"]
                        print(f"风险控制: 最大仓位 {risk.get('max_position_size', '未知')}, 最大日亏损 {risk.get('max_daily_loss', '未知')}")
                
                # 询问是否导出完整结果
                if input("\n是否导出完整分析结果？(y/n): ").lower() == 'y':
                    output_file = input("请输入输出文件名 (默认为 {wallet}_analysis.json): ").strip()
                    if not output_file:
                        output_file = f"{wallet}_analysis.json"
                    
                    if await export_analysis_result(wallet, output_file):
                        print(f"分析结果已导出到 {output_file}")
            else:
                print("分析失败或无数据")
        else:
            print("没有发现交易，无法分析")
            
    except Exception as e:
        print(f"处理钱包时出错: {e}")

async def export_specific_analysis(config):
    """导出特定分析结果"""
    print("\n----- 导出分析结果 -----")
    
    # 获取钱包地址
    wallet = input("请输入钱包地址: ").strip()
    if not wallet:
        print("钱包地址不能为空")
        return
    
    # 获取存储实例
    storage = get_storage()
    
    # 获取分析结果列表
    analyses = storage.list_analysis_results(wallet)
    
    if not analyses:
        print(f"未找到钱包 {wallet} 的分析结果")
        return
    
    print(f"\n找到 {len(analyses)} 个分析结果:")
    for i, analysis in enumerate(analyses):
        print(f"  {i+1}. {analysis.get('analysis_id')} - {analysis.get('timestamp')}")
    
    # 选择要导出的结果
    index_str = input("\n请选择要导出的结果编号 (默认1): ").strip()
    try:
        index = int(index_str) - 1 if index_str else 0
        if not (0 <= index < len(analyses)):
            print("无效的编号，使用最新的分析结果")
            index = 0
    except ValueError:
        print("无效的编号，使用最新的分析结果")
        index = 0
    
    # 获取输出文件名
    output_file = input("请输入输出文件名 (默认为 {wallet}_analysis.json): ").strip()
    if not output_file:
        output_file = f"{wallet}_analysis.json"
    
    # 导出结果
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analyses[index], f, indent=2, ensure_ascii=False)
        print(f"分析结果已导出到 {output_file}")
    except Exception as e:
        print(f"导出分析结果出错: {e}")

async def real_time_monitor(config):
    """
    实时监控钱包交易
    使用GRPC流式连接，实时接收和处理交易数据
    
    Args:
        config: 配置信息
    """
    print("\n----- 实时监控 -----")
    
    if not config.get("monitored_wallets"):
        print("没有监听的钱包地址，请先添加")
        return
    
    # 选择是否使用API分析
    use_api = False
    if config.get("api_key"):
        use_api_input = input("是否启用API分析? (y/n, 默认n): ").strip().lower()
        use_api = use_api_input == 'y'
    else:
        print("未设置API密钥，无法启用API分析")
    
    # 设置分析间隔(如果启用API分析)
    analysis_interval = 0
    if use_api:
        interval_str = input("设置分析间隔(小时，默认6): ").strip()
        try:
            analysis_interval = int(interval_str) if interval_str else 6
        except ValueError:
            print("无效的间隔，使用默认值6小时")
            analysis_interval = 6
    
    # 确保GRPC端点设置
    grpc_endpoint = config.get("grpc_endpoint", DEFAULT_GRPC_ENDPOINT)
    
    print(f"\n开始实时监控 {len(config['monitored_wallets'])} 个钱包...")
    print(f"GRPC节点: {grpc_endpoint}")
    
    if use_api:
        print(f"API分析间隔: {analysis_interval}小时")
    else:
        print("API分析: 已禁用")
    
    print("按 Ctrl+C 停止监控")
    
    # 初始化存储
    storage = init_storage(api_key=config.get("api_key"), api_endpoint=config.get("api_endpoint"))
    
    # 初始化收集器(每个钱包一个收集器)
    collectors = {}
    callbacks = {}
    analysis_times = {}
    
    for wallet in config["monitored_wallets"]:
        # 创建收集器
        collectors[wallet] = SolanaCollector(
            use_grpc=True,
            grpc_endpoint=grpc_endpoint
        )
        
        # 创建交易处理回调
        callbacks[wallet] = create_transaction_callback(wallet, storage, use_api)
        
        # 初始化分析时间
        analysis_times[wallet] = time.time()
    
    try:
        # 启动监听
        tasks = []
        for wallet, collector in collectors.items():
            task = asyncio.create_task(
                monitor_wallet_transactions(
                    wallet, 
                    collector, 
                    callbacks[wallet], 
                    analysis_times, 
                    analysis_interval
                )
            )
            tasks.append(task)
        
        # 等待所有任务完成(实际上不会完成，除非发生错误或用户中断)
        await asyncio.gather(*tasks)
        
    except KeyboardInterrupt:
        print("\n监控已手动停止")
    except Exception as e:
        print(f"\n监控出错: {e}")
    finally:
        # 关闭所有收集器
        for wallet, collector in collectors.items():
            await collector.close()
            print(f"已关闭钱包 {wallet} 的监控")

def create_transaction_callback(wallet_address, storage, use_api):
    """
    创建交易处理回调函数
    
    Args:
        wallet_address: 钱包地址
        storage: 存储实例
        use_api: 是否使用API分析
        
    Returns:
        回调函数
    """
    async def callback(tx_data):
        try:
            # 打印交易信息
            tx_hash = tx_data.get("transaction_id", "unknown")
            timestamp = tx_data.get("timestamp", "unknown")
            success = "成功" if tx_data.get("success", False) else "失败"
            
            # 识别交易类型
            tx_type = "普通"
            if tx_data.get("is_swap", False):
                tx_type = "交换"
            elif tx_data.get("is_liquidity", False):
                tx_type = "流动性"
            elif tx_data.get("is_stake", False):
                tx_type = "质押"
            
            print(f"\n接收到 {wallet_address} 的{tx_type}交易: {tx_hash}")
            print(f"  时间: {timestamp}")
            print(f"  状态: {success}")
            
            # 提取交易对信息
            if tx_data.get("is_swap", False) and "swap_info" in tx_data:
                swap_info = tx_data["swap_info"]
                input_token = swap_info.get("input_token_symbol", "未知")
                output_token = swap_info.get("output_token_symbol", "未知")
                input_amount = swap_info.get("input_amount", 0)
                output_amount = swap_info.get("output_amount", 0)
                
                print(f"  交易: {input_amount} {input_token} -> {output_amount} {output_token}")
                
                # 更新全局监控的交易对
                token_pair = f"{input_token}/{output_token}"
                global monitored_pairs
                
                if token_pair not in monitored_pairs:
                    monitored_pairs[token_pair] = {
                        "start_time": time.time(),
                        "last_activity": time.time(),
                        "last_analysis": 0,
                        "transactions": [],
                        "pool_states": [],
                        "market_data": [],
                        "routes": []
                    }
                else:
                    monitored_pairs[token_pair]["last_activity"] = time.time()
                
                monitored_pairs[token_pair]["transactions"].append(tx_data)
            
            # 存储交易数据
            storage.store_transaction(tx_data, wallet_address)
            print(f"  已存储交易数据")
            
        except Exception as e:
            print(f"处理交易时出错: {e}")
    
    return callback

async def monitor_wallet_transactions(wallet_address, collector, callback, analysis_times, analysis_interval):
    """
    持续监控钱包交易
    
    Args:
        wallet_address: 钱包地址
        collector: 收集器实例
        callback: 交易处理回调
        analysis_times: 上次分析时间字典
        analysis_interval: 分析间隔(小时)
    """
    print(f"开始监控钱包 {wallet_address} 的交易...")
    
    # 监听新交易
    await collector.listen_for_transactions(wallet_address, callback)
    
    # 注意：由于listen_for_transactions是一个阻塞调用，
    # 以下代码只会在监听结束后执行，这里添加是为了保持完整性
    print(f"钱包 {wallet_address} 的监控已结束")

async def perform_periodic_analysis(wallet_address, storage, analysis_times, analysis_interval):
    """
    定期执行分析
    
    Args:
        wallet_address: 钱包地址
        storage: 存储实例
        analysis_times: 上次分析时间字典
        analysis_interval: 分析间隔(小时)
    """
    current_time = time.time()
    last_analysis = analysis_times.get(wallet_address, 0)
    
    # 检查是否需要分析
    if analysis_interval > 0 and (current_time - last_analysis) >= (analysis_interval * 3600):
        print(f"\n开始分析钱包 {wallet_address} 的交易...")
        
        # 执行分析
        analysis_result = await analyze_wallet(wallet_address)
        
        if analysis_result:
            print(f"分析完成: {wallet_address}")
        else:
            print(f"分析失败: {wallet_address}")
        
        # 更新分析时间
        analysis_times[wallet_address] = current_time

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Solana交易分析移动客户端")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 收集命令
    collect_parser = subparsers.add_parser("collect", help="收集并存储交易数据")
    collect_parser.add_argument("wallet", help="钱包地址")
    collect_parser.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC节点URL")
    collect_parser.add_argument("--days", type=int, default=7, help="收集多少天的数据")
    collect_parser.add_argument("--use-grpc", action="store_true", help="使用GRPC连接")
    collect_parser.add_argument("--grpc-endpoint", default=DEFAULT_GRPC_ENDPOINT, help="GRPC节点地址")
    
    # 分析命令
    analyze_parser = subparsers.add_parser("analyze", help="分析存储的交易数据")
    analyze_parser.add_argument("wallet", help="钱包地址")
    analyze_parser.add_argument("--days", type=int, default=30, help="分析多少天的数据")
    analyze_parser.add_argument("--api-key", help="API密钥")
    
    # 列出命令
    list_parser = subparsers.add_parser("list", help="列出存储的数据")
    list_parser.add_argument("--wallet", help="钱包地址(可选)")
    
    # 导出命令
    export_parser = subparsers.add_parser("export", help="导出分析结果")
    export_parser.add_argument("wallet", help="钱包地址")
    export_parser.add_argument("--output", help="输出文件路径")
    
    # 初始化命令
    init_parser = subparsers.add_parser("init", help="初始化存储")
    init_parser.add_argument("--dir", help="基础存储目录")
    init_parser.add_argument("--api-endpoint", help="API分析端点")
    init_parser.add_argument("--api-key", help="API访问密钥")
    
    # 交互式菜单
    menu_parser = subparsers.add_parser("menu", help="启动交互式菜单")
    
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_arguments()
    
    # 检查命令
    if args.command == "collect":
        result = await collect_and_store(args.wallet, args.rpc, args.days, args.use_grpc, args.grpc_endpoint)
        print(json.dumps(result, indent=2))
    
    elif args.command == "analyze":
        result = await analyze_stored_data(args.wallet, args.days, args.api_key)
        if result:
            # 仅打印分析结果概要，避免输出过多内容
            summary = {
                "wallet_address": result["wallet_address"],
                "analyzed_transactions": result["analyzed_transactions"],
            }
            if "analysis_result" in result and isinstance(result["analysis_result"], dict):
                if "pattern_recognition" in result["analysis_result"]:
                    summary["primary_pattern"] = result["analysis_result"]["pattern_recognition"].get("primary_pattern")
                if "strategy" in result["analysis_result"]:
                    summary["strategy_name"] = result["analysis_result"]["strategy"].get("name")
            print(json.dumps(summary, indent=2))
    
    elif args.command == "list":
        await list_wallet_data(args.wallet)
    
    elif args.command == "export":
        success = await export_analysis_result(args.wallet, args.output)
        if success:
            print("分析结果导出成功")
        else:
            print("分析结果导出失败")
    
    elif args.command == "init":
        init_storage(args.dir, args.api_endpoint, args.api_key)
        print("存储初始化完成")
    
    elif args.command == "menu" or args.command is None:
        await interactive_menu()
    
    else:
        print("请指定命令: collect, analyze, list, export, init 或 menu")

if __name__ == "__main__":
    asyncio.run(main()) 