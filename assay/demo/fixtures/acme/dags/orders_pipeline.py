"""Acme's hourly orders pipeline — fixture file, parsed by AST only, never executed.

Deliberate smells: no retries, no failure callback, default 'airflow' owner, catchup=True.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "airflow",
}

dag = DAG(
    "orders_pipeline",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@hourly",
    catchup=True,
)

extract = BashOperator(task_id="extract_orders", bash_command="./bin/extract_orders.sh", dag=dag)
load = BashOperator(task_id="load_orders", bash_command="./bin/load_orders.sh", dag=dag)
extract >> load
