# -*- coding: utf-8 -*-
"""
Testes unitários para o motor de agendamento em background (Scheduler).
"""
from datetime import datetime
from src.scheduler.engine import calculate_next_run, DAY_MAP, DAY_LABELS

class TestSchedulerCalculations:
    """Valida o cálculo determinístico da próxima execução agendada."""

    def test_calculate_next_run_today_later(self):
        # Quinta-feira (thu) às 10:00, com agendamento para 14:00
        mock_now = datetime(2026, 9, 24, 10, 0, 0)
        assert DAY_MAP[mock_now.weekday()] == "thu"

        next_run = calculate_next_run(
            days_of_week=["thu", "fri"],
            times=["14:00"],
            from_dt=mock_now
        )
        assert next_run is not None
        assert next_run.year == 2026
        assert next_run.month == 9
        assert next_run.day == 24
        assert next_run.hour == 14
        assert next_run.minute == 0

    def test_calculate_next_run_tomorrow(self):
        # Quinta-feira (thu) às 18:00, com agendamento para 08:00
        mock_now = datetime(2026, 9, 24, 18, 0, 0)

        next_run = calculate_next_run(
            days_of_week=["thu", "fri"],
            times=["08:00"],
            from_dt=mock_now
        )
        assert next_run is not None
        # Deve agendar para sexta (25) às 08:00
        assert next_run.day == 25
        assert next_run.hour == 8

    def test_calculate_next_run_next_week(self):
        # Sexta-feira (25) às 20:00 com dias apenas [mon]
        mock_now = datetime(2026, 9, 25, 20, 0, 0)
        next_run = calculate_next_run(
            days_of_week=["mon"],
            times=["09:00"],
            from_dt=mock_now
        )
        assert next_run is not None
        # Próxima segunda é 28/09
        assert next_run.day == 28
        assert next_run.hour == 9

    def test_calculate_empty_inputs_returns_none(self):
        assert calculate_next_run([], ["08:00"]) is None
        assert calculate_next_run(["mon"], []) is None
        assert calculate_next_run(None, None) is None
