# -*- coding: utf-8 -*-
"""
Testes unitários para o motor de agendamento em background (Scheduler).
Compatível tanto com pytest quanto com unittest runner.
"""
import unittest
from datetime import datetime

import tests.test_helpers
from src.scheduler.engine import calculate_next_run, DAY_MAP, DAY_LABELS

class TestSchedulerCalculations(unittest.TestCase):
    """Valida o cálculo determinístico da próxima execução agendada."""

    def test_calculate_next_run_today_later(self):
        # Quinta-feira (thu) às 10:00, com agendamento para 14:00
        mock_now = datetime(2026, 9, 24, 10, 0, 0)
        self.assertEqual(DAY_MAP[mock_now.weekday()], "thu")

        next_run = calculate_next_run(
            days_of_week=["thu", "fri"],
            times=["14:00"],
            from_dt=mock_now
        )
        self.assertIsNotNone(next_run)
        self.assertEqual(next_run.year, 2026)
        self.assertEqual(next_run.month, 9)
        self.assertEqual(next_run.day, 24)
        self.assertEqual(next_run.hour, 14)
        self.assertEqual(next_run.minute, 0)

    def test_calculate_next_run_tomorrow(self):
        # Quinta-feira (thu) às 18:00, com agendamento para 08:00
        mock_now = datetime(2026, 9, 24, 18, 0, 0)

        next_run = calculate_next_run(
            days_of_week=["thu", "fri"],
            times=["08:00"],
            from_dt=mock_now
        )
        self.assertIsNotNone(next_run)
        self.assertEqual(next_run.day, 25)
        self.assertEqual(next_run.hour, 8)

    def test_calculate_next_run_next_week(self):
        # Sexta-feira (25) às 20:00 com dias apenas [mon]
        mock_now = datetime(2026, 9, 25, 20, 0, 0)
        next_run = calculate_next_run(
            days_of_week=["mon"],
            times=["09:00"],
            from_dt=mock_now
        )
        self.assertIsNotNone(next_run)
        self.assertEqual(next_run.day, 28)
        self.assertEqual(next_run.hour, 9)

    def test_calculate_empty_inputs_returns_none(self):
        self.assertIsNone(calculate_next_run([], ["08:00"]))
        self.assertIsNone(calculate_next_run(["mon"], []))
        self.assertIsNone(calculate_next_run(None, None))


class TestTimezoneFormatting(unittest.TestCase):
    """Valida a conversão de timestamps UTC para o fuso local (America/Campo_Grande)."""

    def test_format_br_datetime_utc_to_local(self):
        import os
        from src.config import format_br_datetime
        # Garante fuso do MS (UTC-4)
        os.environ["TZ"] = "America/Campo_Grande"
        
        # 22:01:32 UTC corresponde a 18:01:32 local (UTC-4)
        utc_ts = "2026-10-01 22:01:32"
        formatted = format_br_datetime(utc_ts, is_utc=True)
        self.assertEqual(formatted, "01/10/2026 18:01:32")

    def test_format_br_datetime_direct_local(self):
        from src.config import format_br_datetime
        # Quando is_utc=False, mantém a data/hora local informada
        local_ts = "2026-10-01 18:01:32"
        formatted = format_br_datetime(local_ts, is_utc=False)
        self.assertEqual(formatted, "01/10/2026 18:01:32")

    def test_format_br_datetime_invalid_or_empty(self):
        from src.config import format_br_datetime
        self.assertEqual(format_br_datetime(""), "-")
        self.assertEqual(format_br_datetime(None), "-")
        self.assertEqual(format_br_datetime("nan"), "-")


if __name__ == '__main__':
    unittest.main()
