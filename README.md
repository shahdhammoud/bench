# Benchmark Dataset Generator

This repository contains the pipeline for generating a controllable benchmark dataset for evaluating and improving the AI code reviewer agent.

## Setup

    pip install -r requirements.txt
    cp .env.example .env

## Usage

    # Step 3 - Parse existing documentation
    python parser/parser.py --docs_dir /path/to/docs --output result.json

    # Step 4 - Generate documentation from gold code
    python doc_generator/run.py --repo_path /path/to/gold/code --output_dir data/my_task
