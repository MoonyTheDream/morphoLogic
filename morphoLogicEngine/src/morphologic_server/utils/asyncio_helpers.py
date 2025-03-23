"""Helper functions for asyncio."""

# 888                                  d8b                   888
# 888                                  Y8P                   888
# 888                                                        888
# 888888 .d88b.  888d888 88888b.d88b.  888 88888b.   8888b.  888888 .d88b.  888d888
# 888   d8P  Y8b 888P"   888 "888 "88b 888 888 "88b     "88b 888   d88""88b 888P"
# 888   88888888 888     888  888  888 888 888  888 .d888888 888   888  888 888
# Y88b. Y8b.     888     888  888  888 888 888  888 888  888 Y88b. Y88..88P 888
#  "Y888 "Y8888  888     888  888  888 888 888  888 "Y888888  "Y888 "Y88P"  888


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Task Group Terminator ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
class TerminateTaskGroup(Exception):
    """Exception raised to terminate a teask group."""


async def force_terminate_task_group():
    """Used to force termination of a task group."""
    raise TerminateTaskGroup()


# ------------------------------------------------------------------------------------------------ #
