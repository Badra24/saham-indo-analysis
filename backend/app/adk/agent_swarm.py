import logging
import json
from typing import Dict, Any, List

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADK_Swarm")

class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Base process method to be overridden by agents."""
        return {"agent": self.name, "status": "idle"}

class QuantWorker(BaseAgent):
    """Analyzes Valuation, Financials, and Scoring."""
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        alpha_v = context.get("alpha_v", {})
        score = alpha_v.get("score", 0)
        grade = alpha_v.get("grade", "E")
        
        analysis = f"Valuation is {grade} (Score: {score}). "
        if score > 70:
            analysis += "Undervalued with high potential. "
        elif score < 40:
            analysis += "Overvalued or poor fundamentals. "
            
        return {
            "agent": self.name,
            "sentiment": "bullish" if score > 60 else "bearish",
            "analysis": analysis
        }

class RiskWorker(BaseAgent):
    """Risk Management - Has VETO POWER."""
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        risk_data = context.get("risk_profile", {})
        volatility = risk_data.get("atr_percentage", 0)
        
        # VETO RULE: If daily volatility > 8%, it's too risky for standard entry
        veto = False
        warning = ""
        
        if volatility > 0.08:
            veto = True
            warning = "VETO: Asset too volatile (ATR > 8%). reduced size recommended. "
        
        return {
            "agent": self.name,
            "veto": veto,
            "warning": warning,
            "max_allocation": "5%" if not veto else "0%"
        }

class BandarWorker(BaseAgent):
    """Analyzes Smart Money Flow."""
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        bandar_data = context.get("bandarmology", {})
        bcr = bandar_data.get("bcr", 0.0)
        action = bandar_data.get("action", "Neutral")
        
        analysis = f"Bandar Action: {action} (BCR: {bcr}). "
        if bcr > 1.2:
            analysis += "Strong Accumulation detected. "
        elif bcr < 0.8:
            analysis += "Distribution detected. "
            
        return {
            "agent": self.name,
            "flow_status": action,
            "analysis": analysis
        }

class SupervisorAgent(BaseAgent):
    """Orchestrates the workers and synthesizes the final decision."""
    def __init__(self):
        super().__init__("Supervisor", "Orchestrator")
        self.quant = QuantWorker("Quant_Analyst", "Valuation")
        self.risk = RiskWorker("Risk_Officer", "Risk")
        self.bandar = BandarWorker("Bandar_Detective", "Flow")

    async def run_mission(self, ticker: str, full_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Supervisor starting mission for {ticker}")
        
        # 1. Parallel Execution (Simulated here with await sequence, can be gathered)
        quant_res = await self.quant.process(full_context)
        bandar_res = await self.bandar.process(full_context)
        risk_res = await self.risk.process(full_context)
        
        # 2. Synthesis Logic
        decision = "HOLD"
        confidence = "Low"
        summary = ""
        
        # Check Risk Veto
        if risk_res.get("veto"):
            decision = "NO TRADE"
            summary += f"⚠️ RISK VETO: {risk_res['warning']} "
        else:
            # Combine Quant + Bandar
            q_bullish = quant_res["sentiment"] == "bullish"
            b_bullish = bandar_res.get("flow_status") in ["Accumulation", "Mark-Up"]
            
            if q_bullish and b_bullish:
                decision = "STRONG BUY"
                confidence = "High"
            elif q_bullish or b_bullish:
                decision = "SPECULATIVE BUY"
                confidence = "Medium"
            else:
                decision = "AVOID"
        
        # 3. Final Narrative Construction
        final_report = (
            f"### Mission Report: {ticker}\n"
            f"**Decision**: {decision} (Conf: {confidence})\n\n"
            f"**💰 Quant Analysis**: {quant_res['analysis']}\n"
            f"**🕵️ Bandar Flow**: {bandar_res['analysis']}\n"
            f"**🛡️ Risk Check**: {risk_res['warning']}Max Alloc: {risk_res['max_allocation']}"
        )
        
        return {
            "ticker": ticker,
            "decision": decision,
            "report": final_report,
            "details": {
                "quant": quant_res,
                "bandar": bandar_res,
                "risk": risk_res
            }
        }

# Singleton instance
agent_swarm = SupervisorAgent()
