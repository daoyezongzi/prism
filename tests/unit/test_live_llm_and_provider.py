"""Unit tests for Live Market/Wencai providers and Copilot LLM Agent ReAct streaming."""

from __future__ import annotations

import asyncio
from fastapi.testclient import TestClient

from app.api.main import app
from app.llm.agent import CopilotAgent, CopilotMessage
from app.providers.contracts import FrozenDict, ProviderOperation, ProviderRequest
from app.providers.live_market import LiveMarketProvider
from app.providers.live_wencai import LiveWencaiProvider


def test_live_market_provider_stock_quote() -> None:
    async def _run():
        provider = LiveMarketProvider()
        req = ProviderRequest(
            request_id="req-live-stock-001",
            subject="300750",
            operation=ProviderOperation.MARKET_DATA,
            parameters=FrozenDict({"symbol": "300750"}),
            timeout_ms=5000,
        )
        result = await provider.execute(req)
        assert result.status.value == "SUCCESS"
        assert len(result.records) == 1
        rec = result.records[0].fields
        assert rec["symbol"] == "300750.SZ"
        assert rec["name"] == "宁德时代"
        assert rec["price_cny"] > 0
        assert rec["pe_ttm"] > 0

    asyncio.run(_run())


def test_live_market_provider_fund_lookthrough() -> None:
    async def _run():
        provider = LiveMarketProvider()
        req = ProviderRequest(
            request_id="req-live-fund-001",
            subject="588000",
            operation=ProviderOperation.FUND_DATA,
            parameters=FrozenDict({"fund_code": "588000"}),
            timeout_ms=5000,
        )
        result = await provider.execute(req)
        assert result.status.value == "SUCCESS"
        assert len(result.records) == 1
        fund_rec = result.records[0].fields
        assert fund_rec["fund_code"] == "588000.SH"
        assert len(fund_rec["top_holdings"]) >= 3
        assert "中芯国际" in [h["name"] for h in fund_rec["top_holdings"]]

    asyncio.run(_run())


def test_live_wencai_provider() -> None:
    async def _run():
        provider = LiveWencaiProvider()
        req = ProviderRequest(
            request_id="req-live-wc-001",
            subject="半导体龙头股",
            operation=ProviderOperation.MARKET_DATA,
            parameters=FrozenDict({"query": "半导体龙头股"}),
            timeout_ms=5000,
        )
        result = await provider.execute(req)
        assert result.status.value == "SUCCESS"
        assert len(result.records) == 1
        assert "问财" in result.records[0].fields["results_summary"]

    asyncio.run(_run())


def test_copilot_agent_streaming_and_tool_execution() -> None:
    async def _run():
        agent = CopilotAgent()
        events: list[dict] = []
        async for event in agent.stream_chat(
            user_message="请帮我研判一下 300750 宁德时代目前的估值和财务质地",
            persona_info={"name": "张先生", "tag": "R3 平衡型", "max_drawdown": 15, "budget_cap": "30.0%"},
        ):
            events.append(event)

        event_types = [e["type"] for e in events]
        assert "start" in event_types
        assert "tool_start" in event_types or "token" in event_types
        assert "done" in event_types

    asyncio.run(_run())


def test_copilot_portfolio_parser() -> None:
    async def _run():
        agent = CopilotAgent()
        parsed = await agent.parse_portfolio_from_text(
            "我持有1000股宁德时代，买入价格220元；还有20000份科创50ETF，以及5万元现金"
        )
        assert parsed["cash_cny"] == 50000.0
        assert parsed["parsed_count"] >= 1
        names = [p["name"] for p in parsed["positions"]]
        assert any("宁德时代" in n for n in names)

    asyncio.run(_run())


def test_copilot_http_endpoints() -> None:
    client = TestClient(app)

    # Test Live Quote Endpoint
    quote_resp = client.get("/api/v1/copilot/live-quote?symbol=688256")
    assert quote_resp.status_code == 200
    quote_data = quote_resp.json()
    assert quote_data["status"] == "SUCCESS"
    assert quote_data["data"]["name"] == "寒武纪"

    # Test Live Fund Endpoint
    fund_resp = client.get("/api/v1/copilot/live-fund?fund_code=512480")
    assert fund_resp.status_code == 200
    fund_data = fund_resp.json()
    assert fund_data["status"] == "SUCCESS"
    assert "半导体" in fund_data["data"]["fund_name"]

    # Test Parse Portfolio Endpoint
    parse_resp = client.post(
        "/api/v1/copilot/parse-portfolio",
        json={"text": "持有500股贵州茅台和10000份沪深300ETF，现金2万元"},
    )
    assert parse_resp.status_code == 200
    parse_data = parse_resp.json()
    assert parse_data["cash_cny"] == 20000.0
    assert len(parse_data["positions"]) >= 1

    # Test Streaming Chat Endpoint
    chat_resp = client.post(
        "/api/v1/copilot/chat",
        json={
            "message": "我的持仓科技股太多了，请帮我做一下健康体检",
            "persona_id": "persona-zhang-r3",
            "persona_info": {"name": "张先生", "tag": "R3 平衡型", "max_drawdown": 15, "budget_cap": "30.0%"},
        },
    )
    assert chat_resp.status_code == 200
    assert "text/event-stream" in chat_resp.headers["content-type"]
    assert "data:" in chat_resp.text
