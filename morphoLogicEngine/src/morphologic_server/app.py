"""
Application bootstrap and dependency injection.

This is the ONLY place where globals happen - at startup in main().
Everything else receives dependencies explicitly.
"""

import asyncio
import logging
from typing import Optional

from morphologic_server.config import ServerSettings


class Server:
    """
    The application server - all dependencies injected, NO globals.
    
    Instead of:
        from morphologic_server.config import settings  # BAD: hidden global
        from morphologic_server import context  # BAD: mutable global
    
    Do this:
        settings = ServerSettings()  # Load config
        server = Server(settings)  # Pass to server
        await server.run()  # Everything inside has access
    """
    
    def __init__(self, settings: ServerSettings):
        """
        Initialize server with explicit dependencies.
        
        Args:
            settings: ServerSettings instance (never None, always validated)
        """
        self.settings = settings
        self.logger = logging.getLogger("morphologic")
        self._setup_logging()
        
        # Services will be initialized on demand
        self._kafka = None
        self._database = None
        self._message_handler = None
    
    def _setup_logging(self) -> None:
        """Configure logging based on settings."""
        level = logging.DEBUG if self.settings.is_debug() else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    async def initialize_services(self) -> None:
        """
        Initialize all services with settings.
        
        This is where Kafka, Database, and other services are created.
        Everything is explicit - no hidden state.
        """
        self.logger.info("Initializing services...")
        
        # Kafka service
        from morphologic_server.services.kafka_service import KafkaService
        self._kafka = KafkaService(self.settings)
        
        # Database service  
        from morphologic_server.services.database_service import DatabaseService
        self._database = DatabaseService(self.settings)
        
        # Message handler
        from morphologic_server.services.message_handler import MessageHandler
        self._message_handler = MessageHandler(
            kafka=self._kafka,
            database=self._database,
            settings=self.settings,
            logger=self.logger
        )
        
        self.logger.info("Services initialized successfully")
    
    async def run(self) -> None:
        """
        Start the server with all services.
        
        No globals, no hidden state. Everything is explicit.
        """
        try:
            await self.initialize_services()
            
            self.logger.info("Starting morphoLogic v%s", self.settings.SERVER_VERSION)
            
            # Start message handler
            await self._message_handler.start()
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error("Server error: %s", e, exc_info=True)
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """
        Graceful shutdown of all services.
        """
        self.logger.info("Shutting down...")
        
        if self._kafka:
            await self._kafka.close()
        
        if self._database:
            await self._database.close()
        
        if self._message_handler:
            await self._message_handler.stop()
        
        self.logger.info("Shutdown complete")


async def main() -> None:
    """
    Entry point - this is the ONLY place where we create globals.
    
    Everything else receives dependencies explicitly through constructors.
    """
    # Load configuration (only once, at startup)
    settings = ServerSettings()
    
    # Create server with settings
    server = Server(settings)
    
    # Run server (all dependencies are inside the server instance)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
