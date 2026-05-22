import os
import json
from time import sleep
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich import box
from rich.align import Align
from rich.text import Text

# Paths
DB_PATH = "data/celestium.db"
STATE_PATH = "data/account_state.json"
REPORT_PATH = "data/backtest_report.json"

def get_db_size():
    if os.path.exists(DB_PATH):
        size_kb = os.path.getsize(DB_PATH) / 1024
        return f"{size_kb:.0f} KB"
    return "Not Found"

def get_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"balance": 0.0, "status": "UNKNOWN"}

def get_report():
    if os.path.exists(REPORT_PATH):
        try:
            with open(REPORT_PATH, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def generate_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="flow", size=15)
    )
    
    layout["main"].split_row(
        Layout(name="left"),
        Layout(name="right")
    )
    
    layout["left"].split_column(
        Layout(name="status", size=6),
        Layout(name="tickers", size=6)
    )
    
    layout["right"].split_column(
        Layout(name="risk", size=7),
        Layout(name="model")
    )
    return layout

def make_header() -> Panel:
    return Panel(Align.center(Text("CELESTIUM QT TUI", style="bold cyan")), box=box.ROUNDED)

def make_status_panel() -> Panel:
    state = get_state()
    t = Table.grid(padding=(0, 1))
    t.add_column(style="bold", justify="right")
    t.add_column()
    t.add_row("State:", f"[green]{state.get('status', 'UNKNOWN')}[/green]")
    t.add_row("Shadow Mode:", "[yellow]TRUE[/yellow]")
    t.add_row("Broker:", "Alpaca (Cash)")
    return Panel(t, title="[bold]SYSTEM STATUS[/bold]", border_style="cyan")

def make_tickers_panel() -> Panel:
    t = Table.grid(padding=(0, 1))
    t.add_column(style="bold", justify="right")
    t.add_column()
    t.add_row("Target:", "SPLG (Fractional)")
    t.add_row("Trend:", "[green][ ▄▅▇██▇▅▃  ][/green] (BULLISH)")
    t.add_row("Chart:", "[green][+][/green] +1.2% (Daily)")
    t.add_row("DB Size:", f"{get_db_size()} (data/celestium.db)")
    t.add_row("DuckDB:", "[blue]Online[/blue] (Polars Native)")
    return Panel(t, title="[bold]TICKERS & DATA[/bold]", border_style="cyan")

def make_risk_panel() -> Panel:
    state = get_state()
    bal = state.get("balance", 0.0)
    t = Table.grid(padding=(0, 1))
    t.add_column(style="bold", justify="right")
    t.add_column()
    t.add_row("Balance:", f"[green]${bal:.2f}[/green] (Settled)")
    t.add_row("DLL:", "[red]-$20.00[/red]")
    t.add_row("Max Trades:", "50")
    t.add_row("Hurst Min:", "0.42")
    return Panel(t, title="[bold]RISK FIREWALL[/bold]", border_style="cyan")

def make_model_panel() -> Panel:
    report = get_report()
    wr = report.get("Win Rate", 0) * 100
    profit = report.get("Total Net Profit", 0)
    dd = report.get("Max Drawdown", 0)
    trades = report.get("Total Trades", 0)
    
    t = Table.grid(padding=(0, 1))
    t.add_column(style="bold", justify="right")
    t.add_column()
    t.add_row("Engine:", "XGBoost Classifier")
    t.add_row("File:", "alpha_v1.ubj")
    if trades > 0:
        t.add_row("Accuracy:", f"[green]{wr:.2f}% Win Rate[/green]")
        t.add_row("Profit:", f"[green]${profit:.2f}[/green]")
        t.add_row("Drawdown:", f"[red]-${dd:.2f}[/red]")
        t.add_row("Trades:", str(trades))
    else:
        t.add_row("Accuracy:", "[yellow]Awaiting Backtest Run[/yellow]")
        
    return Panel(t, title="[bold]LAYER 2 MODEL[/bold]", border_style="cyan")

def make_flow_panel() -> Panel:
    flow_text = """
       [ MARKET DATA ] 
      (Ingestion/Alpaca)
              |
              v
     [ LAYER 1: REGIME ]
   (Hurst, ADX, ATR, DuckDB)
              |
              v
     [ LAYER 2: SIGNAL ]
    (XGBoost Classifier)
              |
              v
     [ LAYER 3: ORACLE ]
 ----------------------------------
 | - Checks DLL / Profit Ceiling  |
 | - Checks GFV (T+1 Settlement)  |
 | - Checks Hurst Threshold       |
 ----------------------------------
              |
         (Veto? -> Halt)
              |
         (Pass? -> Go)
              v
    [ LAYER 4: EXECUTION ]
     (Alpaca API -> BUY)
              |
              v
    [ LAYER 4: ADVISOR ]
    (LLM Session Summary)
"""
    return Panel(Align.center(Text(flow_text, style="white")), title="[bold]SYSTEM FLOW[/bold]", border_style="blue")

def main():
    layout = generate_layout()
    
    with Live(layout, refresh_per_second=1, screen=True):
        while True:
            layout["header"].update(make_header())
            layout["status"].update(make_status_panel())
            layout["tickers"].update(make_tickers_panel())
            layout["risk"].update(make_risk_panel())
            layout["model"].update(make_model_panel())
            layout["flow"].update(make_flow_panel())
            sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
