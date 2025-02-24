import os
import pickle
from abc import abstractmethod
from typing import Union

import dagster._check as check
from dagster._annotations import experimental
from dagster._config import Field, StringSource
from dagster._core.errors import DagsterInvariantViolationError
from dagster._core.execution.context.input import InputContext
from dagster._core.execution.context.output import OutputContext
from dagster._core.storage.io_manager import IOManager, io_manager
from dagster._utils import PICKLE_PROTOCOL, mkdir_p


class MemoizableIOManager(IOManager):
    """
    Base class for IO manager enabled to work with memoized execution. Users should implement
    the ``load_input`` and ``handle_output`` methods described in the ``IOManager`` API, and the
    ``has_output`` method, which returns a boolean representing whether a data object can be found.
    """

    @abstractmethod
    def has_output(self, context: OutputContext) -> bool:
        """The user-defined method that returns whether data exists given the metadata.

        Args:
            context (OutputContext): The context of the step performing this check.

        Returns:
            bool: True if there is data present that matches the provided context. False otherwise.
        """


class VersionedPickledObjectFilesystemIOManager(MemoizableIOManager):
    def __init__(self, base_dir=None):
        self.base_dir = check.opt_str_param(base_dir, "base_dir")
        self.write_mode = "wb"
        self.read_mode = "rb"

    def _get_path(self, context: Union[InputContext, OutputContext]) -> str:
        output_context: OutputContext

        if isinstance(context, OutputContext):
            output_context = context
        else:
            if context.upstream_output is None:
                raise DagsterInvariantViolationError(
                    "Missing value of InputContext.upstream_output. "
                    "Cannot compute the input path."
                )

            output_context = context.upstream_output

        # automatically construct filepath
        step_key = check.str_param(output_context.step_key, "context.step_key")
        output_name = check.str_param(output_context.name, "context.name")
        version = check.str_param(output_context.version, "context.version")

        return os.path.join(self.base_dir, step_key, output_name, version)

    def handle_output(self, context, obj):
        """Pickle the data with the associated version, and store the object to a file.

        This method omits the AssetMaterialization event so assets generated by it won't be tracked
        by the Asset Catalog.
        """

        filepath = self._get_path(context)

        context.log.debug(f"Writing file at: {filepath}")

        # Ensure path exists
        mkdir_p(os.path.dirname(filepath))

        with open(filepath, self.write_mode) as write_obj:
            pickle.dump(obj, write_obj, PICKLE_PROTOCOL)

    def load_input(self, context):
        """Unpickle the file and Load it to a data object."""

        filepath = self._get_path(context)

        context.log.debug(f"Loading file from: {filepath}")

        with open(filepath, self.read_mode) as read_obj:
            return pickle.load(read_obj)

    def has_output(self, context):
        """Returns true if data object exists with the associated version, False otherwise."""

        filepath = self._get_path(context)

        context.log.debug(f"Checking for file at: {filepath}")

        return os.path.exists(filepath) and not os.path.isdir(filepath)


@io_manager(config_schema={"base_dir": Field(StringSource, is_required=False)})
@experimental
def versioned_filesystem_io_manager(init_context):
    """Filesystem IO manager that utilizes versioning of stored objects.

    It requires users to specify a base directory where all the step outputs will be stored in. It
    serializes and deserializes output values (assets) using pickling and automatically constructs
    the filepaths for the assets using the provided directory, and the version for a provided step
    output.
    """
    return VersionedPickledObjectFilesystemIOManager(
        base_dir=init_context.resource_config.get(
            "base_dir", os.path.join(init_context.instance.storage_directory(), "versioned_outputs")
        )
    )
