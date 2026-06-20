# 币安广场自动发帖

## 目录结构
```
square-autopost/
├── scripts/
│   ├── hot_coins.py   # 抓取热度数据 + 加权打分
│   ├── chart.py       # 生成K线图PNG
│   ├── draft.py       # 生成发帖文案
│   └── run_once.py    # 整合编排(单次执行)
├── vendor/square-post/ # 官方发帖skill(本地已放好,见下方说明)
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

预期输出:终端会打印完整的文案预览,并在 `data/tmp/` 目录下生成一张K线图PNG。
**这一步不会调用Square API,纯本地产物,可以反复跑、随便改模板,不消耗发帖额度。**

打开 `data/tmp/chart_xxx.png` 用看图工具检查K线图是否正常、文案是否通顺、链接格式对不对。

如果这步报"热度榜为空"——大概率是web3.binance.com那几个接口临时不可用或者被限流了,可以单独跑:
```bash
python3 scripts/hot_coins.py --top 10
```
看看具体是哪个信号源失败(脚本会把每个信号源的报错单独打出来)。

## Step 3: 真实发一条,去广场上检查实际效果

确认dry-run的文案和图片都满意后,去掉 `--dry-run` 真发一条:

```bash
python3 scripts/run_once.py --rank 0
```

成功的话终端会打印类似:
```
Publishing...
Success! ID: 123456789
Link: https://www.binance.com/square/post/123456789
```

**拿着这个Link直接打开,在浏览器/App里检查:**
- [ ] `$BTC` 这种cashtag是否正确渲染成可点击标签
- [ ] 正文里的 `https://www.binance.com/zh-CN/futures/BTCUSDT` 链接点开能不能跳转,是纯文本链接还是自动变成了带预览图的卡片(这个我没法在文档里确认,需要你实测)
- [ ] K线图是否正常显示、清晰度够不够
- [ ] 整体排版在手机App里看起来是否拥挤/合适

如果哪里不满意,改 `scripts/draft.py` 的模板或者 `scripts/chart.py` 的画图参数,重新回到Step 2用`--dry-run`迭代,确认OK了再发一条真实验证,如此反复,不用每次都用GitHub Actions跑。

## Step 4: 接入 GitHub Actions 定时发帖

1. 把这个项目push到你的GitHub仓库(建议private)
2. 仓库 Settings → Secrets and variables → Actions → New repository secret
   - 添加 `BINANCE_SQUARE_OPENAPI_KEY`
   - 如果要Telegram通知,也加 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_USER_ID`
3. workflow文件已经写好是每15分钟跑一次(`.github/workflows/auto-post.yml`),也可以先去Actions页面手动点 "Run workflow" 立即测一次,不用等定时触发
4. 观察 Actions 的运行日志,确认连续跑几次都正常,再放心让它按计划长期跑

## 已知限制 / 要留意的点

1. **`--rank 0` 默认只发热度榜第1名** — 如果15分钟跑一次、榜单变化不大,短期内会重复发同一个币。前面讨论过你决定不做去重,这里保留原样,如果发现刷屏感太重,后续可以改成 `--rank` 轮换或者从前N名里随机抽。
2. **交易链接是纯文本URL**,不确定Square前端会不会自动渲染成卡片,需要Step 3实测确认。
3. **GitHub Actions的schedule不保证精确到分钟**,高峰期可能延迟,不要指望严格的15分钟节奏。
4. **24h成交额门槛 `MIN_QUOTE_VOLUME = 5_000_000`** 写在 `hot_coins.py` 顶部,嫌太严/太松自己改这个数字。
5. 高频发帖+内容相似度高,有被判定为垃圾内容/降权的风险(前面已经提过),实际跑起来注意看Square后台的内容质量数据反馈。
