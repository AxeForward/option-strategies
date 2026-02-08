# option-strategies

一个用于研究「加密期权策略 + 永续期货对冲」的小项目：

- 期权：Binance（欧式期权）
- 永续期货：Paradex（用于获取现价/对冲腿）
- 无风险利率：FRED（美国国债利率时间序列）

本仓库目前主要做两件事：
1. 拉取实时行情（期权链 + 永续 BBO + 可选的无风险利率）；
2. 将多腿策略在“到期收益/盈亏”维度做快速评估并画图（含一个静态 delta 对冲腿的示例）。

## 数据源

### Binance 期权（Options）
- 脚本：`src/get_asset_option_t_quote.py`
- 使用 Binance Options API（`https://eapi.binance.com`）批量拉取：
  - 合约信息：`/eapi/v1/exchangeInfo`
  - 盘口/成交量：`/eapi/v1/ticker`（bulk）
  - 标记价与 Greeks/IV：`/eapi/v1/mark`（bulk，包含 `delta` 等）
- 本项目将数据整理为 `dict[expiry_date] -> pandas.DataFrame`，便于按到期日挑选与筛选。

### Paradex 永续（Perpetual Futures）
- 脚本：`src/fetch_market_data.py`
- 使用 Paradex BBO 接口获取永续的最优买卖价与中间价（用于 spot/对冲腿）：
  - `GET https://api.prod.paradex.trade/v1/bbo/{symbol}`

### FRED 无风险利率（Risk-free rate）
- 脚本：`src/fetch_market_data.py`
- 使用 FRED `series/observations` 拉取利率时间序列（默认 `DGS3MO`：3M Treasury CMT）。
- 需要在环境变量或 `.env` 中提供 `FRED_API_KEY`（仅当你使用该功能时需要）。

## 代码结构（`src/`）

- `src/get_asset_option_t_quote.py`：从 Binance 批量拉取期权链报价与 Greeks（含 delta），并按到期日返回 `DataFrame`；也提供 `print_option_quotes()` 方便直接打印表格。
- `src/fetch_market_data.py`：
  - `get_paradex_futures_data()`：获取 Paradex 永续 BBO（bid/ask/mid 等）。
  - `get_fred_risk_free_rate()`：获取 FRED 无风险利率时间序列。
- `src/strategy_evaluation.py`：
  - `calculate_strategy_pnl()`：按“到期内在价值”计算多腿组合在一组标的价格区间上的 PnL（支持 `call/put/futures`）。
  - `plot_strategy_payoff()`：用 Plotly 画图并输出到 `imgs/`（HTML + 可选 PNG）。
  - `calculate_quantlib_greeks()`：用 QuantLib 计算欧式期权 Greeks（可选工具函数）。

## 示例与输出

`static_strategy_examples.py` 包含两个示例：
- `example_iron_condor()`：基于实时期权链构建 Iron Condor，并加入 1 次静态 delta 对冲腿（Paradex 永续）。
- `example_gamma_scalping()`：基于实时 ATM Straddle 的“gamma scalping 模板”（同样加入 1 次静态 delta 对冲腿）。

图表默认输出到 `imgs/`（示例见 `imgs/*.html` / `imgs/*.png`）。

## 新增一个期权策略（含 delta 对冲）怎么改 `static_strategy_examples.py`

推荐直接照着现有的 `example_iron_condor()` / `example_gamma_scalping()` 的模式加一个新函数：

1. 新建函数，例如 `example_my_strategy(symbol, expiry_date, ...)`。
2. 获取对冲标的现价（永续 mid）：调用 `get_paradex_futures_data(f\"{symbol}-USD-PERP\")`。
3. 获取期权链（含 bid/ask/delta）：调用 `get_option_quotes(f\"{symbol}USDT\", expiry_date)`。
4. 选腿并用 bid/ask 估计成交价，组装 `option_legs`：
   - 每条腿的字典结构与含义（见 `src/strategy_evaluation.py`）：
     - `type`: `call` / `put` / `futures`
     - `action`: `buy` / `sell`
     - `strike`: 行权价（期权腿需要）
     - `premium`: 成交价（建议 buy 用 ask，sell 用 bid）
     - `quantity`: 数量（支持小数）
5. 计算期权净 delta，并生成对冲腿：
 - 期权净 delta 计算要考虑买卖方向与数量：`buy` 记正、`sell` 记负（再乘 `quantity`）。
 - `hedge_qty = -net_option_delta`，然后把对冲腿作为 `type='futures'` 追加到 `legs`。
6. 调用评估与画图：
 - `pnl_data = calculate_strategy_pnl(legs, spot_price=spot, price_range=...)`
 - `plot_strategy_payoff(..., output_html=..., output_png=...)`
7. （可选）在 `if __name__ == "__main__":` 中添加你的函数调用，方便直接运行。

提示：当前示例的对冲是“静态/一次性”的（只在建仓时用期权链上的 delta 做一次对冲），后续的动态对冲属于 TODO。

## TO DO / Roadmap

- 动态对冲（随时间/价格更新 hedge，加入交易成本、滑点、资金费率等）
- 历史回测（数据落盘、复权/对齐、事件驱动回测框架）
- 实盘交易（下单/风控/监控/告警）

欢迎提 PR / Issue 一起完善。
