"""Acme's nightly customer export — fixture file, parsed by AST only, never executed.

Deliberate smells: no failure callback, and a hardcoded FTP password (the credential scan
lives in the ai-usage collector, which walks the whole repo).
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

# Fixture-only fake credential — this is exactly the smell the scan exists to catch.
ftp_password = "hunter2-hunter2-hunter2"

default_args = {
    "owner": "data-eng",
    "retries": 3,
}


def export_customers() -> None:
    print("exporting customers over ftp")


dag = DAG(
    "customer_export",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
)

export = PythonOperator(task_id="export_customers", python_callable=export_customers, dag=dag)
