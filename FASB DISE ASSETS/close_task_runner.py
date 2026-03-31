#!/usr/bin/env python3
"""
GL Intelligence Platform — Close Task Status Runner
Runs nightly via Cloud Run Job triggered by Cloud Scheduler.
Executes each task's status_query against BigQuery,
updates close_tasks, and writes to close_task_history.

Deploy: Cloud Run Job (not Service — this is a one-shot job)
Schedule: 0 2 * * * (2am daily, after CDC pipeline completes)

Environment variables:
  GOOGLE_CLOUD_PROJECT — GCP project ID (default: diplomatic75)
  BQ_DATASET           — BigQuery dataset (default: dise_reporting)
  QUERY_TIMEOUT_SEC    — max seconds per status query (default: 120)
"""

from __future__ import annotations

import os
import sys
import logging
from datetime import datetime, timezone

from google.cloud import bigquery

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
)
log = logging.getLogger('close-task-runner')

PROJECT       = os.environ.get('GCP_PROJECT', os.environ.get('GOOGLE_CLOUD_PROJECT', 'diplomatic75'))
DATASET       = os.environ.get('BQ_DATASET', 'dise_reporting')
QUERY_TIMEOUT = int(os.environ.get('QUERY_TIMEOUT_SEC', '120'))

try:
    BQ_CLIENT = bigquery.Client(project=PROJECT)
except Exception as e:
    log.error(f"Failed to initialize BigQuery client: {e}")
    sys.exit(1)


def run_status_query(task_id: str, status_query: str) -> dict:
    """
    Execute a task's status_query and return the result row.
    Validates the query returns expected columns before executing.
    """
    if not status_query or not status_query.strip():
        return {
            'is_complete': False,
            'metric_value': 'Empty query',
            'detail': f'Task {task_id} has an empty status_query',
        }

    # Basic safety check — status queries should be SELECT only
    normalized = status_query.strip().upper()
    if any(kw in normalized for kw in ['INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'CREATE ', 'ALTER ', 'TRUNCATE ']):
        log.error(f"Task {task_id}: status_query contains forbidden DDL/DML keywords")
        return {
            'is_complete': False,
            'metric_value': 'Query rejected',
            'detail': f'Task {task_id} status_query contains forbidden DDL/DML keywords',
        }

    try:
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=10 * 1024 * 1024 * 1024,  # 10 GB safety limit
        )
        query_job = BQ_CLIENT.query(status_query, job_config=job_config)
        result = query_job.result(timeout=QUERY_TIMEOUT)
        rows = list(result)

        if not rows:
            return {
                'is_complete': False,
                'metric_value': 'Query returned no rows',
                'detail': f'Task {task_id}: status query produced no results — check query logic',
            }

        row = dict(rows[0])

        # Validate expected columns exist
        if 'is_complete' not in row:
            return {
                'is_complete': False,
                'metric_value': 'Missing is_complete column',
                'detail': f'Task {task_id}: status_query must return is_complete column',
            }

        return {
            'is_complete':  bool(row.get('is_complete', False)),
            'metric_value': str(row.get('metric_value', ''))[:500],
            'detail':       str(row.get('detail', ''))[:2000],
        }

    except Exception as e:
        log.error(f"Task {task_id}: status query failed: {e}")
        return {
            'is_complete': False,
            'metric_value': 'Query error',
            'detail': f'Task {task_id}: {str(e)[:500]}',
        }


def get_open_tasks() -> list[dict]:
    """Fetch all close tasks that need status evaluation."""
    query = f"""
    SELECT task_id, task_name, fiscal_year, fiscal_period,
           company_code, status_query, is_complete AS prev_complete
    FROM `{PROJECT}.{DATASET}.close_tasks`
    ORDER BY sort_order
    """
    try:
        return [dict(row) for row in BQ_CLIENT.query(query).result()]
    except Exception as e:
        log.error(f"Failed to fetch close tasks: {e}")
        return []


def update_task_status(task: dict, result: dict, now: datetime) -> None:
    """Update close_tasks and write history record if status changed."""
    task_id = task['task_id']
    prev = task.get('prev_complete')
    curr = result['is_complete']
    changed_from = 'COMPLETE' if prev else 'INCOMPLETE'
    changed_to   = 'COMPLETE' if curr else 'INCOMPLETE'

    # Update close_tasks
    update_sql = f"""
    UPDATE `{PROJECT}.{DATASET}.close_tasks`
    SET
      is_complete     = @is_complete,
      metric_value    = @metric_value,
      detail          = @detail,
      last_checked_at = @now,
      completed_at    = CASE
        WHEN @is_complete AND completed_at IS NULL THEN @now
        WHEN NOT @is_complete THEN NULL
        ELSE completed_at
      END
    WHERE task_id = @task_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter('is_complete',  'BOOL',      curr),
        bigquery.ScalarQueryParameter('metric_value', 'STRING',    result['metric_value']),
        bigquery.ScalarQueryParameter('detail',       'STRING',    result['detail']),
        bigquery.ScalarQueryParameter('now',          'TIMESTAMP', now),
        bigquery.ScalarQueryParameter('task_id',      'STRING',    task_id),
    ])
    BQ_CLIENT.query(update_sql, job_config=job_config).result()

    # Write history only if status changed
    if prev != curr:
        log.info(f"  Task {task_id} status changed: {changed_from} -> {changed_to}")
        history_sql = f"""
        INSERT INTO `{PROJECT}.{DATASET}.close_task_history`
          (task_id, fiscal_year, fiscal_period, checked_at,
           was_complete, metric_value, detail, changed_from, changed_to)
        VALUES (
          @task_id, @fiscal_year, @fiscal_period, @now,
          @is_complete, @metric_value, @detail,
          @changed_from, @changed_to
        )
        """
        hist_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter('task_id',       'STRING',    task_id),
            bigquery.ScalarQueryParameter('fiscal_year',   'STRING',    task['fiscal_year']),
            bigquery.ScalarQueryParameter('fiscal_period', 'STRING',    task['fiscal_period']),
            bigquery.ScalarQueryParameter('now',           'TIMESTAMP', now),
            bigquery.ScalarQueryParameter('is_complete',   'BOOL',      curr),
            bigquery.ScalarQueryParameter('metric_value',  'STRING',    result['metric_value']),
            bigquery.ScalarQueryParameter('detail',        'STRING',    result['detail']),
            bigquery.ScalarQueryParameter('changed_from',  'STRING',    changed_from),
            bigquery.ScalarQueryParameter('changed_to',    'STRING',    changed_to),
        ])
        BQ_CLIENT.query(history_sql, job_config=hist_config).result()


def main() -> dict:
    now = datetime.now(timezone.utc)
    log.info(f"Close task runner starting — {now.isoformat()} — project={PROJECT} dataset={DATASET}")

    tasks = get_open_tasks()
    if not tasks:
        log.warning("No close tasks found. Check that close_tasks table has been seeded.")
        return {'complete': 0, 'incomplete': 0, 'errors': 0}

    log.info(f"Found {len(tasks)} tasks to evaluate")
    summary = {'complete': 0, 'incomplete': 0, 'errors': 0}

    for task in tasks:
        task_id = task['task_id']
        log.info(f"Evaluating: {task_id} — {task.get('task_name', 'unnamed')}")

        result = run_status_query(task_id, task.get('status_query', ''))

        try:
            update_task_status(task, result, now)
        except Exception as e:
            log.error(f"  Failed to update task {task_id}: {e}")
            summary['errors'] += 1
            continue

        if result['is_complete']:
            summary['complete'] += 1
            log.info(f"  COMPLETE: {result['metric_value']}")
        else:
            summary['incomplete'] += 1
            log.info(f"  INCOMPLETE: {result['metric_value']}")

    log.info(
        f"Run complete: {summary['complete']} complete, "
        f"{summary['incomplete']} incomplete, {summary['errors']} errors "
        f"(of {len(tasks)} total)"
    )
    return summary


if __name__ == '__main__':
    result = main()
    # Exit with non-zero if there were errors (alerts Cloud Run)
    if result.get('errors', 0) > 0:
        sys.exit(1)
