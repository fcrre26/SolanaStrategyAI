const express = require('express');
const { SolanaParser } = require('@debridge-finance/solana-transaction-parser');
const { Connection } = require('@solana/web3.js');
const fs = require('fs').promises;
const path = require('path');

const app = express();
const port = process.env.PORT || 3000;

// 创建Solana连接
const connection = new Connection('https://api.mainnet-beta.solana.com');

// 已知的程序ID和名称映射
const KNOWN_PROGRAMS = {
    'JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB': 'Jupiter',
    'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc': 'Orca',
    '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8': 'Raydium'
};

// 初始化解析器
let parser;

// 加载IDL文件
async function loadIdls() {
    try {
        const idlsPath = path.join(__dirname, 'idls');
        const idls = [];

        // 确保idls目录存在
        try {
            await fs.access(idlsPath);
        } catch {
            await fs.mkdir(idlsPath);
            console.log('Created idls directory');
            return [];
        }

        // 读取所有IDL文件
        const files = await fs.readdir(idlsPath);
        for (const file of files) {
            if (file.endsWith('.json')) {
                const content = await fs.readFile(path.join(idlsPath, file), 'utf8');
                const programId = file.replace('.json', '');
                idls.push({
                    programId,
                    idl: JSON.parse(content)
                });
            }
        }

        console.log(`Loaded ${idls.length} IDL files`);
        return idls;
    } catch (error) {
        console.error('Error loading IDLs:', error);
        return [];
    }
}

// 初始化解析器
async function initParser() {
    try {
        const idls = await loadIdls();
        parser = new SolanaParser(idls);
        console.log('Parser initialized successfully');
    } catch (error) {
        console.error('Error initializing parser:', error);
        process.exit(1);
    }
}

// 健康检查接口
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok',
        knownPrograms: Object.keys(KNOWN_PROGRAMS)
    });
});

// 交易解析接口
app.get('/parse/:signature', async (req, res) => {
    try {
        if (!parser) {
            return res.status(500).json({ error: 'Parser not initialized' });
        }

        const signature = req.params.signature;
        console.log(`Parsing transaction: ${signature}`);

        // 获取交易信息
        const tx = await connection.getTransaction(signature, {
            maxSupportedTransactionVersion: 0,
            commitment: 'confirmed'
        });

        if (!tx) {
            return res.status(404).json({ error: 'Transaction not found' });
        }

        // 解析交易
        const parsed = await parser.parseTransaction(tx);

        // 添加程序名称
        if (parsed && parsed.instructions) {
            parsed.instructions = parsed.instructions.map(ix => ({
                ...ix,
                programName: KNOWN_PROGRAMS[ix.programId] || 'unknown'
            }));
        }

        res.json(parsed);
    } catch (error) {
        console.error(`Error parsing transaction: ${error.message}`);
        res.status(500).json({ 
            error: error.message,
            stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
        });
    }
});

// 启动服务
async function startServer() {
    await initParser();
    app.listen(port, () => {
        console.log(`Parser service running on port ${port}`);
        console.log('Known programs:', Object.keys(KNOWN_PROGRAMS));
    });
}

startServer().catch(console.error); 