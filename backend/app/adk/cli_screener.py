
import asyncio
import sys
import os
from typing import List, Dict
from rich.console import Console
from rich.table import Table
from rich import box

# Ensure backend path is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.services.screener_service import screener_service
from dotenv import load_dotenv

# Load Env
load_dotenv("backend/.env")

console = Console()

async def run_screener():
    console.print("[bold green]Starting Massive AI Market Screener...[/bold green]")
    console.print("Phase 1: Scanning 800+ Universe (Technicals)...")
    
    # 1. Run Screening
    results = await screener_service.screen_stocks(limit=20, min_rvol=1.5)
    
    console.print(f"[bold cyan]Phase 2: Enriched {len(results)} Top Candidates with Bandarmology[/bold cyan]")
    
    # 2. Display Table
    table = Table(title="AI Screener Results (Real-Time)", box=box.ROUNDED)
    
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Price", style="white", justify="right")
    table.add_column("Chg%", style="bold", justify="right")
    table.add_column("RVOL", style="magenta", justify="right")
    table.add_column("Value (B)", style="green", justify="right")
    table.add_column("Bandar Status", style="bold yellow")
    table.add_column("Top Buyer", style="blue")
    
    for r in results:
        # Colorize Change
        chg = r['change_pct']
        chg_str = f"[green]+{chg}%[/green]" if chg > 0 else f"[red]{chg}%[/red]"
        
        # Value in Billions
        val_b = r['value_idr'] / 1_000_000_000
        
        # Bandar Status Color
        b_status = r['bandar_status']
        b_style = "white"
        if "Big Acc" in b_status: b_style = "bold green"
        elif "Normal Acc" in b_status: b_style = "green"
        elif "Dist" in b_status: b_style = "red"
        
        top_buyer = r.get('top_buyers', [{}])[0].get('code', '-') if r.get('top_buyers') else '-'
        
        table.add_row(
            r['ticker'],
            f"{r['price']:,.0f}",
            chg_str,
            str(r['rvol']),
            f"{val_b:.1f} B",
            f"[{b_style}]{b_status}[/{b_style}]",
            top_buyer
        )
        
    console.print(table)

if __name__ == "__main__":
    try:
        asyncio.run(run_screener())
    except KeyboardInterrupt:
        print("Stopped.")
