"""Reporting: a plain-text report (always available) and a rich HTML tearsheet
(via quantstats, lazily imported).

The text report shows its work: a config/provenance header (universe, factor
blend, period, rebalance, costs) so two different strategies never print
look-alike reports, then the data-quality block, then performance metrics.
Output is kept ASCII so it renders on any console (Windows cp1252 included).
"""

from __future__ import annotations

from pathlib import Path

from alphaforge.engine.backtest import BacktestResult
from alphaforge.metrics.performance import compute_metrics

_WIDTH = 44

_LABELS = {
    "cagr": "CAGR",
    "ann_volatility": "Ann. Volatility",
    "sharpe": "Sharpe",
    "sortino": "Sortino",
    "max_drawdown": "Max Drawdown",
    "calmar": "Calmar",
    "hit_rate": "Hit Rate",
    "total_return": "Total Return",
}
_AS_PCT = {"cagr", "ann_volatility", "max_drawdown", "hit_rate", "total_return"}


def _fmt_params(name: str, params: dict) -> str:
    params = params or {}
    if name == "value":
        provider = params.get("provider", "edgar")
        metric = params.get("metric", "book_to_market")
        return f"({provider} {metric})"
    if params:
        return "(" + ", ".join(f"{k}={v}" for k, v in params.items()) + ")"
    return ""


def _factor_lines(result: BacktestResult) -> list[str]:
    fcfg = result.config.factor
    params = fcfg.params or {}
    if fcfg.name == "composite":
        lines = ["Factor:     composite"]
        for c in params.get("components", []):
            cn = c["name"]
            weight = c.get("weight", 1.0)
            extra = _fmt_params(cn, c.get("params", {}))
            lines.append(f"              {cn:<15} x{weight:<4g} {extra}")
        return lines
    return [f"Factor:     {fcfg.name} {_fmt_params(fcfg.name, params)}".rstrip()]


def _universe_desc(result: BacktestResult) -> str:
    cfg = result.config
    u = cfg.data.resolved_universe()
    q = result.quality
    total = q.n_symbols if q is not None else len(cfg.data.symbols or [])
    excluded = len(q.no_data) if q is not None else 0
    with_data = total - excluded
    if u.kind == "static":
        kind = f"static, {total} symbols"
    else:
        fname = Path(u.membership_file).name if u.membership_file else "membership"
        kind = f"point-in-time ({fname}), {total} symbols"
    return f"{kind} ({with_data} with data, {excluded} excluded)"


def _universe_line(result: BacktestResult) -> str:
    return f"Universe:   {_universe_desc(result)}"


def _factor_desc(result: BacktestResult) -> str:
    """Single-line factor description (for the HTML provenance block)."""
    fcfg = result.config.factor
    params = fcfg.params or {}
    if fcfg.name == "composite":
        parts = [
            f"{c['name']} x{c.get('weight', 1.0):g} {_fmt_params(c['name'], c.get('params', {}))}".strip()
            for c in params.get("components", [])
        ]
        return "composite: " + "; ".join(parts)
    return f"{fcfg.name} {_fmt_params(fcfg.name, params)}".strip()


def _settings_desc(result: BacktestResult) -> str:
    cfg = result.config
    costs = f"{cfg.costs.commission_bps:g}+{cfg.costs.slippage_bps:g} bps"
    return f"{cfg.rebalance.value}, Top-N {cfg.top_n}, Costs {costs}"


def _quality_desc(result: BacktestResult) -> str:
    q = result.quality
    if q is None:
        return "n/a"
    bits = []
    if q.no_data:
        bits.append("NO DATA: " + ", ".join(q.no_data))
    if q.partial:
        bits.append("partial: " + ", ".join(f"{s} {q.coverage[s]:.0%}" for s in q.partial))
    if q.non_positive:
        bits.append(f"{q.non_positive} non-positive prices")
    if q.extreme_moves:
        bits.append(f"{q.extreme_moves} extreme moves")
    return "; ".join(bits) if bits else "clean (full coverage, no anomalies)"


def _render_header(result: BacktestResult) -> str:
    cfg = result.config
    q = result.quality
    start = q.start.date() if (q is not None and q.start is not None) else cfg.data.start
    end = q.end.date() if (q is not None and q.end is not None) else cfg.data.end
    costs = f"{cfg.costs.commission_bps:g}+{cfg.costs.slippage_bps:g} bps"

    lines = [f" Run: {cfg.name} ".center(_WIDTH, "=")]
    lines.append(_universe_line(result))
    lines.extend(_factor_lines(result))
    lines.append(f"Period:     {start} -> {end}")
    lines.append(f"Rebalance:  {cfg.rebalance.value}   Top-N: {cfg.top_n}   Costs: {costs}")
    return "\n".join(lines)


def _render_metrics(returns, title: str) -> str:
    stats = compute_metrics(returns).as_dict()
    lines = [f" {title} ".center(_WIDTH, "=")]
    for key, label in _LABELS.items():
        val = stats[key]
        shown = f"{val:>8.2%}" if key in _AS_PCT else f"{val:>8.2f}"
        lines.append(f"  {label:<18}{shown}")
    lines.append("=" * _WIDTH)
    return "\n".join(lines)


def _render_performance(result: BacktestResult) -> str:
    return _render_metrics(result.returns, "Performance")


def print_summary(result: BacktestResult) -> None:
    """Print the full text report: config header, data quality, performance."""
    print(_render_header(result))
    if result.quality is not None:
        print(result.quality.render())
    print(_render_performance(result))


def _fmt_window_params(params: dict) -> str:
    if not params:
        return "base"
    return ", ".join(f"{k}={v}" for k, v in params.items())


def print_walk_forward(wf) -> None:
    """Print a walk-forward study: setup, per-window OOS table, stitched OOS
    metrics, and the in-sample vs out-of-sample Sharpe gap."""
    cfg = wf.config
    n = len(wf.windows)
    grid_combos = len({tuple(sorted(w.params.items())) for w in wf.windows}) if n else 0
    oos = wf.oos_returns

    print(f" Walk-Forward: {cfg.name} ".center(_WIDTH, "="))
    if n:
        w0 = wf.windows[0].window
        train_mo = _months_between(w0.train_start, w0.train_end)
        test_mo = _months_between(w0.test_start, w0.test_end)
        print(f" Train/Test ~ {train_mo}/{test_mo} mo   Windows: {n}   Params seen: {grid_combos}")
        print(f" OOS span:   {oos.index.min().date()} -> {oos.index.max().date()}")
    print("-" * _WIDTH)
    print(f" {'Test period':<19}{'Params':<24}{'tr.SR':>6}{'oos.SR':>7}{'oos.ret':>9}")
    for wr in wf.windows:
        period = f"{wr.window.test_start:%Y-%m}..{wr.window.test_end:%Y-%m}"
        params = _fmt_window_params(wr.params)
        if len(params) > 23:
            params = params[:22] + "."
        print(
            f" {period:<19}{params:<24}{wr.train_sharpe:>6.2f}"
            f"{wr.test_sharpe:>7.2f}{wr.test_return:>9.1%}"
        )

    print(_render_metrics(oos, "OOS (stitched, out-of-sample)"))
    print(f" In-sample (fixed params) Sharpe over OOS span: {wf.benchmark_sharpe:>6.2f}")
    print(f" Walk-forward OOS Sharpe:                       {compute_metrics(oos).sharpe:>6.2f}")
    print("=" * _WIDTH)


def _months_between(a, b) -> int:
    return round((b - a).days / 30.44)


def _html_provenance(result: BacktestResult) -> str:
    """An HTML 'run configuration' block injected into the quantstats tearsheet,
    so the HTML report shows the same universe/factor/quality provenance as the
    text report (quantstats itself only knows the returns series)."""
    import html as _html

    cfg = result.config
    q = result.quality
    start = q.start.date() if (q is not None and q.start is not None) else cfg.data.start
    end = q.end.date() if (q is not None and q.end is not None) else cfg.data.end

    rows = [
        ("Universe", _universe_desc(result)),
        ("Factor", _factor_desc(result)),
        ("Period", f"{start} to {end}"),
        ("Settings", _settings_desc(result)),
        ("Data quality", _quality_desc(result)),
    ]
    trs = "".join(
        f'<tr><td style="padding:3px 16px 3px 0;color:#888;white-space:nowrap;'
        f'vertical-align:top;">{_html.escape(k)}</td>'
        f'<td style="padding:3px 0;">{_html.escape(v)}</td></tr>'
        for k, v in rows
    )
    return (
        '<div style="margin:18px 0;padding:14px 18px;border:1px solid #e3e3e3;'
        "border-radius:8px;background:#fafafa;font-family:Arial,Helvetica,sans-serif;"
        'font-size:13px;color:#333;">'
        '<div style="font-weight:600;margin-bottom:8px;font-size:14px;">'
        "AlphaForge run configuration</div>"
        f'<table style="border-collapse:collapse;">{trs}</table></div>'
    )


def save_html_report(result: BacktestResult, path: str | Path) -> Path:
    """Full quantstats tearsheet, with an AlphaForge run-configuration block
    injected near the top. Requires the 'engine' extra (quantstats)."""
    import quantstats as qs  # lazy heavy import

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    qs.reports.html(
        result.returns,
        title=f"AlphaForge {result.config.name}",
        output=str(path),
    )

    # Inject the provenance block right after the title rule in the tearsheet.
    raw = path.read_text(encoding="utf-8")
    marker = "<hr>"
    idx = raw.find(marker)
    if idx != -1:
        at = idx + len(marker)
        raw = raw[:at] + "\n" + _html_provenance(result) + "\n" + raw[at:]
        path.write_text(raw, encoding="utf-8")
    return path
