import asyncio

from morphologic_server import logger
from morphologic_server.db.memory import Memory
from morphologic_server.db.models import Character
from morphologic_server.db.memory import STANDARD_VISIBILITY_RADIUS

async def stresstest_get_full_surroundings(self, character: Character, memory: Memory, radius: float = STANDARD_VISIBILITY_RADIUS, iterations: int = 10):
        """Stresstest version of get_full_surroundings, with multiple concurrent queries."""
        tasks = [memory.get_full_surroundings(character, radius) for _ in range(iterations)]
        # Let's add timestamps to see how long it takes for each query to complete
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()
        logger.info("Stresstest completed %d iterations in %.2f seconds (%.2f seconds per query)", iterations, end_time - start_time, (end_time - start_time) / iterations)
    