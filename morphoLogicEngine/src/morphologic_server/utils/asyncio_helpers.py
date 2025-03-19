"""Helper functions for asyncio."""

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Task Group Terminator ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
class TerminateTaskGroup(Exception):
    """Exception raised to terminate a teask group."""

async def force_terminate_task_group():
    """Used to force termination of a task group."""
    raise TerminateTaskGroup()
# ------------------------------------------------------------------------------------------------ #
