"""Cached chat service must not share generation allowances across turns."""
import asyncio
from dataclasses import replace
import pytest
from src.b1_answering.core.policy import Limits, PolicyError
from src.retrieval_orchestration.live_research import LiveResearchService


class ReservingRouter:
    def __init__(self): self.budgets = []
    async def answer(self, question, context, *, provider, limits, budget):
        self.budgets.append(budget)
        budget.reserve(1)
        await asyncio.sleep(0)
        assert budget.snapshot()['calls_used'] == 1
        with pytest.raises(PolicyError, match='CALL_LIMIT_EXCEEDED'):
            budget.reserve(1)
        return dict(status='EVIDENCE_READY', answering=dict(budget=budget.snapshot()))


@pytest.mark.parametrize('concurrent', [False, True])
def test_over_twenty_turns_do_not_exhaust_other_requests(concurrent):
    router = ReservingRouter()
    service = LiveResearchService(object(), hybrid_router=router,
        limits=replace(Limits(), max_generation_calls=1))
    async def run():
        if concurrent:
            return await asyncio.gather(*(service.answer('Ai là Chủ tịch VCB?', f'session-{i}') for i in range(25)))
        return [await service.answer('Ai là Chủ tịch VCB?', 'same-session') for _ in range(25)]
    results = asyncio.run(run())
    assert len({id(budget) for budget in router.budgets}) == 25
    assert all(r['answering']['budget']['calls_used'] == 1 for r in results)
    assert all(r['answering']['budget_scope'] == 'REQUEST' for r in results)
    assert service.budget.snapshot()['calls_used'] == 0
