# -*- coding: utf-8 -*-
"""
Motor de Agendamento Automático (Background Scheduler Daemon).
Executa em background dentro do container da aplicação como thread única (singleton),
verificando as preferências salvas no SQLite para disparar as varreduras diárias.
"""
import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime, timedelta
from src.logger import logger
from src.database.db import get_schedule_config, update_schedule_execution_times
from src.config import check_scan_running

DAY_MAP = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun"
}

DAY_LABELS = {
    "mon": "Segunda-feira",
    "tue": "Terça-feira",
    "wed": "Quarta-feira",
    "thu": "Quinta-feira",
    "fri": "Sexta-feira",
    "sat": "Sábado",
    "sun": "Domingo"
}

_SCHEDULER_LOCK = threading.Lock()
_SCHEDULER_STARTED = False

def calculate_next_run(days_of_week: list, times: list, from_dt: datetime = None) -> datetime:
    """Calcula a data e hora exata do próximo disparo baseado nos dias e horários configurados."""
    if not days_of_week or not times:
        return None
    
    if from_dt is None:
        from_dt = datetime.now()

    # Organiza os horários em ordem crescente
    sorted_times = sorted([t.strip() for t in times if t.strip()])
    if not sorted_times:
        return None

    # Procura nos próximos 14 dias
    for day_offset in range(14):
        target_date = from_dt.date() + timedelta(days=day_offset)
        target_weekday_str = DAY_MAP[target_date.weekday()]
        
        if target_weekday_str in days_of_week:
            for t_str in sorted_times:
                try:
                    hour, minute = map(int, t_str.split(":"))
                    candidate_dt = datetime.combine(target_date, datetime.min.time()).replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    if candidate_dt > from_dt:
                        return candidate_dt
                except Exception:
                    continue
    return None

class BackgroundScanScheduler(threading.Thread):
    def __init__(self):
        super().__init__(name="BackgroundScanSchedulerThread", daemon=True)
        self._running = True
        self._last_triggered_minute = ""

    def run(self):
        logger.info("⏰ [Scheduler] Motor de agendamento automático iniciado em background.")
        
        while self._running:
            try:
                self._check_and_run_schedule()
            except Exception as e:
                logger.error(f"⏰ [Scheduler] Erro no loop de agendamento: {e}")
            
            # Verifica a cada 20 segundos
            time.sleep(20)

    def _check_and_run_schedule(self):
        config = get_schedule_config()
        if not config.get("enabled", False):
            return

        now = datetime.now()
        current_minute_key = now.strftime("%Y-%m-%d %H:%M")
        
        # Evita disparos duplicados no mesmo minuto
        if current_minute_key == self._last_triggered_minute:
            return

        current_weekday = DAY_MAP[now.weekday()]
        current_time_str = now.strftime("%H:%M")
        
        days_of_week = config.get("days_of_week", [])
        times = config.get("times", [])

        # Calcula o próximo disparo e mantém o banco atualizado
        next_dt = calculate_next_run(days_of_week, times, now)
        if next_dt:
            next_run_str = next_dt.strftime("%Y-%m-%d %H:%M:%S")
            update_schedule_execution_times(next_run=next_run_str)

        # Se o dia da semana atual estiver habilitado e o horário bater com um dos configurados
        if current_weekday in days_of_week and current_time_str in times:
            self._last_triggered_minute = current_minute_key
            self._trigger_scan(now, next_dt)

    def _trigger_scan(self, triggered_at: datetime, next_dt: datetime):
        if check_scan_running():
            logger.warning("⏰ [Scheduler] Horário de agendamento atingido, mas uma varredura já está em execução. Pulando disparo.")
            return

        logger.info(f"⏰ [Scheduler] DISPARANDO VARREDURA AUTOMÁTICA PROGRAMADA às {triggered_at.strftime('%H:%M:%S')}!")
        
        # Atualiza a data da última execução
        last_run_str = triggered_at.strftime("%Y-%m-%d %H:%M:%S")
        next_run_str = next_dt.strftime("%Y-%m-%d %H:%M:%S") if next_dt else None
        update_schedule_execution_times(last_run=last_run_str, next_run=next_run_str)

        # Dispara o subprocesso run_scan.py de forma totalmente assíncrona
        try:
            subprocess.Popen([sys.executable, "src/run_scan.py", "null", "null"])
            logger.success("⏰ [Scheduler] Subprocesso de varredura disparado com sucesso.")
        except Exception as e:
            logger.error(f"⏰ [Scheduler] Falha ao disparar subprocesso: {e}")

def trigger_manual_test_scan() -> bool:
    """Dispara uma varredura de teste imediata e registra no log/banco."""
    if check_scan_running():
        return False
    
    now = datetime.now()
    last_run_str = now.strftime("%Y-%m-%d %H:%M:%S")
    update_schedule_execution_times(last_run=last_run_str)
    
    try:
        subprocess.Popen([sys.executable, "src/run_scan.py", "null", "null"])
        logger.info("⏰ [Scheduler] Disparo de teste manual do agendador realizado com sucesso.")
        return True
    except Exception as e:
        logger.error(f"⏰ [Scheduler] Falha no teste manual do agendador: {e}")
        return False

def start_scheduler_if_not_running():
    """Inicia a thread do agendador garantindo singleton por processo."""
    global _SCHEDULER_STARTED
    with _SCHEDULER_LOCK:
        if not _SCHEDULER_STARTED:
            scheduler_thread = BackgroundScanScheduler()
            scheduler_thread.start()
            _SCHEDULER_STARTED = True
            logger.info("⏰ [Scheduler] Thread singleton do agendador iniciada.")
