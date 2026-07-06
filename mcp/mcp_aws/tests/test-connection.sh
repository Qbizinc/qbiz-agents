#!/usr/bin/env bash

export AWS_READONLY_ROLE_ARN=arn:aws:iam::907770664110:role/aws-readonly-mcp
export AWS_READONLY_EXTERNAL_ID=aws-readonly-mcp
export AWS_READONLY_SESSION_NAME=mcp-reader
export AWS_READONLY_REGION=us-west-2
export AWS_PROFILE=sts

export PYTHONPATH=../src/aws_readonly_mcp/:$PYTHONPATH
# source ../.venv/bin/activate
python3 connect.py