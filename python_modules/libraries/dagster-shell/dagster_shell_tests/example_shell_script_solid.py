# pylint: disable=no-value-for-parameter
from dagster_shell import create_shell_script_solid

from dagster import file_relative_path
from dagster._legacy import pipeline


@pipeline
def pipe():
    a = create_shell_script_solid(file_relative_path(__file__, "hello_world.sh"), name="a")
    a()
