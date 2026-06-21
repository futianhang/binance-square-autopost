# 币安广场自动发帖

## 目录结构
```
square-autopost/
├── scripts/
│   ├── market_data.py # 抓取行情: BTC/ETH固定 + 24h涨跌幅绝对值前N名("市场热点")
│   ├── draft.py        # 生成纯文本发帖文案
│   └── run_once.py     # 整合编排(单次执行)
├── vendor/square-post/  # 官方发帖skill(本地已放好,见下方说明)
├── .github/workflows/auto-post.yml  # 定时任务
├── .env.example
└── requirements.txt
```

## Step 0: 环境准备(在你自己的机器上,不是这个对话里)

```bash
# Python 依赖
pip install -r requirements.txt

# Node 18+ (square-post skill需要,跑 node --version 确认)
```

`vendor/square-post/` 这个目录我已经从官方仓库
(https://github.com/binance/binance-skills-hub/tree/main/skills/binance/square-post)
拷贝好了,不需要你再装。如果以后官方更新了脚本,重新拉一下覆盖即可。

## Step 1: 申请 API Key

去 https://www.binance.com/square/creator-center/home 创建Square OpenAPI Key。
**每个创作者账号只能生成1个**,丢了只能重新生成(旧key失效),生成后立刻填进 `.env`。

```bash
cp .env.example .env
# 编辑 .env, 填入 BINANCE_SQUARE_OPENAPI_KEY
```

## Step 2: 本地测试 —— 先用 `--dry-run`,不会真实发帖

```bash
source .env  # 或者用 export $(cat .env | xargs), 把环境变量加载进shell
python3 scripts/run_once.py --dry-run
```

预期输出:终端会打印完整的文案预览,并在 `data/tmp/` 目录下生成对应的 `market_*.json`(原始行情数据)和 `draft_*.txt`(文案)。
**这一步不会调用Square API,纯本地产物,可以反复跑、随便改模板,不消耗发帖额度。**

打开 `data/tmp/draft_xxx.txt` 检查文案格式是否符合预期、emoji是否正常显示。

如果这步报"行情数据是空的"——大概率是 data-api.binance.vision 接口临时不可用或者被限流了,可以单独跑:
```bash
python3 scripts/market_data.py --top 3
```
看看具体报什么错(脚本会把请求失败的原因打到stderr)。

## Step 3: 真实发一条,去广场上检查实际效果

确认dry-run的文案满意后,去掉 `--dry-run` 真发一条:

```bash
python3 scripts/run_once.py
```

成功的话终端会打印类似:
```
Publishing text post...
Success! ID: 123456789
Link: https://www.binance.com/square/post/123456789
```

**拿着这个Link直接打开,在浏览器/App里检查:**
- [ ] `$BTC`、`$ETH` 这种cashtag是否正确渲染成可点击标签
- [ ] 整体排版(emoji、换行、空行)在手机App里看起来是否合适
- [ ] 涨跌幅、成交额、价格的数值显示是否符合预期(尤其是PEPE/SHIB这种小数点很多位的meme币)

如果哪里不满意,改 `scripts/draft.py` 的模板,重新回到Step 2用`--dry-run`迭代,确认OK了再发一条真实验证,如此反复,不用每次都用GitHub Actions跑。

## Step 4: 接入 GitHub Actions 定时发帖

1. 把这个项目push到你的GitHub仓库(建议private)
2. 仓库 Settings → Secrets and variables → Actions → New repository secret
   - 添加 `BINANCE_SQUARE_OPENAPI_KEY`
   - 如果要Telegram通知,也加 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_USER_ID`
3. workflow文件已经写好是标准每15分钟跑一次(`.github/workflows/auto-post.yml`,cron为 `*/15 * * * *`,即每小时的0/15/30/45分触发),也可以先去Actions页面手动点 "Run workflow" 立即测一次,不用等定时触发
4. 观察 Actions 的运行日志,确认连续跑几次都正常,再放心让它按计划长期跑

## 文案格式说明

`draft.py` 生成的文案是纯文本,固定结构:

```
行情快报（2026-06-18 18:00 北京时间）

BTC
💰 最新价：$67,234
📈 24h涨跌幅：+2.3%
📊 24h成交额：$32.5B
😊 市场情绪：📈 温和看涨

ETH
💰 最新价：$1,734
📈 24h涨跌幅：+1.3%
📊 24h成交额：$12.5B
😊 市场情绪：📈 温和看涨

🔥 市场热点：

$PEPE
💰 最新价：...
...(按24h涨跌幅绝对值排序的前3名,带$cashtag)
```

- **BTC、ETH 每次必发**,不参与"市场热点"排名。
- **市场热点** = 剔除BTC/ETH/稳定币/杠杆代币(UP/DOWN/BULL/BEAR后缀)、且24h成交额 ≥ `MIN_QUOTE_VOLUME`(默认500万USDT,在 `market_data.py` 顶部改)之后,按**24h涨跌幅绝对值**降序取前3名 —— 涨得猛、跌得猛的都会被选中,不再用之前那套加权热度打分。
- **关于 `$cashtag`**:广场官方限制**每条帖子最多3个 `$coin` cashtag**(超过会被API直接拒绝,报错220095)。所以文案里 **BTC/ETH 不带 `$`**(纯文字),**`$` 留给"市场热点"的最多前3名**,正好卡在上限内。如果 `--top` 配置超过3,第4名开始也会自动降级成不带 `$` 的纯文本,不会因为超额导致整条发帖失败(逻辑在 `draft.py` 的 `MAX_CASHTAGS` 常量和 `coin_block()`)。
- **市场情绪**(`draft.py` 里的 `sentiment()` 函数)按24h涨跌幅划分5档,阈值是拍的经验值,嫌不准自己改:
  - `≥ +5%` → 🔥 强势看涨
  - `+1% ~ +5%` → 📈 温和看涨
  - `-1% ~ +1%` → 😐 横盘整理
  - `-5% ~ -1%` → 📉 温和看跌
  - `≤ -5%` → 🥶 恐慌下跌
- **价格显示精度**(`fmt_price()`)按数量级自适应:≥1美元用2位小数,小于1美元的meme币会自动加到4/6/8位小数,避免PEPE这种币显示成 `$0.00`。

## 已知限制 / 要留意的点

1. **`market_data.py` 默认取热点前3名(`--top 3`)**,正好对应广场3个cashtag的上限,**不建议调大这个数字**——调大了"市场热点"超出的部分会自动变成不带`$`的纯文本(不会发帖失败,但效果打折扣)。
2. **GitHub Actions的schedule不保证精确到分钟**,高峰期可能延迟,不要指望严格的15分钟节奏。
3. **"市场热点"成交额门槛 `MIN_QUOTE_VOLUME = 5_000_000`** 写在 `market_data.py` 顶部,嫌太严/太松自己改这个数字。
4. **稳定币/杠杆代币排除列表**(`EXCLUDE_SYMBOLS` / `EXCLUDE_SUFFIXES`)是手动维护的,币安新上稳定币或杠杆代币如果没加进去,理论上可能混进"市场热点",发现了就去 `market_data.py` 里补一下。
5. 高频发帖+内容相似度高(每次都是同样的固定结构),有被判定为垃圾内容/降权的风险,实际跑起来注意看Square后台的内容质量数据反馈。
