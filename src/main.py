"""
Solana交易策略分析工具主程序 - 专注于监控和数据收集
"""
import asyncio
import logging
import os
import time
import json
from datetime import datetime

from .monitor.wallet_monitor import WalletMonitor
from .storage.database import Database
from .analyzer.ai_client import analyze_trading_pattern, get_latest_analysis

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler(  # 输出到文件
            f'logs/solana_analyzer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
    ]
)

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = "config.json"

def setup_environment():
    """设置运行环境"""
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    
    # 创建数据目录
    os.makedirs('data/transactions', exist_ok=True)
    os.makedirs('data/pools', exist_ok=True)
    os.makedirs('data/market', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    
    # 初始化数据库
    db = Database()
    db.initialize()
    
    logger.info(f"环境初始化完成: {os.getcwd()}")
    return db

def load_config():
    """加载配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置出错: {e}")
    
    # 返回默认配置
    return {
        "wallet_address": "",
        "ark_api_key": "",
        "monitored_wallets": []
    }

def save_config(config):
    """保存配置"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"保存配置出错: {e}")

async def start_monitor(wallet_address: str, db: Database):
    """启动钱包监控
    
    Args:
        wallet_address: 要监控的钱包地址
        db: 数据库实例
    """
    logger.info(f"开始监控钱包: {wallet_address}")
    
    try:
        # 创建钱包监控器
        monitor = WalletMonitor(wallet_address, db)
        
        # 开始监控
        await monitor.start()
        
    except KeyboardInterrupt:
        logger.info("监控服务被用户终止")
    except Exception as e:
        logger.error(f"监控服务出错: {e}")
    finally:
        logger.info("监控服务已停止")

async def analyze_wallet(wallet_address: str, days: int, db: Database):
    """分析钱包数据
    
    Args:
        wallet_address: 要分析的钱包地址
        days: 分析最近几天的数据
        db: 数据库实例
    """
    logger.info(f"开始分析钱包 {wallet_address} 最近 {days} 天的数据")
    
    try:
        # 计算时间范围
        timestamp = int((time.time() - days * 86400) * 1000)
        
        # 获取交易对
        pairs = await db.get_trading_pairs(wallet_address, since_timestamp=timestamp)
        
        if not pairs:
            logger.info(f"没有发现 {wallet_address} 在最近 {days} 天内的交易对")
            return
            
        logger.info(f"发现 {len(pairs)} 个交易对")
        
        # 读取API密钥
        config = load_config()
        api_key = config.get("ark_api_key", "")
        
        if not api_key:
            logger.error("未设置火山引擎API密钥")
            return
        
        # 对每个交易对进行分析
        from openai import OpenAI
        client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=api_key
        )
        
        for pair in pairs:
            logger.info(f"分析交易对 {pair}")
            
            # 获取交易数据
            transactions = await db.get_transactions(wallet_address, pair, since_timestamp=timestamp)
            
            if not transactions:
                logger.warning(f"未找到交易对 {pair} 的交易数据")
                continue
                
            # 调用解析服务解析交易数据
            from .analyzer.transaction_parser import parse_transactions
            parsed_data = await parse_transactions(transactions)
            
            if not parsed_data:
                logger.warning(f"交易对 {pair} 的数据解析失败")
                continue
                
            # 使用解析后的数据进行分析
            analysis = await analyze_trading_pattern(client, pair, parsed_data)
            
            if analysis:
                logger.info(f"交易对 {pair} 分析完成")
                
                # 保存分析报告
                report_dir = f"reports/{wallet_address}"
                os.makedirs(report_dir, exist_ok=True)
                
                report_file = f"{report_dir}/analysis_{pair.replace('/', '_')}_{int(time.time())}.json"
                with open(report_file, 'w') as f:
                    json.dump({
                        "pair": pair,
                        "parsed_data": parsed_data,
                        "analysis": analysis
                    }, f, indent=2)
                    
                logger.info(f"分析报告已保存到 {report_file}")
            else:
                logger.warning(f"交易对 {pair} 分析失败")
                
        logger.info("所有交易对分析完成")
        
    except Exception as e:
        logger.error(f"分析过程出错: {e}")

async def list_reports():
    """列出所有策略分析报告"""
    if not os.path.exists("reports"):
        print("报告目录不存在")
        return
        
    print("\n===== 策略分析报告列表 =====")
    print("(系统根据监控数据自动生成)")
    
    # 统计报告总数
    total_reports = 0
    all_reports = []
    
    # 遍历钱包目录
    for wallet_dir in os.listdir("reports"):
        wallet_path = os.path.join("reports", wallet_dir)
        
        if os.path.isdir(wallet_path):
            print(f"\n钱包: {wallet_dir}")
            
            # 列出该钱包的所有报告
            reports = []
            for report_file in os.listdir(wallet_path):
                if report_file.endswith(".json"):
                    report_path = os.path.join(wallet_path, report_file)
                    report_time = os.path.getmtime(report_path)
                    
                    # 解析报告文件名
                    parts = report_file.split('_')
                    if len(parts) >= 3:
                        pair = parts[1] + "/" + parts[2].split('.')[0]
                    else:
                        pair = report_file
                    
                    # 读取报告基本信息
                    report_info = {
                        "index": len(reports) + 1,
                        "file": report_file,
                        "path": report_path,
                        "time": report_time,
                        "pair": pair,
                        "wallet": wallet_dir
                    }
                    
                    reports.append(report_info)
                    all_reports.append(report_info)
            
            # 按时间排序
            reports.sort(key=lambda x: x["time"], reverse=True)
            
            # 显示报告基本信息
            for report in reports:
                print(f"  {report['index']}. {report['pair']} - {datetime.fromtimestamp(report['time']).strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"     文件: {report['path']}")
                
            total_reports += len(reports)
            
    print(f"\n共 {total_reports} 个策略分析报告")
    
    if total_reports > 0:
        # 提供查看详细报告的选项
        try:
            choice = input("\n输入报告编号查看详细内容 (输入0返回): ")
            if choice.isdigit() and int(choice) > 0 and int(choice) <= total_reports:
                report_index = int(choice)
                selected_report = None
                
                for report in all_reports:
                    if report['index'] == report_index:
                        selected_report = report
                        break
                
                if selected_report:
                    print(f"\n===== 报告详情: {selected_report['pair']} =====")
                    print(f"时间: {datetime.fromtimestamp(selected_report['time']).strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"文件: {selected_report['path']}")
                    print("\n原始报告内容:")
                    print("=" * 80)
                    
                    try:
                        with open(selected_report['path'], 'r') as f:
                            report_content = json.load(f)
                            # 直接输出完整的报告内容
                            print(json.dumps(report_content, indent=2, ensure_ascii=False))
                            print("=" * 80)
                            
                    except Exception as e:
                        logger.error(f"读取报告内容失败: {e}")
                        print(f"读取报告内容失败: {e}")
                
        except Exception as e:
            logger.error(f"查看报告详情出错: {e}")

async def cleanup_data(days: int, db: Database):
    """清理旧数据
    
    Args:
        days: 保留最近几天的数据
        db: 数据库实例
    """
    logger.info(f"清理 {days} 天前的数据")
    
    try:
        # 计算时间戳
        timestamp = int((time.time() - days * 86400) * 1000)
        
        # 清理各类数据
        tx_count = await db.delete_old_transactions(timestamp)
        pool_count = await db.delete_old_pool_states(timestamp)
        market_count = await db.delete_old_market_states(timestamp)
        
        # 压缩数据库
        await db.vacuum()
        
        logger.info(f"数据清理完成。删除了 {tx_count} 条交易记录, {pool_count} 条池子记录, {market_count} 条市场记录")
        print(f"数据清理完成。删除了 {tx_count} 条交易记录, {pool_count} 条池子记录, {market_count} 条市场记录")
        
    except Exception as e:
        logger.error(f"清理数据出错: {e}")

async def show_status(db: Database):
    """显示系统状态
    
    Args:
        db: 数据库实例
    """
    logger.info("查看系统状态")
    
    try:
        # 获取数据统计
        tx_count = await db.get_transaction_count()
        pool_count = await db.get_pool_count()
        market_count = await db.get_market_count()
        
        # 获取监控的钱包数量
        wallets = await db.get_monitored_wallets()
        
        # 获取数据库大小
        db_size = await db.get_database_size()
        
        # 显示状态
        print("===== Solana交易策略分析工具状态 =====")
        print(f"监控钱包数: {len(wallets)}")
        for wallet in wallets:
            print(f"  - {wallet}")
            
        print("\n--- 数据统计 ---")
        print(f"交易记录: {tx_count} 条")
        print(f"池子记录: {pool_count} 条")
        print(f"市场记录: {market_count} 条")
        
        print("\n--- 存储统计 ---")
        print(f"数据库大小: {db_size/1024/1024:.2f} MB")
        
        # 检查系统运行情况
        print("\n--- 系统状态 ---")
        print(f"CPU使用率: {os.getloadavg()[0]:.2f}")
        print(f"内存使用: {os.popen('free -m').readlines()[1].split()[2]} MB")
        print(f"磁盘空间: {os.popen('df -h .').readlines()[1].split()[3]}")
        
    except Exception as e:
        logger.error(f"查看状态出错: {e}")

def print_menu():
    """打印主菜单"""
    print("\n===== Solana交易策略分析工具 =====")
    print("1. 设置监控钱包地址")
    print("2. 设置火山引擎API密钥")
    print("3. 开始监控")
    print("4. 查看分析报告")
    print("5. 手动分析数据")
    print("6. 系统状态")
    print("7. 数据清理")
    print("0. 退出")
    
    return input("\n请选择功能 (0-7): ")

async def interactive_menu():
    """交互式菜单"""
    # 设置环境
    db = setup_environment()
    
    while True:
        choice = print_menu()
        
        if choice == "1":
            # 设置监控钱包地址
            config = load_config()
            print("\n当前监控钱包:", config.get("wallet_address", "未设置"))
            
            wallet = input("请输入要监控的钱包地址 (留空保持不变): ")
            if wallet:
                config["wallet_address"] = wallet
                if wallet not in config.get("monitored_wallets", []):
                    config.setdefault("monitored_wallets", []).append(wallet)
                save_config(config)
                print(f"已设置监控钱包: {wallet}")
                
        elif choice == "2":
            # 设置火山引擎API密钥
            config = load_config()
            current_key = config.get("ark_api_key", "")
            
            if current_key:
                print(f"\n当前API密钥: {current_key[:4]}...{current_key[-4:]}")
            else:
                print("\n当前未设置API密钥")
                
            api_key = input("请输入火山引擎API密钥 (留空保持不变): ")
            if api_key:
                config["ark_api_key"] = api_key
                save_config(config)
                print("API密钥已设置")
                
        elif choice == "3":
            # 开始监控
            config = load_config()
            wallet = config.get("wallet_address", "")
            
            if not wallet:
                print("请先设置要监控的钱包地址")
                continue
                
            print(f"\n开始监控钱包: {wallet}")
            print("(按Ctrl+C停止监控)")
            
            try:
                await start_monitor(wallet, db)
            except KeyboardInterrupt:
                print("\n监控已停止")
                
        elif choice == "4":
            # 查看分析报告
            await list_reports()
                
        elif choice == "5":
            # 手动分析数据
            config = load_config()
            wallet = config.get("wallet_address", "")
            
            if not wallet:
                print("请先设置要分析的钱包地址")
                continue
                
            days_str = input("\n分析最近几天的数据 (默认7天): ")
            days = int(days_str) if days_str.isdigit() else 7
            
            print(f"\n开始分析钱包 {wallet} 最近 {days} 天的数据...")
            await analyze_wallet(wallet, days, db)
                
        elif choice == "6":
            # 系统状态
            await show_status(db)
                
        elif choice == "7":
            # 数据清理
            days_str = input("\n保留最近几天的数据 (默认90天): ")
            days = int(days_str) if days_str.isdigit() else 90
            
            await cleanup_data(days, db)
                
        elif choice == "0":
            # 退出
            print("\n退出程序")
            break
            
        else:
            print("\n无效的选择，请重试")
            
        # 等待用户按任意键继续
        input("\n按Enter键继续...")

async def main():
    """主程序入口"""
    logger.info("Solana交易策略监控工具启动")
    
    try:
        # 启动交互式菜单
        await interactive_menu()
            
    except Exception as e:
        logger.error(f"程序出错: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户终止")
    except Exception as e:
        logger.error(f"程序出错: {e}")
        os.sys.exit(1) 
