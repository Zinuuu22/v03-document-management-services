import os
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
import pytz
import structlog

# Constants and Configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from core.v03.effective_update import update_effective_status_daily, update_article_effective_status_daily
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

def main():
    """Set up and start the scheduler for daily status updates."""
    # APScheduler requires pytz timezones
    scheduler = BlockingScheduler(timezone=pytz.timezone("Asia/Ho_Chi_Minh"))


    # Job 1: Update document effective status daily at 00:30
    scheduler.add_job(update_effective_status_daily, 'cron', hour=0, minute=30)
    logger.info(action="main", event="scheduler_job_added")
    
    # Job 2: Update article effective status daily at 00:45
    scheduler.add_job(update_article_effective_status_daily, 'cron', hour=0, minute=45)
    logger.info(action="main", event="scheduler_job_added")
    logger.info(action="main", event="scheduler_started")

    
    # # TEST MODE: Job 1 - Update document effective status every 1 minute
    # scheduler.add_job(update_effective_status_daily, 'interval', minutes=1)
    # logger.info("Scheduler added: Document effective status update (TEST MODE - every 1 minute)")

    # # TEST MODE: Job 2 - Update article effective status every 2 minutes
    # scheduler.add_job(update_article_effective_status_daily, 'interval', minutes=2)
    # logger.info("Scheduler added: Article effective status update (TEST MODE - every 2 minutes)")
    # logger.info("Scheduler started in TEST MODE - jobs will run every 1/2 minutes")

    # Start the scheduler
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info(action="main", event="scheduler_stopped")


if __name__ == '__main__':
    main()