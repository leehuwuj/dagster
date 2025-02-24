from dagster import repository
from dagster._legacy import pipeline


@pipeline
def pipeline_one():
    pass


@pipeline
def pipeline_two():
    pass


@repository
def multi_pipeline():
    return [pipeline_one, pipeline_two]
