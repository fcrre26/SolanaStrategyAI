"""
AI analysis client implementation using Volcano Engine (火山引擎).
This module handles the AI-powered analysis of trading patterns and strategy generation.
"""

import os
import json
import time
import asyncio
from openai import OpenAI
from ..storage.database import init_db
from ..utils.helpers import (
    get_trading_history,
    get_price_history,
    get_depth_history,
    get_volume_history,
    get_pool_history,
    get_market_sentiment,
    get_liquidity_data,
    get_routing_efficiency,
    get_execution_performance,
    get_slippage_analysis
)

async def determine_analysis_interval(token_pair):
    """根据数据量确定分析间隔"""
    db = init_db()
    cursor = db.cursor()
    
    # 获取最近24小时的数据量
    query = """
    SELECT COUNT(*) as count 
    FROM base_transactions 
    WHERE (input_token = ? OR output_token = ?) 
    AND timestamp > ?
    """
    
    token_addresses = token_pair.split("/")
    if len(token_addresses) != 2:
        return 21600  # 默认6小时
    
    token_a, token_b = token_addresses
    twenty_four_hours_ago = int(time.time() * 1000) - (24 * 3600 * 1000)
    
    cursor.execute(query, (token_a, token_b, twenty_four_hours_ago))
    result = cursor.fetchone()
    data_count = result['count']
    
    db.close()
    
    # 根据数据量动态调整分析间隔
    if data_count > 1000:  # 数据量大
        return 21600  # 6小时
    elif data_count > 500:  # 数据量中等
        return 43200  # 12小时
    else:  # 数据量小
        return 86400  # 24小时

async def schedule_analysis(token_pair):
    """调度分析任务"""
    while True:
        try:
            # 确定分析间隔
            interval = await determine_analysis_interval(token_pair)
            
            # 初始化 AI 客户端
            ai_client = OpenAI(
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                api_key=os.environ.get("ARK_API_KEY")
            )
            
            # 执行分析
            analysis_result = await analyze_trading_pattern(ai_client, token_pair)
            
            if analysis_result:
                # 存储分析结果
                await store_analysis_result(token_pair, analysis_result)
                print(f"Analysis completed for {token_pair}, next analysis in {interval/3600} hours")
            
            # 等待下一次分析
            await asyncio.sleep(interval)
            
        except Exception as e:
            print(f"Error in analysis schedule: {e}")
            await asyncio.sleep(300)  # 发生错误时等待5分钟后重试

async def analyze_trading_pattern(ai_client, token_pair):
    """使用火山引擎分析交易模式"""
    try:
        # 收集分析所需数据
        analysis_data = await collect_analysis_data(token_pair)
        
        # 构建系统提示
        system_prompt = """
你是一位专业的加密货币交易策略分析师，精通 Solana 生态系统中的交易策略分析。
请根据提供的历史交易数据、市场数据和池子数据，分析并提供详细的交易策略建议。
输出必须是有效的 JSON 格式，包含选标策略、买入策略、卖出策略、仓位管理、自动化流程和风险控制等完整内容。
"""

        # 构建用户提示
        user_prompt = f"""
请分析以下交易数据并提供完整的策略建议：

交易对: {token_pair}
分析数据: {json.dumps(analysis_data, indent=2)}

请提供以下方面的具体建议：
1. 交易对选择标准
2. 买入策略和触发条件
3. 卖出策略和风险控制
4. 仓位管理方案
5. 自动化执行流程
"""

        # 调用火山引擎API
        completion = ai_client.chat.completions.create(
            model="deepseek-v3-250324",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        # 获取分析结果
        analysis_result = completion.choices[0].message.content
        
        # 验证JSON格式
        try:
            json.loads(analysis_result)
            return analysis_result
        except json.JSONDecodeError:
            print("Warning: Analysis result is not valid JSON")
            return json.dumps({
                "error": "Invalid JSON format",
                "raw_result": analysis_result
            })
            
    except Exception as e:
        print(f"Error in analysis: {e}")
        return None

async def collect_analysis_data(token_pair):
    """收集分析所需的所有数据"""
    return {
        "token_pair": token_pair,
        "trading_history": await get_trading_history(token_pair),
        "price_history": await get_price_history(token_pair),
        "depth_history": await get_depth_history(token_pair),
        "volume_history": await get_volume_history(token_pair),
        "pool_history": await get_pool_history(token_pair),
        "market_sentiment": await get_market_sentiment(token_pair),
        "liquidity_data": await get_liquidity_data(token_pair),
        "routing_efficiency": await get_routing_efficiency(token_pair),
        "execution_performance": await get_execution_performance(token_pair),
        "slippage_analysis": await get_slippage_analysis(token_pair)
    }

async def store_analysis_result(token_pair, result):
    """存储分析结果到数据库"""
    db = init_db()
    cursor = db.cursor()
    
    try:
        parsed_result = json.loads(result)
        
        query = """
        INSERT INTO strategy_analysis (
            token_pair,
            analysis_time,
            trigger_conditions,
            execution_strategy,
            risk_control,
            capital_management
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(query, (
            token_pair,
            int(time.time() * 1000),
            json.dumps(parsed_result.get("target_selection", {})),
            json.dumps(parsed_result.get("buy_strategy", {})),
            json.dumps(parsed_result.get("risk_control", {})),
            json.dumps(parsed_result.get("position_management", {}))
        ))
        
        db.commit()
    except Exception as e:
        print(f"Error storing analysis result: {e}")
        db.rollback()
    finally:
        db.close()

async def get_latest_analysis(token_pair):
    """获取最新的分析结果"""
    db = init_db()
    cursor = db.cursor()
    
    try:
        query = """
        SELECT * FROM strategy_analysis
        WHERE token_pair = ?
        ORDER BY analysis_time DESC
        LIMIT 1
        """
        
        cursor.execute(query, (token_pair,))
        result = cursor.fetchone()
        
        if result:
            return {
                "token_pair": result["token_pair"],
                "analysis_time": result["analysis_time"],
                "trigger_conditions": json.loads(result["trigger_conditions"]),
                "execution_strategy": json.loads(result["execution_strategy"]),
                "risk_control": json.loads(result["risk_control"]),
                "capital_management": json.loads(result["capital_management"])
            }
        return None
    finally:
        db.close() 